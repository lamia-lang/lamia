"""CLI handler for `lamia schedule` commands.

Usage:
    lamia schedule add <script.lm> --every day
    lamia schedule add <script.lm> --every day --remote
    lamia schedule add <script.lm> --cron "0 9 * * *"
    lamia schedule list
    lamia schedule update <id> --every day
    lamia schedule remove <id>

Local schedules use OS scheduler (launchd/systemd/schtasks).
Remote schedules use lamia-cloud (pip install "lamia-lang[cloud]").
"""

import argparse
import shutil
import sys
from pathlib import Path

from .base import BaseScheduler, ScheduleJob, generate_schedule_id
from .local import LocalScheduler
from .registry import save_job, remove_job, list_jobs, load_job, find_job_by_script

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
        from .local import _parse_cron_fields
        try:
            _parse_cron_fields(args.cron)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return args.cron

    print("Error: provide exactly one of --every <preset> or --cron <expression>.", file=sys.stderr)
    print(
        f"  Presets: {', '.join(EVERY_CHOICES)} "
        f"(aliases: {', '.join(sorted(EVERY_ALIASES.keys()))})",
        file=sys.stderr,
    )
    sys.exit(1)


def _find_lamia_bin() -> str:
    lamia_path = shutil.which("lamia")
    if lamia_path:
        return lamia_path
    return f"{sys.executable} -m lamia"


def _get_cloud_scheduler(project_root: Path) -> BaseScheduler:
    """Load the cloud scheduler from the lamia-cloud package.

    The lamia-cloud package is responsible for reading config.yaml,
    selecting the provider, and returning a configured BaseScheduler instance.
    """
    try:
        from lamia_cloud import get_scheduler
    except ImportError:
        print(
            "Error: cloud scheduling requires the lamia-cloud package.\n"
            "Install with: pip install \"lamia-lang[cloud]\"\n"
            "See: https://lamia-lang.github.io/lamia/advanced/lamia-cloud/",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        return get_scheduler(project_root)
    except Exception as e:
        print(f"Error: cloud scheduler configuration failed: {e}", file=sys.stderr)
        sys.exit(1)


def _scheduler_for_job(job_data: dict, project_root: Path) -> BaseScheduler:
    """Return the appropriate scheduler based on job backend metadata."""
    backend = job_data.get("backend", "local")
    if backend == "cloud":
        return _get_cloud_scheduler(Path(project_root))
    return LocalScheduler()


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
    job_id = generate_schedule_id(relative_script, str(project_root))

    job = ScheduleJob(
        script=relative_script,
        cron=cron,
        schedule_id=job_id,
        catch_up=not args.no_catch_up,
        project_root=project_root,
    )

    lamia_bin = _find_lamia_bin()
    remote = getattr(args, "remote", False)
    backend = "cloud" if remote else "local"

    if remote:
        scheduler = _get_cloud_scheduler(project_root)
        job.catch_up = False
    else:
        scheduler = LocalScheduler()

    existing = find_job_by_script(relative_script, str(project_root))
    if existing:
        old_scheduler = _scheduler_for_job(existing, project_root)
        old_scheduler.uninstall(ScheduleJob(
            script=existing["script"],
            cron=existing["cron"],
            schedule_id=existing["id"],
            project_root=Path(existing["project_root"]),
        ))

    scheduler.install(job, lamia_bin)
    job_id = save_job(job, lamia_bin, backend=backend)

    schedule_desc = args.every if args.every else cron
    print(f"Scheduled: {relative_script}")
    print(f"  backend:   {backend}")
    print(f"  frequency: {schedule_desc}")
    if cron != "@reboot":
        print(f"  cron:      {cron}")
    print(f"  catch_up:  {job.catch_up}")
    print(f"  id:        {job_id}")


def _handle_list(args: argparse.Namespace) -> None:
    jobs = list_jobs()
    if not jobs:
        print("No scheduled jobs.")
        return

    for job in jobs:
        backend = job.get("backend", "local")
        print(f"  [{job['id']}] {job['script']}")
        print(f"    backend: {backend}")
        cron_val = job['cron']
        friendly = _cron_to_friendly(cron_val)
        print(f"    schedule: {friendly}  catch_up: {job.get('catch_up', True)}")
        print(f"    path: {job['project_root']}")

        last_run = job.get("last_run")
        if last_run:
            status_icon = "ok" if last_run.get("success") else "FAILED"
            ts = last_run.get("timestamp", "unknown")
            error_msg = last_run.get("error", "")
            print(f"    last run: {ts}  status: {status_icon}")
            if error_msg:
                print(f"    error: {error_msg}")
        else:
            print(f"    last run: never")
        print()


def _cron_to_friendly(cron: str) -> str:
    """Convert cron expression back to a friendly name if it matches a preset."""
    for name, expr in EVERY_PRESETS.items():
        if cron == expr:
            return name
    return cron


def _handle_remove(args: argparse.Namespace) -> None:
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
    lamia_bin = _find_lamia_bin()

    scheduler.uninstall(old_job)
    scheduler.install(updated_job, lamia_bin)
    save_job(updated_job, lamia_bin, backend=backend)

    schedule_desc = args.every if args.every else cron
    print(f"Updated schedule: {updated_job.script} [{job_id}]")
    print(f"  backend:   {backend}")
    print(f"  frequency: {schedule_desc}")
    if cron != "@reboot":
        print(f"  cron:      {cron}")
    print(f"  catch_up:  {updated_job.catch_up}")


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
    remove_parser.add_argument("id", help="Job ID (from 'lamia schedule list')")

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
    else:
        parser.print_help()
        sys.exit(1)
