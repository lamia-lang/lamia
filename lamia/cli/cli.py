from ast import Pass
import asyncio
import json
import re
import signal
import sys
import os
from typing import Optional
import argparse
import select
import yaml
import logging
import runpy
import traceback

from lamia import Lamia
from lamia.async_bridge import EventLoopManager
from lamia.errors import (
    MissingAPIKeysError,
    ExternalOperationTransientError,
    ExternalOperationPermanentError,
    ExternalOperationRateLimitError,
    ExternalOperationError,
)
from .scaffold import create_minimal_config, ensure_extensions_folder, update_config_with_extensions, create_env_file, create_config_from_wizard_result
from .init_wizard import run_init_wizard
from .eval_cli import handle_eval
from .cli_styling import setup_cli_logging
from lamia.interpreter.command_types import CommandType
from lamia.interpreter.hybrid_executor import HybridExecutor
from lamia.interpreter.human.parser import parse_hu_file
from lamia.interpreter.human.executor import HuCallable

HYBRID_EXTENSIONS = {'.lm'}
HUMAN_EXTENSIONS = {'.hu'}

logger = logging.getLogger(__name__)

async def interactive_mode(lamia: Lamia):
    """Run Lamia in interactive mode, processing user prompts."""
    logger.info("Lamia Interactive Mode")
    logger.info("Enter your prompts")

    prompt_str = "\n🧟‍♀️ > (SEND=submit, CANCEL=discard, STOP=interrupt, STATS=stats, Command/Ctrl C or EXIT=quit)\n> "

    running_task = None

    # Flag to indicate an immediate command like STATS was executed
    do_stats_command = False

    while True:
        try:
            # Multiline input: keep reading until 'SEND' is entered on a new line
            lines = []
            while True:
                line = input(prompt_str if not lines else "> ")
                # Immediate command: STATS (case-insensitive) without SEND
                if not lines and line.strip().upper() == "STATS":
                    stats = lamia.get_validation_stats()
                    print("\n📊 Validation statistics:")
                    print("----------------------------------------")
                    print(stats)
                    print("----------------------------------------")
                    do_stats_command = True
                    break  # break out of inner input loop
                if line.strip() == "SEND":
                    break
                if line.strip().upper() == "CANCEL":
                    logger.info("Prompt cancelled. Start typing a new prompt.")
                    lines = []
                    # Show the prompt again for a new input
                    continue
                # Immediate exit: only when typed alone before any real content (no SEND needed)
                if not lines and line.strip().lower() in ['exit', 'quit', ':q']:
                    _exit_interactive(running_task, lamia)
                    return
                if line.strip():
                    lines.append(line)
            # If an immediate command like STATS was executed, restart outer loop
            if do_stats_command:
                do_stats_command = False
                continue

            user_input = "\n".join(lines).strip()

            if not user_input:
                logger.info("Prompt is empty. Start typing a new prompt.")
                continue

            # Generate LLM response
            logger.info("\nThinking... 🤔 (type STOP to interrupt)")
            running_task = asyncio.create_task(lamia.run_async(user_input, _full_result=True))
            while not running_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(running_task), timeout=0.2)
                except asyncio.TimeoutError:
                    # Check for STOP command from user
                    if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                        stop_input = sys.stdin.readline().strip()
                        if stop_input.upper() == 'STOP':
                            running_task.cancel()
                            logger.warning("Prompt interrupted by user (STOP). Start typing a new prompt.")
                            break
                        elif stop_input.lower() in ['exit', 'quit', ':q']:
                            _exit_interactive(running_task, lamia)
                            return
            if running_task.done() and not running_task.cancelled():
                result = running_task.result()
                # TODO: use a logger without timestamps, etc
                print("🔮 Response:")
                print("----------------------------------------")
                print(result.result_text)
                print("----------------------------------------")
                
                # Show detailed info for LLM responses
                if result.tracking_context.command_type == CommandType.LLM:
                    if result.tracking_context:
                        print(f"Model: {result.tracking_context.data_provider_name}")
                        
                        # Extract usage from metadata if available
                        if result.tracking_context.metadata and "usage" in result.tracking_context.metadata:
                            usage = result.tracking_context.metadata["usage"]
                            # Format usage similar to the README example
                            usage_parts = []
                            if 'prompt_tokens' in usage:
                                usage_parts.append(f"'prompt_tokens': {usage['prompt_tokens']}")
                            elif 'input_tokens' in usage:
                                usage_parts.append(f"'prompt_tokens': {usage['input_tokens']}")
                            
                            if 'completion_tokens' in usage:
                                usage_parts.append(f"'completion_tokens': {usage['completion_tokens']}")
                            elif 'output_tokens' in usage:
                                usage_parts.append(f"'completion_tokens': {usage['output_tokens']}")
                            
                            if 'total_tokens' in usage:
                                usage_parts.append(f"'total_tokens': {usage['total_tokens']}")
                            
                            if usage_parts:
                                print(f"Tokens used: {{{', '.join(usage_parts)}}}")
                else:
                    print(f"Executed by: {result.tracking_context.command_type}")
        except (KeyboardInterrupt, SystemExit):
            _exit_interactive(running_task, lamia)
            return
        except Exception as e:
            traceback.print_exc()
            logger.error(f"❌ Error: {str(e)}")
            logger.error(traceback.format_exc())
            continue

def _exit_interactive(running_task: 'Optional[asyncio.Task[object]]', lamia: Lamia) -> None:
    """Cancel any in-flight task and shut down cleanly."""
    print("\nGoodbye! 👋")
    if running_task and not running_task.done():
        running_task.cancel()
    _graceful_shutdown(lamia)


def _json_write(obj: dict) -> None:
    """Write a single JSON object as one line to stdout and flush."""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _friendly_error(raw: str) -> str:
    """Convert raw tool errors into user-friendly text without truncation."""
    if "old_text not found" in raw:
        return "Could not apply the edit because the target text was not found in the file."
    if raw.startswith("File not found"):
        return "File does not exist"
    if raw.startswith("Unknown tool"):
        return raw
    if raw.startswith("Error: file not found"):
        return "File does not exist"
    msg = raw
    if msg.startswith("Error: "):
        msg = msg[7:]
    if msg.startswith("Error reading file: "):
        msg = msg[20:]
    if msg.startswith("Error writing file: "):
        msg = msg[20:]
    return msg


def _format_history(messages: list[dict]) -> str:
    """Format pre-compressed conversation messages into a prompt block."""
    if not messages:
        return ""
    parts = []
    for m in messages:
        role = m.get("role", "assistant").capitalize()
        parts.append(f"{role}: {m.get('text', '')}")
    return "\n\n".join(parts)


async def json_mode(lamia: Lamia) -> None:
    """Machine-readable JSON-line protocol for IDE integration.

    Reads one JSON object per line from stdin.  Writes one JSON object per
    line to stdout.  All logging goes to the log file only (console handler
    is suppressed before this function is called).

    Request  : {"text": "user message"} or advanced {"text": "...", "system": "...", "files": ["/path/a.lm", "/path/b.hu"],
                "messages": [{"role": "user", "text": "..."}, {"role": "assistant", "text": "..."}]}
    Response : {"type": "response", "text": "...", "model": "...", "tokens": {...}}
    Error    : {"type": "error", "message": "..."}
    Ready    : {"type": "ready"}  (sent once after startup)
    """
    from lamia.cli.tools import execute_tool, get_tools_system_prompt, reset_file_writes, get_file_writes, tool_progress_label, ToolName

    MAX_TOOL_ROUNDS = 50
    tools_prompt = get_tools_system_prompt()

    _json_write({"type": "ready"})

    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader(limit=10 * 1024 * 1024)
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        try:
            raw = await reader.readline()
        except ValueError as exc:
            _json_write({"type": "error", "message": f"Request too large: {exc}"})
            continue
        if not raw:
            break

        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            _json_write({"type": "error", "message": f"Invalid JSON: {exc}"})
            continue

        user_text = request.get("text", "").strip()
        if not user_text:
            _json_write({"type": "error", "message": "Missing 'text' field"})
            continue

        system_prefix = request.get("system", "")
        if system_prefix:
            system_prefix = system_prefix.rstrip() + "\n\n" + tools_prompt
        else:
            system_prefix = tools_prompt

        raw_messages = request.get("messages", [])
        if raw_messages:
            history_block = _format_history(raw_messages)
            prompt = (
                f"{system_prefix}\n\n"
                f"<conversation_history>\n{history_block}\n</conversation_history>\n\n"
                f"User: {user_text}"
            )
        else:
            prompt = system_prefix + "\n\n" + user_text
        file_paths = request.get("files", [])

        # NOTE: reads files locally — if Lamia moves to a remote server,
        # file contents should be sent in the request JSON instead of paths.
        if file_paths:
            file_sections = []
            for fp in file_paths:
                try:
                    with open(fp, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    file_sections.append(f"<file path=\"{fp}\">\n{content}\n</file>")
                except Exception as read_err:
                    logger.warning("Could not read attached file %s: %s", fp, read_err)
            if file_sections:
                prompt = prompt + "\n\n<attached_files>\n" + "\n".join(file_sections) + "\n</attached_files>"

        try:
            response_to_caller_text = "" # responce of the execution to the m2m callee e.g. to The Lamia IDE
            model_name = None
            total_tokens: dict = {}
            reset_file_writes()

            MAX_SAME_FILE_WRITES = 3

            write_counts: dict[str, int] = {}

            for _round in range(MAX_TOOL_ROUNDS + 1):
                result = await lamia.run_async(prompt, _full_result=True)

                ctx = result.tracking_context
                if ctx and ctx.data_provider_name:
                    model_name = ctx.data_provider_name
                if ctx and ctx.metadata and "usage" in ctx.metadata:
                    usage = ctx.metadata["usage"]
                    inp = usage.get("prompt_tokens") or usage.get("input_tokens", 0)
                    out = usage.get("completion_tokens") or usage.get("output_tokens", 0)
                    total_tokens["input"] = total_tokens.get("input", 0) + inp
                    total_tokens["output"] = total_tokens.get("output", 0) + out
                    total_tokens["total"] = total_tokens["input"] + total_tokens["output"]

                text = result.result_text or ""
                tool_calls = _extract_tool_calls(text)

                if not tool_calls:
                    if _detect_malformed_tool_call(text) and _round < MAX_TOOL_ROUNDS:
                        logger.debug("Malformed tool call detected, sending correction")
                        prompt = (
                            f"{prompt}\n\nAssistant: {text}\n\n"
                            f"System: {TOOL_FORMAT_CORRECTION}"
                        )
                        continue
                    response_to_caller_text = _strip_tool_calls(text)
                    break

                tool_result_entries: list[dict[str, object]] = []
                should_break = False
                for tool_call in tool_calls:
                    tool_name = tool_call.get("tool", "")
                    tool_args = tool_call.get("args", {})
                    logger.debug(f"Tool call: {tool_name}({tool_args})")

                    if tool_name in (ToolName.WRITE_FILE, ToolName.PATCH_FILE):
                        target = tool_args.get("path", "")
                        write_counts[target] = write_counts.get(target, 0) + 1
                        if write_counts[target] > MAX_SAME_FILE_WRITES:
                            logger.warning(
                                "Loop detected: %s written %d times, breaking",
                                target, write_counts[target],
                            )
                            response_to_caller_text = _strip_tool_calls(text)
                            should_break = True
                            break

                    _json_write({
                        "type": "tool_use",
                        "tool": tool_name,
                        "args": tool_args,
                        "label": tool_progress_label(tool_name, tool_args),
                    })
                    tool_result, tool_success = execute_tool(tool_name, tool_args, os.getcwd(), lamia=lamia)
                    evt: dict = {
                        "type": "tool_result",
                        "tool": tool_name,
                        "success": tool_success,
                    }
                    if not tool_success:
                        evt["error"] = _friendly_error(tool_result)
                    _json_write(evt)
                    tool_result_entries.append(
                        _build_tool_result_entry(tool_name, tool_args, tool_result)
                    )

                if should_break:
                    break

                if _round < MAX_TOOL_ROUNDS:
                    if tool_result_entries:
                        tool_results_json = json.dumps(
                            {"tool_results": tool_result_entries},
                            ensure_ascii=False,
                        )
                        prompt = (
                            f"{prompt}\n\n"
                            f"Tool results JSON:\n{tool_results_json}\n\n"
                            f"Continue your response to the user based on these tool results."
                        )
                    else:
                        # Should not happen, but just in case
                        break

                    continue

                response_to_caller_text = _strip_tool_calls(text)
                break

            response: dict = {"type": "response", "text": response_to_caller_text}
            if model_name:
                response["model"] = model_name
            if total_tokens:
                response["tokens"] = total_tokens
            file_writes = get_file_writes()
            if file_writes:
                response["files"] = file_writes

            _json_write(response)

        except MissingAPIKeysError as exc:
            _json_write({"type": "error", "message": str(exc)})
        except (ExternalOperationTransientError,
                ExternalOperationPermanentError,
                ExternalOperationRateLimitError) as exc:
            _json_write({"type": "error", "message": str(exc)})
        except Exception as exc:
            logger.error(f"json_mode error: {exc}", exc_info=True)
            _json_write({"type": "error", "message": str(exc)})


def _extract_tool_calls(text: str) -> list[dict]:
    """Extract all tool calls from LLM response text.

    Supports two formats:
    - JSON:  {"tool": "name", "args": {"k": "v"}}
    - XML:   <invoke ...><tool_name>name</tool_name><parameter name="k">v</parameter></invoke>
    """
    calls: list[dict] = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
            if "tool" in obj and isinstance(obj.get("tool"), str):
                calls.append(obj)
        except json.JSONDecodeError:
            continue

    for invoke_match in re.finditer(r"<invoke\b[^>]*>(.*?)</invoke>", text, re.DOTALL):
        block = invoke_match.group(1)
        name_match = re.search(r"<tool_name>\s*(\w+)\s*</tool_name>", block)
        if name_match:
            args: dict = {}
            for pm in re.finditer(
                r'<parameter\s+name="(\w+)">(.*?)</parameter>', block, re.DOTALL
            ):
                args[pm.group(1)] = pm.group(2)
            calls.append({"tool": name_match.group(1), "args": args})

    return calls


_MALFORMED_TOOL_PATTERNS = [
    re.compile(r"<function_calls>", re.IGNORECASE),
    re.compile(r"<tool_call>", re.IGNORECASE),
    re.compile(r"<tool_use>", re.IGNORECASE),
    re.compile(r'<invoke\s+name\s*=\s*["\']', re.IGNORECASE),
    re.compile(r"```tool", re.IGNORECASE),
    re.compile(r"```json\s*\n\s*\{\s*\"tool", re.IGNORECASE),
]

_MALFORMED_JSON_KEYS = [
    ("name", "input"),       # Anthropic native tool_use
    ("function", "arguments"),  # OpenAI function_call
    ("name", "parameters"),  # Generic
    ("tool_name", "args"),   # Close but wrong key
    ("tool_name", "parameters"),
]


def _detect_malformed_tool_call(text: str) -> bool:
    """Detect if the LLM attempted a tool call in an unsupported format.

    Casts a wide net: XML wrappers (function_calls, tool_call, tool_use,
    invoke-with-name-attr), JSON with wrong keys (name+input, function+arguments),
    and fenced code blocks containing tool-like JSON.
    """
    for pattern in _MALFORMED_TOOL_PATTERNS:
        if pattern.search(text):
            return True

    for line in text.strip().split("\n"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            for key_a, key_b in _MALFORMED_JSON_KEYS:
                if key_a in obj and key_b in obj:
                    return True
        except json.JSONDecodeError:
            continue

    return False


TOOL_FORMAT_CORRECTION = (
    "Your tool call was NOT in the correct format and could not be executed. "
    "Do NOT use XML tags like <function_calls>, <invoke>, <tool_call>, or <tool_use>. "
    "Do NOT use JSON keys like \"name\"/\"input\" or \"function\"/\"arguments\".\n\n"
    "You MUST use this EXACT JSON format on its own line:\n"
    '{"tool": "tool_name", "args": {"param": "value"}}\n\n'
    "Retry your tool call now using the correct format."
)


def _strip_tool_calls(text: str) -> str:
    """Remove tool-call JSON and XML blocks from LLM response text."""
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("{"):
            try:
                obj = json.loads(stripped)
                if not isinstance(obj, dict):
                    lines.append(line)
                    continue
                if "tool" in obj and isinstance(obj.get("tool"), str):
                    continue
                for key_a, key_b in _MALFORMED_JSON_KEYS:
                    if key_a in obj and key_b in obj:
                        break
                else:
                    lines.append(line)
                    continue
            except json.JSONDecodeError:
                lines.append(line)
                continue
        else:
            lines.append(line)
    result = "\n".join(lines)

    result = re.sub(r"<function_calls>.*?</function_calls>", "", result, flags=re.DOTALL)
    result = re.sub(r"<tool_call>.*?</tool_call>", "", result, flags=re.DOTALL)
    result = re.sub(r"<tool_use>.*?</tool_use>", "", result, flags=re.DOTALL)
    result = re.sub(r"<tool_result>.*?</tool_result>", "", result, flags=re.DOTALL)
    result = re.sub(r"<invoke\b[^>]*>.*?</invoke>", "", result, flags=re.DOTALL)
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def _build_tool_result_entry(tool_name: str, tool_args: dict, tool_result: str) -> dict[str, object]:
    """Build a single tool result entry for the next LLM round."""
    return {
        "tool": tool_name,
        "args": tool_args,
        "result": tool_result,
    }


def _tool_result_success(tool_result: str) -> bool:
    """Classify tool result status for UI progress rendering."""
    return not tool_result.startswith("Error:")


def _open_ide(folder: str) -> None:
    """Open Lamia Studio IDE at *folder*, reading the app path from ~/.lamia/ide-path.txt."""
    import platform
    import subprocess

    ide_path_file = os.path.join(os.path.expanduser("~"), ".lamia", "ide-path.txt")
    ide_path = None
    if os.path.isfile(ide_path_file):
        ide_path = open(ide_path_file).read().strip()
        if not os.path.exists(ide_path):
            ide_path = None

    if ide_path is None:
        well_known = [
            os.path.expanduser("~/Applications/Lamia Studio.app"),
            "/Applications/Lamia Studio.app",
        ]
        for p in well_known:
            if os.path.exists(p):
                ide_path = p
                break

    if ide_path is None:
        print("Lamia Studio is not installed or could not be found.")
        print("Download it from: https://github.com/LamiaOrg/lamia-ide/releases")
        sys.exit(1)

    abs_folder = os.path.abspath(folder)
    system = platform.system()
    if system == "Darwin":
        subprocess.Popen(["open", "-a", ide_path, abs_folder])
    elif system == "Windows":
        subprocess.Popen([ide_path, abs_folder])
    else:
        subprocess.Popen([ide_path, abs_folder])


def main():
    """Main entry point for the Lamia CLI."""
    _install_sigint_handler()

    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        from lamia._version import __version__
        print(f"lamia {__version__}")
        return

    if len(sys.argv) > 1 and sys.argv[1] == ".":
        _open_ide(sys.argv[2] if len(sys.argv) > 2 else ".")
        return

    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        _open_ide(sys.argv[1])
        return

    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        from .debug_runner import handle_debug
        handle_debug()
        return

    if len(sys.argv) > 1 and sys.argv[1] == "init":
        parser = argparse.ArgumentParser(
            description="Lamia CLI",
            epilog="""
            Subcommands:
            init        Initialize a new Lamia project (see 'init --help' for options like --with-extensions)

            For help on a subcommand, run:
            lamia <subcommand> --help
            """
        )
        subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommands (use '<subcommand> --help' for details)")
        init_parser = subparsers.add_parser("init", help="Initialize a new Lamia project in the current directory")
        init_parser.add_argument("--with-extensions", action="store_true", help="Also scaffold the extensions folder structure (adapters, validators)")
        parser.add_argument('--log-level', default='INFO', help='Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
        args = parser.parse_args()
        if args.command == "init":
            config_path = os.path.join(os.getcwd(), "config.yaml")

            # Check for existing config (re-init support)
            if os.path.exists(config_path):
                print("config.yaml already exists in this directory.")
                raw = input("Overwrite with a new configuration? [y/N]: ").strip().lower()
                if raw not in ("y", "yes"):
                    print("Init cancelled.")
                    return

            project_dir = os.getcwd()

            # Run the interactive wizard (handles API key saving internally)
            wizard_result = run_init_wizard(project_dir=project_dir, with_extensions=args.with_extensions)

            # Generate config.yaml from wizard result
            create_config_from_wizard_result(config_path, wizard_result)
            print("Created config.yaml")

            # Handle extensions folder
            if args.with_extensions:
                ext_path = ensure_extensions_folder(project_dir)
                update_config_with_extensions(config_path)
                print(f"Extensions folder scaffolded at: {ext_path}")

            # TODO: create_minimal_config is kept for programmatic/test use;
            #       the wizard path above is the primary init flow.

            print("\nDone! Run 'lamia <file.lm>' or 'lamia' for interactive mode.")
            return
        return
    elif len(sys.argv) > 1 and sys.argv[1] == "eval":
        handle_eval()
        return
    else:
        parser = argparse.ArgumentParser(
            description="Lamia CLI",
            epilog="""
            For help on a subcommand, run:
            lamia <subcommand> --help
            """
        )
        
        # Check if first arg is 'cache' subcommand
        if len(sys.argv) > 1 and sys.argv[1] == 'cache':
            # Handle cache subcommand
            from .cache_cli import CacheCLI
            import argparse as cache_argparse
            
            cache_parser = cache_argparse.ArgumentParser(
                description='Manage Lamia selector resolution cache',
                prog='lamia cache'
            )
            cache_subparsers = cache_parser.add_subparsers(dest='cache_command', help='Cache command to execute')
            
            # List command
            list_parser = cache_subparsers.add_parser('list', help='List cached selectors')
            list_parser.add_argument('--url', help='Filter by URL')
            list_parser.add_argument('--description', help='Filter by description')
            
            # Add command  
            add_parser = cache_subparsers.add_parser('add', help='Add a selector resolution to cache')
            add_parser.add_argument('original', help='Original selector that failed')
            add_parser.add_argument('resolved', help='Working selector to use instead')
            add_parser.add_argument('url', help='URL where this resolution applies')
            add_parser.add_argument('--context', help='Optional parent context for scoped cache')
            
            # Clear command
            clear_parser = cache_subparsers.add_parser('clear', help='Clear cache entries')
            clear_parser.add_argument('--description', help='Clear entries matching description')
            clear_parser.add_argument('--url', help='Clear entries matching URL')
            clear_parser.add_argument('--all', action='store_true', help='Clear entire cache')
            
            # Stats command
            stats_parser = cache_subparsers.add_parser('stats', help='Show cache statistics')
            
            # Parse cache args (skip 'cache' in sys.argv)
            cache_args = cache_parser.parse_args(sys.argv[2:])
            
            # Execute cache command
            cli = CacheCLI()
            if cache_args.cache_command == 'list':
                cli.list_cache(url_filter=cache_args.url, description_filter=cache_args.description)
            elif cache_args.cache_command == 'add':
                cli.add_selector(
                    original_selector=cache_args.original,
                    resolved_selector=cache_args.resolved,
                    url=cache_args.url,
                    parent_context=cache_args.context
                )
            elif cache_args.cache_command == 'clear':
                if not (cache_args.description or cache_args.url or cache_args.all):
                    print("Error: Must specify --description, --url, or --all", file=sys.stderr)
                    sys.exit(1)
                cli.clear_cache(description=cache_args.description, url=cache_args.url, all_entries=cache_args.all)
            elif cache_args.cache_command == 'stats':
                cli.stats()
            else:
                cache_parser.print_help()
            
            sys.exit(0)
        
        # Regular CLI arguments
        parser.add_argument('filename', nargs='?', help='Lamia script file to run (if not provided, runs in interactive mode)')
        parser.add_argument('--file', '-f', type=str, help='Lamia script file to run (if not provided, runs in interactive mode)')
        parser.add_argument('--config', '-c', type=str, help='Path to config file (optional)')
        parser.add_argument('--log-level', default='INFO', help='Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
        #parser.add_argument('--verbose', '-v', action='store_true', help='Show all Lamia logs on console (default: only warnings/errors)')
        parser.add_argument('--log-file', type=str, help='Custom path for the Lamia log file (default: .lamia/lamia.log)')
        parser.add_argument('--no-cache', action='store_true', help='Disable selector resolution cache (forces fresh resolution)')
        parser.add_argument('--json', action='store_true', help='Machine-readable JSON-line mode for IDE/tool integration')
        args = parser.parse_args()

    json_flag = getattr(args, 'json', False)

    setup_cli_logging(
        level=args.log_level.upper(),
        verbose=not json_flag,
        log_file=args.log_file,
    )

    if json_flag:
        lamia_console = logging.getLogger("lamia")
        for hdlr in lamia_console.handlers[:]:
            if isinstance(hdlr, logging.StreamHandler) and hdlr.stream in (sys.stderr, sys.stdout):
                lamia_console.removeHandler(hdlr)

    prompt_file = args.filename or args.file
    config_path = args.config

    config_dict = None
    if config_path:
        logger.debug(f"Using configuration from: {config_path}")
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)
    else:
        from lamia.project import find_config_file
        discovered = find_config_file(prompt_file)
        if discovered:
            logger.debug(f"Using configuration from: {discovered}")
            with open(discovered, 'r') as f:
                config_dict = yaml.safe_load(f)
        else:
            from pathlib import Path
            search_start = Path(prompt_file).resolve().parent if prompt_file else Path.cwd()
            logger.error(
                f"fatal: no config.yaml found (searched upwards from {search_start}).\n"
                f"Place a config.yaml in your project root, or pass --config <path>.\n"
                f"Run 'lamia init' to create one."
            )
            sys.exit(1)

    # Note: Lazy loading is now handled by HybridExecutor for .hu files
    # Python files still need sys.path management for regular execution

    lamia = None
    try:
        # Handle --no-cache flag
        if args.no_cache:
            logger.debug("Cache disabled via --no-cache flag")
            if config_dict is None:
                config_dict = {}
            if 'web' not in config_dict:
                config_dict['web'] = {}
            if 'selector_resolution' not in config_dict['web']:
                config_dict['web']['selector_resolution'] = {}
            config_dict['web']['selector_resolution']['cache_enabled'] = False
        
        lamia = Lamia.from_config(config_dict)
        
        if prompt_file:
            # File execution - no async needed
            file_ext = os.path.splitext(prompt_file)[1].lower()
            
            if file_ext in HUMAN_EXTENSIONS:
                # TODO: Support .hu files from the cli
                pass
            elif file_ext in HYBRID_EXTENSIONS:
                try:
                    executor = HybridExecutor(lamia)
                    executor.execute_file(prompt_file, enable_lazy_dependency_loading=True)
                    _graceful_shutdown(lamia, 0)
                except ExternalOperationTransientError as e:
                    _log_external_error("❌ External operation failed after all retries", e)
                    _graceful_shutdown(lamia, 1)
                except ExternalOperationPermanentError as e:
                    _log_external_error("❌ Permanent failure", e)
                    _graceful_shutdown(lamia, 1)
                except ExternalOperationRateLimitError as e:
                    _log_external_error("❌ Rate limit exceeded", e)
                    _graceful_shutdown(lamia, 1)
                except SyntaxError as e:
                    logger.error(f"❌ Syntax error in hybrid file: {e}")
                    logger.error(f"Line {e.lineno}: {e.text}")
                    logger.debug(traceback.format_exc())
                    _graceful_shutdown(lamia, 1)
                except ImportError as e:
                    logger.error(f"❌ Missing dependency: {e}")
                    logger.debug(traceback.format_exc())
                    _graceful_shutdown(lamia, 1)
                except MissingAPIKeysError as e:
                    logger.error(f"❌ {e}")
                    _graceful_shutdown(lamia, 1)
                except KeyboardInterrupt:
                    _graceful_shutdown(lamia)
                except Exception as e:
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['parse', 'syntax', 'transform', 'ast']):
                        logger.error(f"❌ Error processing hybrid syntax file: {e}")
                    else:
                        logger.error(f"❌ Runtime error: {e}")
                    logger.debug(traceback.format_exc())
                    _graceful_shutdown(lamia, 1)
            else:
                # Regular Python file — inject Lamia builtins so types like
                # HTML, web, InputType are available without explicit imports.
                try:
                    runpy.run_path(prompt_file, run_name="__main__")
                    _graceful_shutdown(lamia, 0)
                except MissingAPIKeysError as e:
                    logger.error(f"❌ {e}")
                    _graceful_shutdown(lamia, 1)
                except KeyboardInterrupt:
                    _graceful_shutdown(lamia)
                except Exception as e:
                    logger.error(f"❌ Error executing script: {e}")
                    logger.debug(traceback.format_exc())
                    _graceful_shutdown(lamia, 1)
        elif json_flag:
            async def run_json():
                await json_mode(lamia)

            asyncio.run(run_json())
        else:
            async def run_interactive():
                await interactive_mode(lamia)

            asyncio.run(run_interactive())
            
    except MissingAPIKeysError as e:
        logger.error(f"❌ Missing API Keys: {str(e)}")
        logger.error("Please check your .env file or config.yaml for required API keys.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1)
    except KeyboardInterrupt:
        _graceful_shutdown(lamia)


def _install_sigint_handler() -> None:
    """Install a SIGINT handler that immediately silences loggers and exits.

    When Ctrl+C is pressed the OS sends SIGINT to the whole process group,
    killing ChromeDriver instantly.  In-flight Selenium calls then fail and
    urllib3 retries each one, flooding the console with warnings.
    Raising KeyboardInterrupt from the handler is not enough because asyncio
    absorbs it and the loop continues processing fields against a dead browser.
    Instead we mute every noisy logger and terminate the process directly.
    """
    def _handler(signum: int, frame: object) -> None:
        logging.getLogger("urllib3").setLevel(logging.CRITICAL)
        logging.getLogger("selenium").setLevel(logging.CRITICAL)
        logging.getLogger("lamia").setLevel(logging.CRITICAL)
        print("\nShutting down...", flush=True)
        os._exit(0)

    signal.signal(signal.SIGINT, _handler)


def _graceful_shutdown(lamia_instance: 'Optional[Lamia]', exit_code: int = 0) -> None:
    """Clean up resources and terminate the process.

    Uses os._exit() to bypass asyncio's loop-teardown which would otherwise
    block waiting for cancelled tasks to drain.
    """
    if lamia_instance is not None:
        try:
            EventLoopManager.run_coroutine(lamia_instance._engine.cleanup())
        except Exception:
            pass
    EventLoopManager.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)


def _log_external_error(prefix: str, exc: Exception) -> None:
    """Log user-facing external errors without stack traces unless debugging."""
    logger.error(f"{prefix}: {exc}")
    if not isinstance(exc, ExternalOperationError):
        logger.debug(traceback.format_exc())

if __name__ == "__main__":
    main() 