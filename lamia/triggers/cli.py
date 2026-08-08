"""CLI handler for `lamia trigger` commands.

Usage:
    lamia trigger list [--verbose]
    lamia trigger drain <id>
    lamia trigger clear <id>
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

    drain_parser = subparsers.add_parser("drain", help="Clear failed events for a trigger")
    drain_parser.add_argument("id", help="Trigger ID (shown in list)")

    clear_parser = subparsers.add_parser("clear", help="Stop and unload a trigger")
    clear_parser.add_argument("id", help="Trigger ID (shown in list)")

    args = parser.parse_args(sys.argv[2:])

    if args.action == "list":
        _handle_list(verbose=args.verbose)
    elif args.action == "drain":
        _handle_drain(args.id)
    elif args.action == "clear":
        _handle_clear(args.id)
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


def _handle_drain(trigger_id: str) -> None:
    """Clear failed events for a trigger (local or cloud)."""
    local_provider = LocalTriggerProvider()
    local_deployments = local_provider.list_deployments()
    local_ids = {d.get("name") for d in local_deployments}

    if trigger_id in local_ids:
        count = local_provider.clear_failed_events(trigger_id)
        if count > 0:
            print(f"Drained {count} failed event(s) for '{trigger_id}'.")
        else:
            print(f"No failed events to drain for '{trigger_id}'.")
        return

    cloud_provider = _try_get_cloud_provider()
    if cloud_provider is not None:
        cloud_deployments = _try_cloud_list()
        cloud_ids = {d.get("name") for d in cloud_deployments}
        if trigger_id in cloud_ids:
            count = cloud_provider.clear_failed_events(trigger_id)
            if count > 0:
                print(f"Drained {count} failed event(s) for '{trigger_id}'.")
            else:
                print(f"No failed events to drain for '{trigger_id}'.")
            return

    print(f"Trigger '{trigger_id}' not found (local or cloud).", file=sys.stderr)
    sys.exit(1)


def _handle_clear(trigger_id: str) -> None:
    """Stop and unload a trigger entirely."""
    local_provider = LocalTriggerProvider()
    local_result = local_provider.clear_trigger(trigger_id)
    if local_result["cleared"]:
        if local_result["was_running"]:
            print(f"Trigger '{trigger_id}' stopped and cleared.")
        else:
            print(f"Trigger '{trigger_id}' was not running; stale registry entry cleaned up.")
        return

    cloud_provider = _try_get_cloud_provider()
    if cloud_provider is not None:
        try:
            cloud_provider.undeploy(trigger_id)
            print(f"Trigger '{trigger_id}' undeployed from cloud.")
            return
        except Exception as e:
            print(f"Error undeploying '{trigger_id}': {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Trigger '{trigger_id}' not found.", file=sys.stderr)
    sys.exit(1)


def _get_failed_events_for(trigger_id: str, location: str) -> list[dict]:
    """Get failed events from the appropriate provider."""
    if location == "local":
        return LocalTriggerProvider().get_failed_events(trigger_id)
    cloud_provider = _try_get_cloud_provider()
    if cloud_provider is not None:
        return cloud_provider.get_failed_events(trigger_id)
    return []


def _try_cloud_list() -> list[dict]:
    """Attempt to list cloud triggers; return [] if lamia_cloud unavailable."""
    provider = _try_get_cloud_provider()
    if provider is None:
        return []
    try:
        deployments = provider.list_deployments()
        for d in deployments:
            d.setdefault("location", "cloud")
        return deployments
    except Exception:
        return []


def _try_get_cloud_provider():
    """Try to load the cloud provider, return None if unavailable."""
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


