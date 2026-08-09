"""CLI handler for `lamia trigger` commands.

Usage:
    lamia trigger list [--verbose]
    lamia trigger drain <id>
    lamia trigger clear <id>
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

    drain_parser = subparsers.add_parser("drain", help="Remove failed events for a trigger")
    drain_parser.add_argument("id", help="Trigger id (from 'lamia trigger list')")

    clear_parser = subparsers.add_parser("clear", help="Stop and remove a trigger")
    clear_parser.add_argument("id", help="Trigger id (from 'lamia trigger list')")

    logs_parser = subparsers.add_parser("logs", help="View execution logs for a trigger")
    logs_parser.add_argument("id", help="Trigger id (from 'lamia trigger list')")

    args = parser.parse_args(sys.argv[2:])

    if args.action == "list":
        _handle_list(verbose=args.verbose)
    elif args.action == "drain":
        _handle_drain(args.id)
    elif args.action == "clear":
        _handle_clear(args.id)
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


def _try_cloud_list() -> list[dict]:
    """Try to list cloud triggers — returns [] if lamia-cloud is unavailable."""
    provider = _get_cloud_provider(Path.cwd())
    if provider is None:
        return []
    try:
        return provider.list_deployments()
    except Exception:
        return []


def _get_failed_events_for(trigger_name: str, location: str) -> list[dict]:
    """Fetch failed events for a trigger — returns [] on error."""
    if location == "local":
        local_provider = LocalTriggerProvider()
        try:
            return local_provider.get_failed_events(trigger_name)
        except Exception:
            return []
    provider = _get_cloud_provider(Path.cwd())
    if provider is None:
        return []
    try:
        return provider.get_failed_events(trigger_name)
    except Exception:
        return []


def _handle_drain(trigger_id: str) -> None:
    """Remove failed events for a trigger."""
    local_provider = LocalTriggerProvider()
    local_triggers = local_provider.list_deployments()
    local_names = {t["name"] for t in local_triggers}

    if trigger_id in local_names:
        count = local_provider.clear_failed_events(trigger_id)
        if count:
            print(f"Drained {count} failed event(s) for {trigger_id}")
        else:
            print(f"No failed events for {trigger_id}")
        return

    cloud_provider = _try_get_cloud_provider()
    if cloud_provider is not None:
        try:
            count = cloud_provider.clear_failed_events(trigger_id)
            if count:
                print(f"Drained {count} failed event(s) for {trigger_id}")
            else:
                print(f"No failed events for {trigger_id}")
            return
        except Exception:
            pass

    print(f"Error: trigger '{trigger_id}' not found", file=sys.stderr)
    sys.exit(1)


def _handle_clear(trigger_id: str) -> None:
    """Stop and remove a trigger."""
    local_provider = LocalTriggerProvider()
    result = local_provider.clear_trigger(trigger_id)

    if result.get("cleared"):
        if result.get("was_running"):
            print(f"Trigger {trigger_id} stopped and cleared")
        else:
            print(f"Trigger {trigger_id} not running (stale entry cleared)")
        return

    cloud_provider = _try_get_cloud_provider()
    if cloud_provider is not None:
        try:
            cloud_provider.clear_trigger(trigger_id)
            print(f"Trigger {trigger_id} stopped and cleared (cloud)")
            return
        except Exception:
            pass

    print(
        "Error: trigger not found locally. For cloud triggers, ensure "
        "cloud.project_id is set in config.yaml",
        file=sys.stderr,
    )
    sys.exit(1)


def _try_get_cloud_provider():
    """Return the cloud trigger provider, or None if unavailable."""
    return _get_cloud_provider(Path.cwd())


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
        from lamia_cloud import get_trigger_provider
    except ImportError:
        return None

    try:
        return get_trigger_provider(project_root)
    except (ValueError, FileNotFoundError):
        return None


