"""CLI handler for `lamia trigger` commands.

Usage:
    lamia trigger add <script.lm> --remote
    lamia trigger list
    lamia trigger remove <id>
"""

import argparse
import ast
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

    add_parser = subparsers.add_parser(
        "add",
        help="Deploy a triggered script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "The script must contain at least one trigger.* call.\n\n"
            "Examples:\n"
            "  lamia trigger add email_handler.lm --remote\n"
            "  lamia trigger add invoice_processor.lm --remote\n"
        ),
    )
    add_parser.add_argument("script", help="Path to the .lm script file")
    add_parser.add_argument(
        "--remote",
        action="store_true",
        help="Deploy to cloud (requires lamia-lang[cloud]).",
    )

    subparsers.add_parser("list", help="List all deployed triggers")

    remove_parser = subparsers.add_parser("remove", help="Remove a deployed trigger")
    remove_parser.add_argument("id", help="Trigger ID (from 'lamia trigger list')")

    if len(sys.argv) >= 3 and sys.argv[2] == "add" and len(sys.argv) == 3:
        add_parser.print_help()
        sys.exit(2)

    args = parser.parse_args(sys.argv[2:])

    if args.action == "add":
        _handle_add(args)
    elif args.action == "list":
        _handle_list()
    elif args.action == "remove":
        _handle_remove(args)
    else:
        parser.print_help()
        sys.exit(1)


def _handle_add(args: argparse.Namespace) -> None:
    script_path = Path(args.script).resolve()
    if not script_path.exists():
        print(f"Error: script not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    stages = extract_all_triggers(script_path)
    if not stages:
        print(
            f"Error: no trigger.* call found in {script_path.name}.\n"
            "The script must contain at least one trigger call, e.g.:\n"
            "  trigger.email_received(sender, subject, body)",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args.remote:
        print(
            "Error: local triggers are not yet supported.\n"
            "Use --remote to deploy to cloud.",
            file=sys.stderr,
        )
        sys.exit(1)

    name = script_path.stem.replace("_", "-")
    project_root = script_path.parent

    provider = _get_cloud_provider(project_root)

    from lamia_cloud.types import TriggerDeploymentPlan
    plan = TriggerDeploymentPlan(name=name, stages=stages)

    print(f"Deploying trigger: {script_path.name} ({len(stages)} stage(s))...")
    deployment_id = provider.deploy(plan)
    print(f"Deployed: {deployment_id}")


def _handle_list() -> None:
    project_root = Path.cwd()
    provider = _get_cloud_provider(project_root)
    deployments = provider.list_deployments()
    if not deployments:
        print("No triggers deployed.")
        return
    for d in deployments:
        status_str = d.get("last_status", "never run")
        print(f"  [{d['name']}] {d.get('script', '?')}")
        print(f"    event: {d.get('trigger_method', '?')}")
        print(f"    last run: {d.get('last_run', 'never')}  status: {status_str}")
        if d.get("logs_url"):
            print(f"    logs: {d['logs_url']}")
        print()


def _handle_remove(args: argparse.Namespace) -> None:
    name = args.id
    project_root = Path.cwd()
    provider = _get_cloud_provider(project_root)
    provider.undeploy(name)
    print(f"Removed: {name}")


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
