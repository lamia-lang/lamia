"""Local trigger registry — persists state at ~/.lamia/triggers/.

Structure:
    ~/.lamia/triggers/
    ├── active.json                    # [{id, script, project_root, mode, pid, started_at}]
    └── {trigger_id}/
        ├── failed_events.json         # [{payload, timestamp, error}]
        ├── seen_messages.json         # [message_ids...] for email dedup
        └── executions/
            └── {exec_id}.json         # {current_stage, context, deadline}
"""

import fcntl
import json
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from lamia.persistence import atomic_write, read_json

TRIGGERS_DIR = Path.home() / ".lamia" / "triggers"

# Guards the entire read-modify-write cycle for a given JSON file. In-process
# concurrent workers hit this lock first; cross-process safety comes from the
# per-file fcntl lock inside _locked_file below.
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _get_lock(key: str) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock


@contextmanager
def _locked_file(path: Path):
    """Acquire an in-process + cross-process lock for a JSON registry file.

    Locking is keyed on the target path so unrelated files (different triggers)
    don't serialize. The lockfile lives beside the target with a ``.lock``
    suffix and is created lazily.
    """
    _ensure_dir(path.parent)
    key = str(path)
    thread_lock = _get_lock(key)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with thread_lock:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _active_file() -> Path:
    return TRIGGERS_DIR / "active.json"


def _trigger_dir(trigger_id: str) -> Path:
    return TRIGGERS_DIR / trigger_id


def _failed_events_file(trigger_id: str) -> Path:
    return _trigger_dir(trigger_id) / "failed_events.json"


def _executions_dir(trigger_id: str) -> Path:
    return _trigger_dir(trigger_id) / "executions"


# ─── Active triggers ─────────────────────────────────────────────────────────

def save_active_trigger(trigger_id: str, script: str, project_root: str, mode: str, pid: int) -> None:
    """Register a trigger as active."""
    with _locked_file(_active_file()):
        entries = read_json(_active_file(), [])
        entries = [e for e in entries if e.get("id") != trigger_id]
        entries.append({
            "id": trigger_id,
            "script": script,
            "project_root": project_root,
            "mode": mode,
            "pid": pid,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        atomic_write(_active_file(), json.dumps(entries, indent=2))


def remove_active_trigger(trigger_id: str) -> bool:
    """Remove a trigger from active list. Returns True if found."""
    with _locked_file(_active_file()):
        entries = read_json(_active_file(), [])
        new_entries = [e for e in entries if e.get("id") != trigger_id]
        if len(new_entries) == len(entries):
            return False
        atomic_write(_active_file(), json.dumps(new_entries, indent=2))
        return True


def list_active_triggers() -> list[dict]:
    """Return all active trigger entries."""
    return read_json(_active_file(), [])


def get_active_trigger(trigger_id: str) -> Optional[dict]:
    """Return a single active trigger entry by ID."""
    for entry in list_active_triggers():
        if entry.get("id") == trigger_id:
            return entry
    return None


# ─── Failed events ───────────────────────────────────────────────────────────

def append_failed_event(trigger_id: str, payload: dict, error: str) -> None:
    """Add a failed event to the trigger's failed events log."""
    path = _failed_events_file(trigger_id)
    with _locked_file(path):
        events = read_json(path, [])
        events.append({
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error,
        })
        atomic_write(path, json.dumps(events, indent=2))


def get_failed_events(trigger_id: str) -> list[dict]:
    """Return all failed events for a trigger."""
    return read_json(_failed_events_file(trigger_id), [])


def clear_failed_events(trigger_id: str) -> int:
    """Remove all failed events. Returns count cleared."""
    path = _failed_events_file(trigger_id)
    with _locked_file(path):
        events = read_json(path, [])
        count = len(events)
        if count > 0:
            atomic_write(path, "[]")
    return count


# ─── Execution state (per-execution isolation) ───────────────────────────────

def save_execution(trigger_id: str, exec_id: str, state: dict) -> None:
    """Persist an execution's state."""
    _ensure_dir(_executions_dir(trigger_id))
    path = _executions_dir(trigger_id) / f"{exec_id}.json"
    atomic_write(path, json.dumps(state, indent=2))


def get_execution(trigger_id: str, exec_id: str) -> Optional[dict]:
    """Load an execution's state."""
    path = _executions_dir(trigger_id) / f"{exec_id}.json"
    if not path.exists():
        return None
    return read_json(path, None)


def remove_execution(trigger_id: str, exec_id: str) -> None:
    """Remove a completed execution's state file."""
    path = _executions_dir(trigger_id) / f"{exec_id}.json"
    try:
        path.unlink()
    except OSError:
        pass


def list_executions(trigger_id: str) -> list[dict]:
    """List all active execution states for a trigger."""
    exec_dir = _executions_dir(trigger_id)
    if not exec_dir.exists():
        return []
    results = []
    for f in exec_dir.glob("*.json"):
        data = read_json(f, None)
        if data is not None:
            results.append(data)
    return results


# ─── Email dedup ─────────────────────────────────────────────────────────────

def get_seen_message_ids(trigger_id: str) -> set[str]:
    """Return set of already-processed email message IDs."""
    path = _trigger_dir(trigger_id) / "seen_messages.json"
    ids = read_json(path, [])
    return set(ids)


def add_seen_message_id(trigger_id: str, message_id: str) -> None:
    """Mark an email message as processed."""
    path = _trigger_dir(trigger_id) / "seen_messages.json"
    with _locked_file(path):
        ids = read_json(path, [])
        if message_id not in ids:
            ids.append(message_id)
            atomic_write(path, json.dumps(ids))
