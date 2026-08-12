"""CLI handler for `lamia schedule` commands.

Usage:
    lamia schedule add <script.lm> --every day
    lamia schedule add <script.lm> --every day --remote
    lamia schedule add <script.lm> --cron "0 9 * * *"
    lamia schedule list
    lamia schedule update <id> --every day
    lamia schedule remove <id>
    lamia schedule logs <id>

Local schedules use OS scheduler (launchd/systemd/schtasks).
Remote schedules use lamia-cloud (pip install "lamia-lang[cloud]").
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lamia.id_gen import generate_unique_id
from lamia.runtime import find_lamia_bin

from .base import BaseScheduler, ScheduleJob
from .cloud_scheduler import (
    get_cloud_scheduler,
    LAMIA_CLOUD_AVAILABLE,
    deploy_scheduled_trigger,
    fetch_cloud_statuses,
)
from .local_scheduler import LocalScheduler
from .registry import save_job, remove_job, list_jobs, load_job, find_job_by_script, set_paused
from lamia.triggers.extraction import extract_all_triggers


def _ensure_ci_auth(project_root: Path) -> None:
    """Set up CI authentication before any cloud operations. No-op locally."""
    from lamia.cli.remote import _setup_ci_auth_if_needed

    _setup_ci_auth_if_needed(project_root)


EVERY_PRESETS = {
    "hour": "0 * * * *",
    "day": "0 9 * * *",
    "weekday": "0 9 * * 1-5",
    "week": "0 9 * * 1",
    "on-wake": "@reboot",
}

# Backward-compatible aliases for older docs/commands.
EVERY_ALIASES = {
    "hourly": "hour",
    "daily": "day",
    "weekdays": "weekday",
    "weekly": "week",
}

EVERY_CHOICES = list(EVERY_PRESETS.keys())


def _resolve_cron(args: argparse.Namespace) -> str:
    """Resolve schedule from --every preset or --cron expression."""
    if args.every:
        preset = args.every.lower().strip()
        preset = EVERY_ALIASES.get(preset, preset)
        if preset not in EVERY_PRESETS:
            aliases = ", ".join(sorted(EVERY_ALIASES.keys()))
            print(
                f"Error: unknown preset '{args.every}'. Choose from: {', '.join(EVERY_CHOICES)}. "
                f"Aliases: {aliases}",
                file=sys.stderr,
            )
            sys.exit(1)
        return EVERY_PRESETS[preset]

    if args.cron:
        return args.cron

    print("Error: provide exactly one of --every <preset> or --cron <expression>.", file=sys.stderr)
    print(
        f"  Presets: {', '.join(EVERY_CHOICES)} "
        f"(aliases: {', '.join(sorted(EVERY_ALIASES.keys()))})",
        file=sys.stderr,
    )
    sys.exit(1)


def _scheduler_for_job(job_data: dict, project_root: Path) -> BaseScheduler:
    """Return the appropriate scheduler based on job backend metadata."""
    backend = job_data.get("backend", "local")
    if backend == "cloud":
        return get_cloud_scheduler(Path(project_root))
    return LocalScheduler()


def _fetch_cloud_jobs() -> list[dict]:
    """Return cloud schedule entries from the local cache.

    Cloud state (paused, last run) is fetched from GCP — the local file
    only remembers which cloud jobs exist so we know what to query.
    TODO: replace with CloudScheduler.list_jobs() when lamia-cloud adds it.
    """
    return [j for j in list_jobs() if j.get("backend") == "cloud"]


def _handle_add(args: argparse.Namespace) -> None:
    script = args.script
    script_path = Path(script).resolve()

    if not script_path.exists():
        print(f"Error: script not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    if not script_path.suffix == ".lm":
        print(f"Error: only .lm scripts can be scheduled", file=sys.stderr)
        sys.exit(1)

    cron = _resolve_cron(args)

    project_root = script_path.parent
    relative_script = script_path.name
    remote = getattr(args, "remote", False)

    if remote:
        _ensure_ci_auth(project_root)
        stages = extract_all_triggers(script_path)
        if stages:
            deploy_scheduled_trigger(relative_script, project_root, cron, stages)
            return

    existing = find_job_by_script(relative_script, str(project_root))
    job_id = existing["id"] if existing else generate_unique_id()

    job = ScheduleJob(
        script=relative_script,
        cron=cron,
        schedule_id=job_id,
        catch_up=not args.no_catch_up,
        project_root=project_root,
    )

    lamia_bin = find_lamia_bin()
    backend = "cloud" if remote else "local"

    if remote:
        scheduler = get_cloud_scheduler(project_root)
        job.catch_up = False
    else:
        scheduler = LocalScheduler()

    if existing:
        old_scheduler = _scheduler_for_job(existing, project_root)
        old_scheduler.uninstall(ScheduleJob(
            script=existing["script"],
            cron=existing["cron"],
            schedule_id=existing["id"],
            project_root=Path(existing["project_root"]),
        ))

    try:
        scheduler.install(job, lamia_bin)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    job_id = save_job(job, lamia_bin, backend=backend)

    schedule_desc = args.every if args.every else cron
    print(f"Scheduled: {relative_script}")
    print(f"  backend:   {backend}")
    print(f"  frequency: {schedule_desc}")
    if cron != "@reboot":
        print(f"  cron:      {cron}")
    print(f"  catch_up:  {job.catch_up}")
    print(f"  id:        {job_id}")






def _format_error_line(error_msg: str, job: dict) -> str:
    """Truncate a potentially huge error to a single readable line.

    If the error is multi-line or longer than 120 chars, show only the first
    meaningful line and append a pointer to the full log file.
    """
    first_line = error_msg.split("\n", 1)[0].strip()
    max_len = 120
    truncated = len(first_line) > max_len or "\n" in error_msg

    if len(first_line) > max_len:
        first_line = first_line[:max_len] + "..."

    if not truncated:
        return first_line

    backend = job.get("backend", "local")
    if backend == "local":
        job_id = job.get("id", "")
        log_path = Path.home() / ".lamia" / "logs" / "schedules" / job_id / "schedule.log"
        return f"{first_line}  (see {log_path})"

    return f"{first_line}  (see cloud logs)"


def _print_job(job: dict, last_run: dict | None = None) -> None:
    """Print a single job entry."""
    backend = job.get("backend", "local")
    paused = job.get("paused", False)
    status_label = " [PAUSED]" if paused else ""
    print(f"  [{job['id']}] {job['script']}{status_label}")
    print(f"    backend: {backend}")
    cron_val = job['cron']
    friendly = _cron_to_friendly(cron_val)
    print(f"    schedule: {friendly}  catch_up: {job.get('catch_up', True)}")
    print(f"    path: {job['project_root']}")
    if job.get("source_missing"):
        print("    source: MISSING (script file not found at path)")

    if last_run is None:
        last_run = job.get("last_run")

    if job.get("source_missing"):
        print("    last run: unavailable  status: SOURCE_MISSING")
    elif last_run:
        status_icon = "ok" if last_run.get("success") else "FAILED"
        ts = last_run.get("timestamp", "unknown")
        error_msg = last_run.get("error", "")
        print(f"    last run: {ts}  status: {status_icon}")
        if error_msg:
            print(f"    error: {_format_error_line(error_msg, job)}")
    else:
        print(f"    last run: never")
    print()


def _handle_list(args: argparse.Namespace) -> None:
    local_jobs = [j for j in list_jobs() if j.get("backend", "local") == "local"]

    for job in local_jobs:
        _print_job(job)

    if not LAMIA_CLOUD_AVAILABLE:
        if not local_jobs:
            print("No scheduled jobs.")
        return

    sys.stderr.write("  fetching cloud schedules...")
    sys.stderr.flush()
    cloud_jobs = _fetch_cloud_jobs()
    cloud_statuses = fetch_cloud_statuses(cloud_jobs) if cloud_jobs else {}
    sys.stderr.write("\r\033[K")
    sys.stderr.flush()

    for job in cloud_jobs:
        _print_job(job, last_run=cloud_statuses.get(job["id"]))

    if not local_jobs and not cloud_jobs:
        print("No scheduled jobs.")

    try:
        from lamia_cloud import get_deployer
        deployer = get_deployer(Path.cwd())
        cleaned = deployer.cleanup_stale_resources()
        for name in cleaned:
            print(f"  Cleaned up stale resource: {name}", file=sys.stderr)
    except Exception:
        pass


def _cron_to_friendly(cron: str) -> str:
    """Convert cron expression back to a friendly name if it matches a preset."""
    for name, expr in EVERY_PRESETS.items():
        if cron == expr:
            return name
    return cron


def _handle_remove(args: argparse.Namespace) -> None:
    if getattr(args, "orphaned", False) is True:
        if getattr(args, "id", None):
            print("Error: provide either <id> or --orphaned, not both.", file=sys.stderr)
            sys.exit(1)
        _handle_remove_orphaned()
        return

    if not getattr(args, "id", None):
        print("Error: provide a schedule id or use --orphaned.", file=sys.stderr)
        sys.exit(1)

    job_id = args.id
    job_data = load_job(job_id)

    if not job_data:
        print(f"Error: no schedule found with id '{job_id}'", file=sys.stderr)
        sys.exit(1)

    job = ScheduleJob(
        script=job_data["script"],
        cron=job_data["cron"],
        schedule_id=job_id,
        catch_up=job_data.get("catch_up", True),
        project_root=Path(job_data["project_root"]),
    )

    scheduler = _scheduler_for_job(job_data, Path(job_data["project_root"]))
    scheduler.uninstall(job)
    remove_job(job_id)
    print(f"Removed schedule: {job_data['script']} [{job_id}]")


def _handle_remove_orphaned() -> None:
    orphaned = [j for j in list_jobs() if j.get("source_missing")]
    orphaned = [j for j in orphaned if j.get("backend", "local") != "cloud"]

    safe = []
    for j in orphaned:
        last_run = j.get("last_run")
        if last_run:
            ts_str = last_run.get("timestamp", "")
            if ts_str:
                try:
                    run_time = datetime.fromisoformat(ts_str)
                    if datetime.now(timezone.utc) - run_time < timedelta(days=7):
                        print(
                            f"  Skipped: {j['script']} [{j['id']}] "
                            f"(ran within 7 days — use 'remove <id>' instead)",
                            file=sys.stderr,
                        )
                        continue
                except ValueError:
                    pass
        safe.append(j)
    orphaned = safe

    if not orphaned:
        print("No orphaned schedules found.")
        return

    removed = 0
    for job_data in orphaned:
        job_id = job_data["id"]
        job = ScheduleJob(
            script=job_data["script"],
            cron=job_data["cron"],
            schedule_id=job_id,
            catch_up=job_data.get("catch_up", True),
            project_root=Path(job_data["project_root"]),
        )
        try:
            scheduler = _scheduler_for_job(job_data, Path(job_data["project_root"]))
            scheduler.uninstall(job)
        except Exception:
            pass
        if remove_job(job_id):
            removed += 1
            print(f"Removed orphaned schedule: {job_data['script']} [{job_id}]")

    print(f"Removed {removed} orphaned schedule(s).")


def _handle_update(args: argparse.Namespace) -> None:
    job_id = args.id
    job_data = load_job(job_id)

    if not job_data:
        print(f"Error: no schedule found with id '{job_id}'", file=sys.stderr)
        sys.exit(1)

    cron = _resolve_cron(args)

    if args.catch_up:
        catch_up = True
    elif args.no_catch_up:
        catch_up = False
    else:
        catch_up = job_data.get("catch_up", True)

    updated_job = ScheduleJob(
        script=job_data["script"],
        cron=cron,
        schedule_id=job_id,
        catch_up=catch_up,
        project_root=Path(job_data["project_root"]),
    )

    old_job = ScheduleJob(
        script=job_data["script"],
        cron=job_data["cron"],
        schedule_id=job_id,
        catch_up=job_data.get("catch_up", True),
        project_root=Path(job_data["project_root"]),
    )

    backend = job_data.get("backend", "local")
    scheduler = _scheduler_for_job(job_data, Path(job_data["project_root"]))
    lamia_bin = find_lamia_bin()

    scheduler.uninstall(old_job)
    try:
        scheduler.install(updated_job, lamia_bin)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    save_job(updated_job, lamia_bin, backend=backend)

    schedule_desc = args.every if args.every else cron
    print(f"Updated schedule: {updated_job.script} [{job_id}]")
    print(f"  backend:   {backend}")
    print(f"  frequency: {schedule_desc}")
    if cron != "@reboot":
        print(f"  cron:      {cron}")
    print(f"  catch_up:  {updated_job.catch_up}")


def _handle_pause(args: argparse.Namespace) -> None:
    job_id = args.id
    job_data = load_job(job_id)

    if not job_data:
        print(f"Error: no schedule found with id '{job_id}'", file=sys.stderr)
        sys.exit(1)

    if job_data.get("paused"):
        print(f"Already paused: {job_data['script']} [{job_id}]")
        return

    job = ScheduleJob(
        script=job_data["script"],
        cron=job_data["cron"],
        schedule_id=job_id,
        catch_up=job_data.get("catch_up", True),
        project_root=Path(job_data["project_root"]),
    )

    scheduler = _scheduler_for_job(job_data, Path(job_data["project_root"]))
    scheduler.pause(job)
    set_paused(job_id, True)
    print(f"Paused: {job_data['script']} [{job_id}]")


def _handle_resume(args: argparse.Namespace) -> None:
    job_id = args.id
    job_data = load_job(job_id)

    if not job_data:
        print(f"Error: no schedule found with id '{job_id}'", file=sys.stderr)
        sys.exit(1)

    if not job_data.get("paused"):
        print(f"Already active: {job_data['script']} [{job_id}]")
        return

    job = ScheduleJob(
        script=job_data["script"],
        cron=job_data["cron"],
        schedule_id=job_id,
        catch_up=job_data.get("catch_up", True),
        project_root=Path(job_data["project_root"]),
    )

    scheduler = _scheduler_for_job(job_data, Path(job_data["project_root"]))
    scheduler.resume(job)
    set_paused(job_id, False)
    print(f"Resumed: {job_data['script']} [{job_id}]")


def _handle_logs(args: argparse.Namespace) -> None:
    job_id = args.id
    job_data = load_job(job_id)

    if not job_data:
        print(f"Error: no schedule found with id '{job_id}'", file=sys.stderr)
        sys.exit(1)

    backend = job_data.get("backend", "local")
    if backend == "local":
        log_path = Path.home() / ".lamia" / "logs" / "schedules" / job_id / "schedule.log"
        if not log_path.exists():
            print("No logs found")
            return
        print(log_path.read_text(), end="")
        return

    scheduler = _scheduler_for_job(job_data, Path(job_data["project_root"]))
    job = ScheduleJob(
        script=job_data["script"],
        cron=job_data["cron"],
        schedule_id=job_id,
        catch_up=job_data.get("catch_up", True),
        project_root=Path(job_data["project_root"]),
    )
    logs = scheduler.fetch_logs(job)
    stdout = logs["stdout"]
    stderr = logs["stderr"]
    logs_url = logs["logs_url"]
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, file=sys.stderr, end="")
    if logs_url:
        print(f"\nLogs: {logs_url}")



def handle_schedule() -> None:
    parser = argparse.ArgumentParser(
        description="Manage scheduled Lamia script execution",
        prog="lamia schedule",
    )
    subparsers = parser.add_subparsers(dest="action")

    add_parser = subparsers.add_parser(
        "add",
        help="Schedule a script for recurring execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "All times are local machine time.\n\n"
            "Defaults:\n"
            "  catch-up enabled (disable with --no-catch-up)\n\n"
            "Exactly one of --every or --cron is required.\n\n"
            "Examples:\n"
            "  lamia schedule add daily_task.lm --every day\n"
            "  lamia schedule add daily_task.lm --every on-wake\n"
            "  lamia schedule add daily_task.lm --cron \"0 9 * * *\"\n\n"
            f"Presets: {', '.join(EVERY_CHOICES)}\n"
            f"Aliases: {', '.join(sorted(EVERY_ALIASES.keys()))}"
        ),
    )
    add_parser.add_argument("script", help="Path to the .lm script file")
    frequency_group = add_parser.add_mutually_exclusive_group(required=True)
    frequency_group.add_argument(
        "--every",
        metavar="PRESET",
        help=f"Schedule preset: {', '.join(EVERY_CHOICES)} (aliases supported)",
    )
    frequency_group.add_argument(
        "--cron",
        metavar="EXPR",
        help='Custom cron expression (e.g. "0 9 * * *"). Times are local.',
    )
    add_parser.add_argument(
        "--no-catch-up",
        action="store_true",
        help="Skip missed runs when machine wakes (default: catch up)",
    )
    add_parser.add_argument(
        "--remote",
        action="store_true",
        help="Use cloud scheduler instead of local OS scheduler. Requires lamia cloud extra.",
    )

    subparsers.add_parser("list", help="List all scheduled jobs")

    remove_parser = subparsers.add_parser("remove", help="Remove a scheduled job")
    remove_parser.add_argument("id", nargs="?", help="Job ID (from 'lamia schedule list')")
    remove_parser.add_argument(
        "--orphaned",
        action="store_true",
        help="Remove schedules whose source script file no longer exists",
    )

    pause_parser = subparsers.add_parser("pause", help="Pause a scheduled job")
    pause_parser.add_argument("id", help="Job ID (from 'lamia schedule list')")

    resume_parser = subparsers.add_parser("resume", help="Resume a paused job")
    resume_parser.add_argument("id", help="Job ID (from 'lamia schedule list')")

    logs_parser = subparsers.add_parser("logs", help="View execution logs for a scheduled job")
    logs_parser.add_argument("id", help="Job ID (from 'lamia schedule list')")

    update_parser = subparsers.add_parser(
        "update",
        help="Update an existing scheduled job in one command",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  lamia schedule update <id> --every day\n"
            "  lamia schedule update <id> --cron \"15 10 * * *\"\n"
            "  lamia schedule update <id> --every on-wake --no-catch-up\n"
        ),
    )
    update_parser.add_argument("id", help="Job ID (from 'lamia schedule list')")
    update_freq_group = update_parser.add_mutually_exclusive_group(required=True)
    update_freq_group.add_argument(
        "--every",
        metavar="PRESET",
        help=f"Schedule preset: {', '.join(EVERY_CHOICES)} (aliases supported)",
    )
    update_freq_group.add_argument(
        "--cron",
        metavar="EXPR",
        help='Custom cron expression (e.g. "0 9 * * *"). Times are local.',
    )
    update_catchup_group = update_parser.add_mutually_exclusive_group(required=False)
    update_catchup_group.add_argument(
        "--catch-up",
        action="store_true",
        help="Enable catch-up on missed runs.",
    )
    update_catchup_group.add_argument(
        "--no-catch-up",
        action="store_true",
        help="Disable catch-up on missed runs.",
    )

    if len(sys.argv) >= 3 and sys.argv[2] == "add" and len(sys.argv) == 3:
        add_parser.print_help()
        sys.exit(2)

    args = parser.parse_args(sys.argv[2:])

    if args.action == "add":
        _handle_add(args)
    elif args.action == "list":
        _handle_list(args)
    elif args.action == "remove":
        _handle_remove(args)
    elif args.action == "update":
        _handle_update(args)
    elif args.action == "pause":
        _handle_pause(args)
    elif args.action == "resume":
        _handle_resume(args)
    elif args.action == "logs":
        _handle_logs(args)
    else:
        parser.print_help()
        sys.exit(1)
