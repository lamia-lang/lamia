"""CLI handler for `lamia trigger` commands.

Usage:
    lamia trigger list [--verbose]
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Optional


def handle_trigger() -> None:
    """Entry point for `lamia trigger` subcommand."""
    parser = argparse.ArgumentParser(
        description="Manage event-driven Lamia script triggers",
        prog="lamia trigger",
    )
    subparsers = parser.add_subparsers(dest="action")

    list_parser = subparsers.add_parser("list", help="List all deployed triggers")
    list_parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show details of failed events",
    )

    args = parser.parse_args(sys.argv[2:])

    if args.action == "list":
        _handle_list(verbose=args.verbose)
    else:
        parser.print_help()
        sys.exit(1)


def _handle_list(verbose: bool = False) -> None:
    project_root = Path.cwd()
    provider = _get_cloud_provider(project_root)
    deployments = provider.list_deployments()
    if not deployments:
        print("No triggers deployed.")
        return
    for d in deployments:
        status_str = d.get("last_status", "never run")
        failed_count = d.get("failed_event_count", 0)
        print(f"  [{d['name']}] {d.get('script', '?')}")
        print(f"    event: {d.get('trigger_method', '?')}")
        print(f"    mode: {d.get('mode', 'reactive')}")
        print(f"    last run: {d.get('last_run', 'never')}  status: {status_str}")
        if failed_count > 0:
            print(f"    failed events: {failed_count}")
            if verbose:
                events = provider.get_failed_events(d["name"])
                for i, evt in enumerate(events, 1):
                    ts = evt.get("timestamp", "?")
                    payload = evt.get("payload", {})
                    print(f"      #{i} [{ts}]")
                    print(f"         {json.dumps(payload, indent=None, ensure_ascii=False)}")
        if d.get("logs_url"):
            print(f"    logs: {d['logs_url']}")
        print()


def _get_cloud_provider(project_root: Path):
    """Load cloud config and return the trigger provider."""
    try:
        from lamia_cloud.gcp.trigger_provider import GCPTriggerProvider
    except ImportError:
        print(
            "Error: lamia-cloud not installed. Install with: pip install \"lamia-lang[cloud]\"",
            file=sys.stderr,
        )
        sys.exit(1)

    import yaml
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        config_path = project_root / "config.yml"

    cloud_cfg: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            full_config = yaml.safe_load(f) or {}
        cloud_cfg = full_config.get("cloud", {})

    if not cloud_cfg.get("project_id"):
        print(
            "Error: cloud.project_id not found in config.yaml.\n"
            "Add:\n  cloud:\n    project_id: your-gcp-project",
            file=sys.stderr,
        )
        sys.exit(1)

    return GCPTriggerProvider.from_config(cloud_cfg)


def extract_all_triggers(script_path: Path) -> list:
    """Find all trigger.* calls in script, split into stages.

    Returns list of TriggerStage-compatible dicts (stage_index, trigger_method,
    trigger_config, output_bindings, script_source).
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

    from lamia_cloud.types import TriggerStage
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
