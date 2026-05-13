"""
``lamia inspect <file>`` — lightweight file analysis for IDE integration.

Uses the same Lamia parser pipeline as the debugger to determine whether
a .lm file has top-level executable statements (as opposed to only
definitions/imports).

Pipeline: HybridSyntaxParser.transform_with_source_map() → AST analysis.
Files with invalid syntax are reported as non-executable.
"""

import argparse
import ast
import json
import re
import sys
import os
from pathlib import Path
from typing import List, Optional, Dict, Set

from lamia.interpreter.hybrid_syntax_parser import HybridSyntaxParser
from lamia.interpreter.human.parser import parse_hu_file, HuFunction


_NON_EXEC_TYPES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Import,
    ast.ImportFrom,
)


def has_top_level_steps(source: str) -> bool:
    """Public API: does this source have executable steps?"""
    return _analyze(source).executable


def get_executable_lines(source: str) -> List[int]:
    """Public API: which original source lines are executable steps?"""
    return _analyze(source).steps


class InspectResult:
    __slots__ = ("executable", "steps", "diagnostics")

    def __init__(
        self,
        executable: bool,
        steps: List[int],
        diagnostics: List[dict],
    ) -> None:
        self.executable = executable
        self.steps = steps
        self.diagnostics = diagnostics


def _analyze(source: str, file_path: Optional[str] = None) -> InspectResult:
    """Transform via Lamia parser, then detect steps via AST."""
    parser = HybridSyntaxParser()
    try:
        transformed, source_map = parser.transform_with_source_map(source)
    except SyntaxError as e:
        diag = _syntax_error_to_diagnostic(e, "lamia-parser")
        return InspectResult(False, [], [diag] if diag else [])
    except (TypeError, ValueError) as e:
        return InspectResult(False, [], [{
            "severity": "error",
            "message": str(e),
            "line": 1,
            "col": 0,
            "source": "lamia-parser",
        }])

    try:
        tree = ast.parse(transformed)
    except SyntaxError as e:
        diag = _syntax_error_to_diagnostic(e, "lamia-ast")
        if diag and source_map:
            orig_line = source_map.get(diag["line"], diag["line"])
            if orig_line > 0:
                diag["line"] = orig_line
        return InspectResult(False, [], [diag] if diag else [])

    step_lines: List[int] = []
    for node in tree.body:
        if isinstance(node, _NON_EXEC_TYPES):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        step_lines.append(node.lineno)

    original_lines: List[int] = []
    for line in step_lines:
        orig = source_map.get(line, line)
        if orig > 0:
            original_lines.append(orig)

    deduped = sorted(set(original_lines))

    diagnostics: List[dict] = []
    if file_path:
        diagnostics = _check_call_integrity(tree, source_map, source, file_path)

    return InspectResult(len(deduped) > 0, deduped, diagnostics)


_INLINE_DEF_PARAM_RE = re.compile(r'\{(\w+)(?::[^}]*)?\}')
_INLINE_DEF_FILEREF_RE = re.compile(r'\{@(\w+)\}')
_SKIP_DIRS = {"node_modules", "__pycache__", ".git", "venv", ".venv", ".tox", "dist", "build"}


def _discover_hu_functions(file_path: str) -> Dict[str, HuFunction]:
    """Scan for .hu files in the project containing the inspected file."""
    start_dir = Path(file_path).resolve().parent
    registry: Dict[str, HuFunction] = {}

    project_root = _find_project_root(start_dir)
    if not project_root:
        project_root = start_dir

    for hu_path in project_root.rglob("*.hu"):
        if any(part in _SKIP_DIRS for part in hu_path.parts):
            continue
        try:
            fn = parse_hu_file(str(hu_path))
            if fn.name not in registry:
                registry[fn.name] = fn
        except (OSError, ValueError):
            continue

    return registry


def _find_project_root(start: Path) -> Optional[Path]:
    """Walk up to find .git or pyproject.toml — capped at 5 levels."""
    current = start
    for _ in range(5):
        if (current / ".git").exists() or (current / "pyproject.toml").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _collect_local_defs(tree: ast.AST) -> Set[str]:
    """Collect function names defined in the file."""
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


def _collect_inline_def_params(source: str) -> Dict[str, Set[str]]:
    """For each inline def, collect the template parameters (from body string)."""
    result: Dict[str, Set[str]] = {}
    lines = source.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        m = re.match(r'def\s+(\w+)\s*\(([^)]*)\)', stripped)
        if not m:
            continue
        func_name = m.group(1)
        sig_params = {p.strip().split("=")[0].strip() for p in m.group(2).split(",") if p.strip()}

        body_line_idx = i + 1
        if body_line_idx >= len(lines):
            continue
        body = lines[body_line_idx]

        template_refs: Set[str] = set()
        for pm in _INLINE_DEF_PARAM_RE.finditer(body):
            template_refs.add(pm.group(1))
        for pm in _INLINE_DEF_FILEREF_RE.finditer(body):
            template_refs.add(pm.group(1))

        missing = template_refs - sig_params
        if missing:
            result[func_name] = missing

    return result


_CALL_RE = re.compile(r'(?:^|\s)(?:\w+\s*=\s*)?(\w+)\(([^)]*)\)')


def _check_call_integrity(
    tree: ast.Module,
    source_map: Dict[int, int],
    source: str,
    file_path: str,
) -> List[dict]:
    """Validate function calls against .hu definitions and inline defs."""
    hu_registry = _discover_hu_functions(file_path)
    local_defs = _collect_local_defs(tree)
    inline_mismatches = _collect_inline_def_params(source)
    diagnostics: List[dict] = []

    for func_name, missing_params in inline_mismatches.items():
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if re.match(rf'\s*def\s+{re.escape(func_name)}\s*\(', line):
                diagnostics.append({
                    "severity": "warning",
                    "message": (
                        f"{func_name}() template references "
                        f"{', '.join(sorted(missing_params))} "
                        f"not in function signature"
                    ),
                    "line": i + 1,
                    "col": 0,
                    "source": "lamia-semantic",
                })
                break

    lines = source.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("def "):
            continue

        m = _CALL_RE.search(line)
        if not m:
            continue

        func_name = m.group(1)
        if func_name.startswith("__LAMIA_"):
            continue
        if func_name in local_defs:
            continue
        if func_name in _PYTHON_BUILTINS:
            continue
        if "." in line[:m.start() + len(m.group(0))] and line[m.start()] != " ":
            idx = line.find(func_name + "(")
            if idx > 0 and line[idx - 1] == ".":
                continue

        if func_name not in hu_registry:
            col = line.find(func_name)
            diagnostics.append({
                "severity": "error",
                "message": f"Unresolved function '{func_name}' — no matching .hu file found",
                "line": i + 1,
                "col": max(0, col),
                "source": "lamia-semantic",
            })
            continue

        hu_fn = hu_registry[func_name]
        provided_kwargs = _extract_kwarg_names(m.group(2))
        required = hu_fn.params - frozenset(hu_fn.defaults.keys())
        missing = required - provided_kwargs
        if missing:
            col = line.find(func_name)
            diagnostics.append({
                "severity": "error",
                "message": (
                    f"{func_name}() missing required "
                    f"{'argument' if len(missing) == 1 else 'arguments'}: "
                    f"{', '.join(sorted(missing))}"
                ),
                "line": i + 1,
                "col": max(0, col),
                "source": "lamia-semantic",
            })

    return diagnostics


def _extract_kwarg_names(args_str: str) -> Set[str]:
    """Extract keyword argument names from a function call args string."""
    names: Set[str] = set()
    if not args_str.strip():
        return names
    depth = 0
    current = ""
    in_str: Optional[str] = None
    for ch in args_str:
        if in_str:
            current += ch
            if ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'"):
            in_str = ch
            current += ch
            continue
        if ch in ("(", "[", "{"):
            depth += 1
            current += ch
            continue
        if ch in (")", "]", "}"):
            depth -= 1
            current += ch
            continue
        if ch == "," and depth == 0:
            _add_kwarg(current, names)
            current = ""
            continue
        current += ch
    if current.strip():
        _add_kwarg(current, names)
    return names


def _add_kwarg(part: str, names: Set[str]) -> None:
    eq_idx = part.find("=")
    if eq_idx > 0:
        key = part[:eq_idx].strip()
        if key.isidentifier():
            names.add(key)


_PYTHON_BUILTINS = frozenset([
    "print", "len", "range", "str", "int", "float", "list", "dict", "set",
    "tuple", "type", "isinstance", "open", "super", "enumerate", "zip", "map",
    "filter", "sorted", "reversed", "any", "all", "min", "max", "sum", "abs",
    "round", "getattr", "setattr", "delattr", "vars", "dir", "id", "hash",
    "input", "format", "repr", "bool", "bytes", "bytearray", "memoryview",
    "object", "staticmethod", "classmethod", "property",
])


def _syntax_error_to_diagnostic(e: SyntaxError, source_label: str) -> dict:
    return {
        "severity": "error",
        "message": e.msg if e.msg else str(e),
        "line": e.lineno if e.lineno else 1,
        "col": (e.offset - 1) if e.offset else 0,
        "source": source_label,
    }


def handle_inspect():
    """Handle ``lamia inspect <file...> [--json]``.

    Supports single or multiple files.  When multiple files are given with
    --json, returns ``{"results": {"path": {"executable": ..., "steps": [...]}, ...}}``.
    Files that don't exist or have syntax errors are individually marked
    non-executable — they never abort the whole batch.
    """
    arg_parser = argparse.ArgumentParser(
        prog="lamia inspect",
        description="Inspect .lm files for IDE integration",
    )
    arg_parser.add_argument("files", nargs="+", help="Lamia .lm file(s) to inspect")
    arg_parser.add_argument("--json", action="store_true", help="JSON output")
    args = arg_parser.parse_args(sys.argv[2:])

    if len(args.files) == 1:
        _inspect_single(args.files[0], args.json)
    else:
        _inspect_batch(args.files, args.json)


def _inspect_single(file_path: str, as_json: bool) -> None:
    if not os.path.isfile(file_path):
        if as_json:
            print(json.dumps({"error": f"file not found: {file_path}"}))
        else:
            print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    with open(file_path, "r") as f:
        source = f.read()

    result = _analyze(source, file_path)

    if as_json:
        out: dict = {
            "executable": result.executable,
            "steps": result.steps,
        }
        if result.diagnostics:
            out["diagnostics"] = result.diagnostics
        print(json.dumps(out))
    else:
        status = "executable" if result.executable else "definitions only"
        print(f"{os.path.basename(file_path)}: {status}")
        if result.steps:
            print(f"  steps at lines: {result.steps}")
        for d in result.diagnostics:
            print(f"  {d['severity']}: line {d['line']}: {d['message']}")


def _inspect_batch(file_paths: List[str], as_json: bool) -> None:
    results: dict = {}
    for file_path in file_paths:
        if not os.path.isfile(file_path):
            results[file_path] = {"executable": False, "steps": [], "error": "file not found"}
            continue
        with open(file_path, "r") as f:
            source = f.read()
        result = _analyze(source, file_path)
        entry: dict = {"executable": result.executable, "steps": result.steps}
        if result.diagnostics:
            entry["diagnostics"] = result.diagnostics
        results[file_path] = entry

    if as_json:
        print(json.dumps({"results": results}))
    else:
        for fpath, info in results.items():
            status = "executable" if info["executable"] else "definitions only"
            err = info.get("error")
            if err:
                status = f"ERROR: {err}"
            print(f"{fpath}: {status}")
            for d in info.get("diagnostics", []):
                print(f"  {d['severity']}: line {d['line']}: {d['message']}")
