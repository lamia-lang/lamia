"""Local trigger provider — reads state from ~/.lamia/triggers/.

Implements the same interface as the cloud provider (list/get_failed/clear_failed/clear)
so that `lamia trigger list` can merge results from both.
"""

import os
import signal
import subprocess
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from lamia.triggers.local.registry import (
    clear_failed_events,
    get_failed_events,
    list_active_triggers,
    list_executions,
    remove_active_trigger,
)


class LocalTriggerProvider:
    """Local trigger provider backed by filesystem state at ~/.lamia/triggers/."""

    def list_deployments(self) -> List[dict]:
        """List all locally-active triggers."""
        entries = list_active_triggers()
        results = []
        for entry in entries:
            trigger_id = entry.get("id", "")
            pid = entry.get("pid", 0)
            started_at_str = entry.get("started_at", "")
            is_alive = bool(pid) and _is_our_process(pid, started_at_str)

            failed_events = get_failed_events(trigger_id)
            executions = list_executions(trigger_id)

            results.append({
                "name": trigger_id,
                "script": entry.get("script", "?"),
                "trigger_method": "",
                "mode": entry.get("mode", "reactive"),
                "last_run": entry.get("started_at", "never"),
                "last_status": "running" if is_alive else "stopped",
                "failed_event_count": len(failed_events),
                "active_executions": len(executions),
                "location": "local",
            })
        return results

    def get_failed_events(self, name: str) -> List[dict]:
        """Return failed event payloads for a trigger."""
        return get_failed_events(name)

    def clear_failed_events(self, name: str) -> int:
        """Remove all failed events. Returns count cleared."""
        return clear_failed_events(name)

    def clear_trigger(self, name: str) -> dict:
        """Stop and unload a trigger entirely.

        Sends SIGTERM to the orchestrator process (if alive) and removes from
        the registry. Returns ``{"cleared": bool, "was_running": bool}``
        so callers can distinguish "killed a running orchestrator" from
        "cleaned up stale registry entry".
        """
        entries = list_active_triggers()
        target = None
        for entry in entries:
            if entry.get("id") == name:
                target = entry
                break

        if target is None:
            return {"cleared": False, "was_running": False}

        pid = target.get("pid", 0)
        started_at_str = target.get("started_at", "")
        was_running = bool(pid) and _is_our_process(pid, started_at_str)
        if was_running:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                was_running = False

        remove_active_trigger(name)
        return {"cleared": True, "was_running": was_running}


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _process_start_time(pid: int) -> Optional[datetime]:
    """Return the process's start time in UTC via ``ps``, or ``None`` on error.

    macOS-only. When Linux support is added, place a ``linux/`` variant that
    reads ``/proc/<pid>/stat`` and wire this to a platform-dispatch shim.
    """
    try:
        result = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    stamp = result.stdout.strip()
    if not stamp:
        return None
    try:
        # ps -o lstart= prints e.g. "Sat Nov 22 09:00:00 2025" in local time.
        naive = datetime.strptime(stamp, "%a %b %d %H:%M:%S %Y")
    except ValueError:
        return None
    return naive.astimezone(timezone.utc)


def _is_our_process(pid: int, registered_started_at: str) -> bool:
    """True only if PID is alive AND its process was started before we registered it.

    Guards against reporting a reused PID (an unrelated process that happened
    to inherit our old PID after a crash) as "running".
    """
    if not _is_pid_alive(pid):
        return False
    if not registered_started_at:
        return True
    try:
        registered = datetime.fromisoformat(registered_started_at)
    except ValueError:
        return True
    proc_started = _process_start_time(pid)
    if proc_started is None:
        # Can't check — trust the alive signal (best-effort under mac-only ps).
        return True
    # Small clock skew: allow 5 seconds of slop.
    return proc_started <= registered + timedelta(seconds=5)
