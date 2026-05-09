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
import sys
import os
from typing import List, Tuple

from lamia.interpreter.hybrid_syntax_parser import HybridSyntaxParser


_NON_EXEC_TYPES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Import,
    ast.ImportFrom,
)


def has_top_level_steps(source: str) -> bool:
    """Public API: does this source have executable steps?"""
    executable, _ = _analyze(source)
    return executable


def get_executable_lines(source: str) -> List[int]:
    """Public API: which original source lines are executable steps?"""
    _, lines = _analyze(source)
    return lines


def _analyze(source: str) -> Tuple[bool, List[int]]:
    """Transform via Lamia parser, then detect steps via AST."""
    parser = HybridSyntaxParser()
    try:
        transformed, source_map = parser.transform_with_source_map(source)
    except (SyntaxError, TypeError, ValueError):
        return False, []

    try:
        tree = ast.parse(transformed)
    except SyntaxError:
        return False, []

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
    return len(deduped) > 0, deduped


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

    executable, step_lines = _analyze(source)

    if as_json:
        print(json.dumps({
            "executable": executable,
            "steps": step_lines,
        }))
    else:
        status = "executable" if executable else "definitions only"
        print(f"{os.path.basename(file_path)}: {status}")
        if step_lines:
            print(f"  steps at lines: {step_lines}")


def _inspect_batch(file_paths: List[str], as_json: bool) -> None:
    results: dict = {}
    for file_path in file_paths:
        if not os.path.isfile(file_path):
            results[file_path] = {"executable": False, "steps": [], "error": "file not found"}
            continue
        with open(file_path, "r") as f:
            source = f.read()
        executable, step_lines = _analyze(source)
        results[file_path] = {"executable": executable, "steps": step_lines}

    if as_json:
        print(json.dumps({"results": results}))
    else:
        for path, info in results.items():
            status = "executable" if info["executable"] else "definitions only"
            err = info.get("error")
            if err:
                status = f"ERROR: {err}"
            print(f"{path}: {status}")
