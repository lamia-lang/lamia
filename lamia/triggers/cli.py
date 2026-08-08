"""CLI handler for `lamia trigger` commands.

Usage:
    lamia trigger list [--verbose]
    lamia trigger logs <id>
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from lamia.triggers.local.provider import LocalTriggerProvider


def handle_trigger() -> None:
    """Entry point for `lamia trigger` subcommand."""
    parser = argparse.ArgumentParser(
        description="Manage event-driven Lamia script triggers",
        prog="lamia trigger",
    )
    subparsers = parser.add_subparsers(dest="action")

    list_parser = subparsers.add_parser("list", help="List all active triggers (local + cloud)")
    list_parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show details of failed events",
    )

    logs_parser = subparsers.add_parser("logs", help="View execution logs for a trigger")
    logs_parser.add_argument("id", help="Trigger id (from 'lamia trigger list')")

    args = parser.parse_args(sys.argv[2:])

    if args.action == "list":
        _handle_list(verbose=args.verbose)
    elif args.action == "logs":
        _handle_logs(args)
    else:
        parser.print_help()
        sys.exit(1)


def _handle_list(verbose: bool = False) -> None:
    """List all triggers: local + cloud (if available)."""
    local_provider = LocalTriggerProvider()
    local_deployments = local_provider.list_deployments()

    cloud_deployments = _try_cloud_list()

    all_deployments = local_deployments + cloud_deployments

    if not all_deployments:
        print("No triggers active.")
        return

    for d in all_deployments:
        location = d.get("location", "cloud")
        status_str = d.get("last_status", "never run")
        failed_count = d.get("failed_event_count", 0)
        active_execs = d.get("active_executions", 0)
        print(f"  [{d['name']}] {d.get('script', '?')} ({location})")
        print(f"    event: {d.get('trigger_method', '?')}")
        print(f"    mode: {d.get('mode', 'reactive')}")
        print(f"    last run: {d.get('last_run', 'never')}  status: {status_str}")
        if verbose and active_execs > 0:
            print(f"    active executions: {active_execs}")
        if failed_count > 0:
            print(f"    failed events: {failed_count}")
            if verbose:
                events = _get_failed_events_for(d["name"], location)
                for i, evt in enumerate(events, 1):
                    ts = evt.get("timestamp", "?")
                    payload = evt.get("payload", {})
                    print(f"      #{i} [{ts}]")
                    print(f"         {json.dumps(payload, indent=None, ensure_ascii=False)}")
        if d.get("logs_url"):
            print(f"    logs: {d['logs_url']}")
        print()


def _handle_logs(args: argparse.Namespace) -> None:
    provider = _get_cloud_provider(Path.cwd())
    try:
        logs = provider.fetch_logs(args.id)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if logs.get("stdout"):
        print(logs["stdout"], end="")
    if logs.get("stderr"):
        print(logs["stderr"], file=sys.stderr, end="")
    if logs.get("logs_url"):
        print(f"\nLogs: {logs['logs_url']}")


def _get_cloud_provider(project_root: Path):
    """Load cloud config and return the trigger provider."""
    try:
        from lamia_cloud.gcp.trigger_provider import GCPTriggerProvider
    except ImportError:
        return None

    import yaml
    project_root = Path.cwd()
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        config_path = project_root / "config.yml"

    cloud_cfg: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            full_config = yaml.safe_load(f) or {}
        cloud_cfg = full_config.get("cloud", {})

    if not cloud_cfg.get("project_id"):
        return None

    return GCPTriggerProvider.from_config(cloud_cfg)


