"""Minimal Docker-side runner for FunctionalValidator.

Executes a single user function from a mounted Python file and returns a JSON
result so the host process can validate outputs safely.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from types import FunctionType


def _is_user_function(name: str, value: object) -> bool:
    return (
        isinstance(value, FunctionType)
        and not name.startswith("__")
        and not name.endswith("Error")
        and name not in {"StopIteration"}
    )


def _load_single_function(file_path: Path) -> FunctionType:
    namespace: dict[str, object] = {}
    code = file_path.read_text(encoding="utf-8")
    exec(compile(code, str(file_path), "exec"), namespace, namespace)

    functions = [value for name, value in namespace.items() if _is_user_function(name, value)]
    if not functions:
        raise ValueError("No function found in the response")
    if len(functions) > 1:
        names = [name for name, value in namespace.items() if _is_user_function(name, value)]
        raise ValueError(
            f"Multiple functions found in response: {', '.join(names)}. Please provide only one function"
        )
    return functions[0]


def main() -> int:
    if len(sys.argv) != 3:
        print(json.dumps({"success": False, "result": None, "error": "Usage: docker_runner.py <func.py> <repr(tuple)>"}))
        return 2

    func_path = Path(sys.argv[1])
    test_inputs = ast.literal_eval(sys.argv[2])

    try:
        func = _load_single_function(func_path)
        result = func(*test_inputs)
        print(json.dumps({"success": True, "result": result, "error": None}))
        return 0
    except Exception as exc:  # noqa: BLE001 - propagate precise error to validator
        print(json.dumps({"success": False, "result": None, "error": f"{type(exc).__name__}: {exc}"}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
