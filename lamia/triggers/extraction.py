"""Parse a Lamia script and extract its trigger stages.

Kept out of ``lamia.triggers.cli`` so that lightweight paths (like a normal
``.lm`` file execution that has no triggers) don't pull in the trigger CLI
handlers and their provider dependencies.
"""

import ast
from pathlib import Path

from lamia.triggers.types import TriggerStage


def extract_all_triggers(script_path: Path) -> list:
    """Find all trigger.* calls in script, split into stages.

    Returns a list of lamia.triggers.types.TriggerStage.
    """
    source = script_path.read_text()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    lines = source.splitlines(keepends=False)
    trigger_positions: list[dict] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not isinstance(call.func, ast.Attribute):
            continue
        if not isinstance(call.func.value, ast.Name):
            continue
        if call.func.value.id != "trigger":
            continue

        method_name = call.func.attr
        config_params = _extract_config_params(call)
        output_bindings = _extract_output_bindings(call)

        trigger_positions.append({
            "method": method_name,
            "config": config_params,
            "bindings": output_bindings,
            "lineno": node.lineno,
        })

    if not trigger_positions:
        return []

    trigger_positions.sort(key=lambda t: t["lineno"])

    stages: list[TriggerStage] = []
    for i, trig in enumerate(trigger_positions):
        start_line = trig["lineno"]
        if i + 1 < len(trigger_positions):
            end_line = trigger_positions[i + 1]["lineno"] - 1
        else:
            end_line = len(lines)
        stage_source = "\n".join(lines[start_line:end_line])
        stages.append(TriggerStage(
            stage_index=i,
            trigger_method=trig["method"],
            trigger_config=trig["config"],
            output_bindings=trig["bindings"],
            script_source=stage_source,
        ))

    return stages


def _extract_config_params(call: ast.Call) -> dict:
    """Extract string-literal keyword arguments (config params)."""
    params: dict = {}
    for kw in call.keywords:
        if kw.arg and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            params[kw.arg] = kw.value.value
    return params


def _extract_output_bindings(call: ast.Call) -> list[str]:
    """Extract bare name arguments (output bindings)."""
    bindings: list[str] = []
    for arg in call.args:
        if isinstance(arg, ast.Name):
            bindings.append(arg.id)
    return bindings
