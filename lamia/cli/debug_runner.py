"""
Lamia debug runner — step-by-step debugger for .lm files.

Two modes:
  Interactive (default):  lamia debug file.lm
  JSON protocol (IDE):   lamia debug file.lm --json

The JSON mode speaks a line-delimited JSON protocol over stdio,
compatible with the Lamia IDE debug adapter.
"""

import sys
import os
import json
import threading
import traceback
import argparse
import logging

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = 1


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

class _JsonProtocolIO:
    """JSON-lines protocol over dup'd stdout/stdin fds.

    Duplicates stdout/stdin at construction so user-facing print() and
    logging can be redirected to ``_DebugOutputStream`` without
    interfering with the protocol channel.
    """

    def __init__(self):
        self._out_fd = os.dup(sys.stdout.fileno())
        self._wlock = threading.Lock()
        self._in_file = os.fdopen(
            os.dup(sys.stdin.fileno()), "r", encoding="utf-8"
        )

    def send(self, obj: dict) -> None:
        raw = json.dumps(obj, default=str) + "\n"
        with self._wlock:
            os.write(self._out_fd, raw.encode())

    def recv(self) -> dict | None:
        line = self._in_file.readline()
        if not line:
            return None
        return json.loads(line)


class _DebugOutputStream:
    """Replacement for sys.stdout/stderr that routes output through the protocol."""

    encoding = "utf-8"

    def __init__(self, io: _JsonProtocolIO, category: str):
        self._io = io
        self._category = category

    def write(self, text: str) -> None:
        if text:
            self._io.send({
                "type": "event", "event": "output",
                "category": self._category, "text": text,
            })

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        raise OSError("not a real file descriptor")


# ---------------------------------------------------------------------------
# Core debugger
# ---------------------------------------------------------------------------

class LamiaDebugger:
    """Trace-based debugger that maps transformed Python lines back to .lm source."""

    def __init__(self, file_path: str, *, json_mode: bool = False):
        self.file_path = os.path.abspath(file_path)
        self.json_mode = json_mode
        self.breakpoints: dict[str, set[int]] = {}
        self.step_mode: str | None = None
        self.step_depth = 0
        self.current_depth = 0
        self.current_frame = None
        self.current_line = 0
        self.current_file: str = self.file_path
        self.line_maps: dict[str, dict[int, int]] = {}
        self.running = True
        self.paused = threading.Event()
        self._var_handles: dict[int, object] = {}
        self._next_var_ref = 2  # 1 is reserved for Locals scope by DAP session

        if json_mode:
            self.io = _JsonProtocolIO()
        else:
            self.io = None

    # -- tracing ------------------------------------------------------------

    def _trace(self, frame, event, arg):
        if not self.running:
            return None
        filename = os.path.abspath(frame.f_code.co_filename)
        is_ours = filename in self.line_maps
        if event == "call":
            if is_ours:
                self.current_depth += 1
            return self._trace
        if event == "return":
            if is_ours:
                self.current_depth -= 1
                if self.step_mode == "stepOut" and self.current_depth < self.step_depth:
                    self.step_mode = None
                    self._stop(frame, "step", filename=filename)
            return self._trace
        if event == "line" and is_ours:
            raw = frame.f_lineno
            file_map = self.line_maps.get(filename, {})
            orig = file_map.get(raw, raw)
            if orig <= 0:
                return self._trace
            should_stop = False
            reason = "step"
            bp_set = self.breakpoints.get(filename, set())
            if orig in bp_set:
                should_stop = True
                reason = "breakpoint"
            elif self.step_mode == "stepIn":
                should_stop = True
            elif self.step_mode == "next" and self.current_depth <= self.step_depth:
                should_stop = True
            elif self.step_mode == "pause":
                should_stop = True
                reason = "pause"
            if should_stop:
                self._stop(frame, reason, orig, filename)
        return self._trace

    def _stop(self, frame, reason, lineno=None, filename=None):
        self.current_frame = frame
        self.current_line = lineno or frame.f_lineno
        self.current_file = filename or self.file_path
        if self.json_mode:
            self.io.send({
                "type": "event", "event": "stopped",
                "reason": reason,
                "line": self.current_line,
                "file": self.current_file,
            })
            self.paused.clear()
            self.paused.wait()
        else:
            self._interactive_stop(reason)

    # -- variable / stack inspection ----------------------------------------

    def _is_expandable(self, val) -> bool:
        if isinstance(val, (dict, list, tuple, set)):
            return len(val) > 0
        if hasattr(val, "model_dump"):
            try:
                dumped = val.model_dump()
                return isinstance(dumped, dict) and len(dumped) > 0
            except Exception:
                return False
        try:
            return len(vars(val)) > 0
        except Exception:
            return False

    def _preview_value(self, val) -> str:
        try:
            if isinstance(val, dict):
                return f"dict({len(val)})"
            if isinstance(val, list):
                return f"list({len(val)})"
            if isinstance(val, tuple):
                return f"tuple({len(val)})"
            if isinstance(val, set):
                return f"set({len(val)})"
            if hasattr(val, "model_dump"):
                return f"{type(val).__name__}"
            return repr(val)[:500]
        except Exception:
            return "<error>"

    def _store_handle(self, val) -> int:
        ref = self._next_var_ref
        self._next_var_ref += 1
        self._var_handles[ref] = val
        return ref

    def _make_var(self, name: str, val) -> dict:
        ref = self._store_handle(val) if self._is_expandable(val) else 0
        return {
            "name": name,
            "value": self._preview_value(val),
            "type": type(val).__name__,
            "variablesReference": ref,
        }

    def _variables_for_value(self, val) -> list[dict]:
        result: list[dict] = []
        try:
            if isinstance(val, dict):
                for key, child in list(val.items())[:500]:
                    result.append(self._make_var(str(key), child))
                return result
            if isinstance(val, (list, tuple)):
                for idx, child in enumerate(list(val)[:500]):
                    result.append(self._make_var(f"[{idx}]", child))
                return result
            if isinstance(val, set):
                for idx, child in enumerate(list(val)[:500]):
                    result.append(self._make_var(f"[{idx}]", child))
                return result
            if hasattr(val, "model_dump"):
                dumped = val.model_dump()
                if isinstance(dumped, dict):
                    for key, child in list(dumped.items())[:500]:
                        result.append(self._make_var(str(key), child))
                    return result
            attrs = vars(val)
            for key, child in list(attrs.items())[:500]:
                if str(key).startswith("__") and str(key).endswith("__"):
                    continue
                result.append(self._make_var(str(key), child))
            return result
        except Exception:
            return result

    def _collect_variables(self, reference: int = 1) -> list[dict]:
        if self.current_frame is None:
            return []
        if reference == 1:
            # Fresh locals request: reset handle map.
            self._var_handles.clear()
            self._next_var_ref = 2
            result = []
            for name, val in self.current_frame.f_locals.items():
                if name.startswith("__") and name.endswith("__"):
                    continue
                result.append(self._make_var(name, val))
            return result
        target = self._var_handles.get(reference)
        if target is None:
            return []
        return self._variables_for_value(target)

    def _collect_stack(self) -> list[dict]:
        frames = []
        f = self.current_frame
        while f:
            fn = os.path.abspath(f.f_code.co_filename)
            if fn in self.line_maps:
                raw = f.f_lineno
                file_map = self.line_maps[fn]
                orig = file_map.get(raw, raw)
                name = f.f_code.co_name
                if name == "<module>":
                    name = os.path.basename(fn)
                frames.append({"name": name, "file": fn, "line": max(orig, 1)})
            f = f.f_back
        return frames

    def _evaluate(self, expression: str) -> dict:
        if self.current_frame is None:
            return {"error": "No active frame"}
        try:
            merged = {**self.current_frame.f_globals, **self.current_frame.f_locals}
            val = eval(expression, merged)
            ref = self._store_handle(val) if self._is_expandable(val) else 0
            return {
                "value": self._preview_value(val),
                "type": type(val).__name__,
                "variablesReference": ref,
            }
        except Exception as e:
            return {"error": str(e)}

    # -- JSON command loop (IDE mode) ---------------------------------------

    def _json_command_loop(self):
        while self.running:
            msg = self.io.recv()
            if msg is None:
                self.running = False
                self.paused.set()
                break
            cmd = msg.get("command")
            if cmd == "continue":
                self.step_mode = None
                self.paused.set()
            elif cmd == "next":
                self.step_mode = "next"
                self.step_depth = self.current_depth
                self.paused.set()
            elif cmd == "stepIn":
                self.step_mode = "stepIn"
                self.paused.set()
            elif cmd == "stepOut":
                self.step_mode = "stepOut"
                self.step_depth = self.current_depth
                self.paused.set()
            elif cmd == "pause":
                self.step_mode = "pause"
            elif cmd == "configurationDone":
                self.paused.set()
            elif cmd == "setBreakpoints":
                f = msg.get("file", self.file_path)
                self.breakpoints[os.path.abspath(f)] = set(msg.get("lines", []))
                self.io.send({
                    "type": "response", "command": "setBreakpoints",
                    "breakpoints": sorted(self.breakpoints.get(os.path.abspath(f), [])),
                })
            elif cmd == "getVariables":
                try:
                    reference = int(msg.get("reference", 1))
                except Exception:
                    reference = 1
                self.io.send({
                    "type": "response", "command": "getVariables",
                    "variables": self._collect_variables(reference),
                })
            elif cmd == "getStackTrace":
                self.io.send({
                    "type": "response", "command": "getStackTrace",
                    "frames": self._collect_stack(),
                })
            elif cmd == "evaluate":
                expr = msg.get("expression", "")
                self.io.send({
                    "type": "response", "command": "evaluate",
                    "result": self._evaluate(expr),
                })
            elif cmd == "disconnect":
                self.running = False
                self.paused.set()
                break

    # -- Interactive CLI mode -----------------------------------------------

    def _interactive_stop(self, reason: str):
        """Handle a stop in interactive (terminal) mode."""
        src_line = ""
        try:
            with open(self.current_file) as f:
                lines = f.readlines()
                if 1 <= self.current_line <= len(lines):
                    src_line = lines[self.current_line - 1].rstrip()
        except Exception:
            pass
        label = os.path.basename(self.current_file)
        if reason == "breakpoint":
            print(f"Hit breakpoint at line {self.current_line}")
        print(f"> {label}:{self.current_line}  {src_line}")
        self._interactive_prompt()

    def _interactive_prompt(self):
        """Read commands from the terminal until the user resumes execution."""
        while True:
            try:
                cmd = input("(lamia-dbg) ").strip()
            except (EOFError, KeyboardInterrupt):
                self.running = False
                return
            if not cmd:
                continue
            parts = cmd.split(None, 1)
            verb = parts[0].lower()
            rest = parts[1] if len(parts) > 1 else ""

            if verb in ("c", "continue"):
                self.step_mode = None
                return
            elif verb in ("n", "next"):
                self.step_mode = "next"
                self.step_depth = self.current_depth
                return
            elif verb in ("s", "step", "stepin"):
                self.step_mode = "stepIn"
                return
            elif verb in ("out", "stepout"):
                self.step_mode = "stepOut"
                self.step_depth = self.current_depth
                return
            elif verb in ("b", "break"):
                self._cmd_break(rest)
            elif verb in ("p", "print"):
                self._cmd_print(rest)
            elif verb in ("bt", "backtrace", "where"):
                self._cmd_backtrace()
            elif verb in ("l", "locals"):
                self._cmd_locals()
            elif verb in ("q", "quit", "exit"):
                self.running = False
                return
            elif verb in ("h", "help"):
                self._cmd_help()
            else:
                self._cmd_print(cmd)

    def _cmd_break(self, rest: str):
        if not rest:
            for f, lines in self.breakpoints.items():
                for ln in sorted(lines):
                    print(f"  {os.path.basename(f)}:{ln}")
            if not any(self.breakpoints.values()):
                print("  No breakpoints set.")
            return
        try:
            line = int(rest)
            bp_set = self.breakpoints.setdefault(self.current_file, set())
            bp_set.add(line)
            print(f"Breakpoint at line {line}")
        except ValueError:
            print(f"Usage: break <line_number>")

    def _cmd_print(self, expr: str):
        if not expr:
            print("Usage: print <expression>")
            return
        result = self._evaluate(expr)
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"({result.get('type', '?')}) {result.get('value', '')}")

    def _cmd_backtrace(self):
        for frame in self._collect_stack():
            print(f"  {frame['name']}  {os.path.basename(frame['file'])}:{frame['line']}")

    def _cmd_locals(self):
        for v in self._collect_variables():
            print(f"  {v['name']}: {v['type']} = {v['value'][:80]}")

    def _cmd_help(self):
        print("""Commands:
  continue (c)      Resume execution
  next (n)          Step over (same depth)
  step (s)          Step into
  stepout (out)     Step out of current function
  break N (b N)     Set breakpoint at line N
  break             List breakpoints
  print EXPR (p)    Evaluate expression
  locals (l)        Show local variables
  backtrace (bt)    Show call stack
  quit (q)          Stop debugging
  help (h)          Show this help
  <expr>            Evaluate expression (shortcut)""")

    # -- execution ----------------------------------------------------------

    def _setup_and_execute(self):
        """Patch HybridExecutor and run the file through the normal CLI path."""
        from lamia.interpreter.hybrid_executor import HybridExecutor
        original_execute = HybridExecutor.execute_file
        debugger = self
        interactive_initialized = [False]

        def patched_execute_file(executor_self, file_path, globals_dict=None,
                                 enable_lazy_dependency_loading=False):
            resolved = os.path.abspath(file_path)
            with open(resolved, "r") as f:
                original_source = f.read()
            transformed = executor_self.transform(original_source, debug=True)
            smap = executor_self.source_map
            if smap:
                debugger.line_maps[resolved] = smap
            else:
                debugger.line_maps[resolved] = _fallback_offset_map(original_source, transformed)

            if not debugger.json_mode and not interactive_initialized[0]:
                interactive_initialized[0] = True
                print(f"Lamia Debugger — {os.path.basename(debugger.file_path)}")
                print("Type 'help' for commands.\n")
                if not debugger.breakpoints:
                    debugger.step_mode = "stepIn"

            old_settrace = sys.gettrace()
            threading.settrace(debugger._trace)
            sys.settrace(debugger._trace)
            try:
                original_execute(executor_self, file_path, globals_dict,
                                 enable_lazy_dependency_loading)
            finally:
                sys.settrace(old_settrace)
                threading.settrace(old_settrace)

        HybridExecutor.execute_file = patched_execute_file

        _original_exit = os._exit
        def _soft_exit(code=0):
            raise SystemExit(code)
        os._exit = _soft_exit

        try:
            sys.argv = ["lamia", self.file_path]
            from lamia.cli.cli import main as lamia_main
            lamia_main()
        finally:
            os._exit = _original_exit

    def run(self):
        """Entry point. Sets up I/O and starts execution."""
        if self.json_mode:
            sys.stdout = _DebugOutputStream(self.io, "stdout")
            sys.stderr = _DebugOutputStream(self.io, "stderr")
            cmd_thread = threading.Thread(target=self._json_command_loop, daemon=True)
            cmd_thread.start()
            self.io.send({"type": "event", "event": "initialized", "protocolVersion": PROTOCOL_VERSION})
            self.paused.clear()
            self.paused.wait()

        exit_code = 0
        try:
            self._setup_and_execute()
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else 0
        except KeyboardInterrupt:
            exit_code = 130
        except Exception:
            if self.json_mode:
                self.io.send({
                    "type": "event", "event": "output",
                    "category": "stderr", "text": traceback.format_exc(),
                })
            else:
                traceback.print_exc()
            exit_code = 1
        finally:
            if self.json_mode:
                self.io.send({"type": "event", "event": "terminated", "exitCode": exit_code})
            else:
                print(f"\nProgram terminated (exit code {exit_code})")


# ---------------------------------------------------------------------------
# Fallback line map when the engine source map is empty
# ---------------------------------------------------------------------------

def _fallback_offset_map(original_source: str, transformed_source: str) -> dict[int, int]:
    orig_lines = original_source.splitlines()
    trans_lines = transformed_source.splitlines()
    added = 0
    for line in trans_lines:
        s = line.strip()
        if s.startswith("from ") or s.startswith("import ") or s == "":
            added += 1
        else:
            break
    orig_imp = 0
    for line in orig_lines:
        s = line.strip()
        if s.startswith("from ") or s.startswith("import ") or s == "":
            orig_imp += 1
        else:
            break
    offset = added - orig_imp
    lmap = {}
    for i in range(len(trans_lines)):
        t = i + 1
        o = t - offset
        if 1 <= o <= len(orig_lines):
            lmap[t] = o
    return lmap


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def handle_debug():
    """Handle ``lamia debug <file> [--json] [--break N]``."""
    parser = argparse.ArgumentParser(
        prog="lamia debug",
        description="Step-by-step debugger for .lm files",
    )
    parser.add_argument("file", help="Lamia .lm file to debug")
    parser.add_argument("--json", action="store_true",
                        help="Machine-readable JSON-lines protocol (for IDE integration)")
    parser.add_argument("--break", "-b", type=int, action="append", dest="breakpoints",
                        default=[], metavar="LINE",
                        help="Set breakpoint at LINE (can repeat)")
    parser.add_argument("--stop-on-entry", action="store_true",
                        help="Pause on the first executable line")
    args = parser.parse_args(sys.argv[2:])

    if not os.path.isfile(args.file):
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    debugger = LamiaDebugger(args.file, json_mode=args.json)

    if args.breakpoints:
        abs_file = os.path.abspath(args.file)
        debugger.breakpoints[abs_file] = set(args.breakpoints)
        if not args.json:
            for ln in sorted(args.breakpoints):
                print(f"Breakpoint at line {ln}")

    if args.stop_on_entry:
        debugger.step_mode = "stepIn"

    debugger.run()
