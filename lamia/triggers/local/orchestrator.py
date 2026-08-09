"""Local trigger orchestrator — lightweight foreground process.

Watches for events, spawns stage subprocesses, handles retry/reject/timeout.
Mirrors the cloud workflow behavior exactly:
  - exit 0: success → advance to next stage
  - exit 2: reject → discard event, keep listening
  - exit 1: exception → retry (up to MAX_EXCEPTION_RETRIES), then fail
"""

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from queue import Empty, Queue
from typing import Dict, List, Optional

from lamia.id_gen import generate_unique_id
from lamia.runtime import find_lamia_bin
from lamia.triggers.constants import (
    CONTINUATION_TIMEOUT_SECONDS,
    EXIT_CODE_REJECT,
    MAX_CONCURRENT_EXECUTIONS,
    MAX_EXCEPTION_RETRIES,
)
from lamia.triggers.local.event_sources.base import BaseEventSource
from lamia.triggers.local.event_sources.file_watcher import FileEventSource
from lamia.triggers.local.event_sources.email_poller import EmailEventSource
from lamia.triggers.local.registry import (
    append_failed_event,
    list_active_triggers,
    remove_active_trigger,
    remove_execution,
    save_active_trigger,
    save_execution,
)
from lamia.triggers.types import TriggerStage

logger = logging.getLogger(__name__)

FILE_TRIGGER_METHODS = {"file_created", "file_modified", "file_deleted"}
EMAIL_TRIGGER_METHODS = {"email_received"}


@dataclass
class ExecutionState:
    exec_id: str
    trigger_id: str
    current_stage: int
    stage_context: Optional[str]
    retry_count: int
    deadline: datetime


def _create_event_source(trigger_method: str, trigger_id: str) -> BaseEventSource:
    """Factory: create appropriate event source for the trigger method.

    ``trigger_id`` is required so sources that need cross-restart persistence
    (email dedup, etc.) can talk to the shared registry.
    """
    if trigger_method in FILE_TRIGGER_METHODS:
        return FileEventSource(trigger_method)
    if trigger_method in EMAIL_TRIGGER_METHODS:
        return EmailEventSource(trigger_id)
    raise ValueError(f"Unsupported trigger method: {trigger_method}")


def _get_email_config(project_root: Optional[Path] = None) -> dict:
    """Load email trigger configuration from the script's ``project_root``.

    Reading from ``project_root`` instead of the current working directory
    keeps configuration lookup consistent whether the CLI is invoked from
    the project directory or from anywhere else.
    """
    root = Path(project_root) if project_root is not None else Path.cwd()
    config_path = root / "config.yaml"
    if not config_path.exists():
        config_path = root / "config.yml"
    if not config_path.exists():
        return {}
    try:
        import yaml
        with open(config_path) as f:
            full_config = yaml.safe_load(f) or {}
        return full_config.get("triggers", {}).get("email", {})
    except Exception:
        return {}


class _ContinuationBroker:
    """Multiplex a single event source across multiple concurrent continuation waits.

    Solves the fanout problem where N executions all waiting for the same trigger
    method + config each spawn their own event source, so a single external event
    gets delivered to every waiter. With a broker, one source is shared and events
    are routed FIFO to the longest-waiting execution — each event is consumed by
    exactly one waiter.
    """

    def __init__(self, source: BaseEventSource, trigger_config: dict):
        self._source = source
        self._waiters: List[Queue] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        source.start(trigger_config)
        self._pump = threading.Thread(target=self._pump_loop, daemon=True)
        self._pump.start()

    def _pump_loop(self) -> None:
        while not self._stop.is_set():
            event = self._source.wait_for_event(timeout_seconds=1)
            if event is None:
                continue
            with self._lock:
                if not self._waiters:
                    continue  # nobody listening; drop
                target = self._waiters.pop(0)
            try:
                target.put_nowait(event)
            except Exception:
                pass

    def wait_for_event(self, timeout_seconds: int) -> Optional[dict]:
        q: Queue = Queue(maxsize=1)
        with self._lock:
            self._waiters.append(q)
        try:
            return q.get(timeout=timeout_seconds)
        except Empty:
            return None
        finally:
            with self._lock:
                if q in self._waiters:
                    self._waiters.remove(q)

    def stop(self) -> None:
        self._stop.set()
        self._pump.join(timeout=5)
        self._source.stop()


def _broker_key(trigger_method: str, trigger_config: dict) -> str:
    """Stable key for broker reuse across concurrent continuation waits."""
    return f"{trigger_method}::{json.dumps(trigger_config, sort_keys=True)}"


def _bindings_from_event(stage: TriggerStage, event: dict) -> dict:
    """Pick the values for a stage's declared output_bindings out of the event.

    A binding name ("subject", "name", ...) matches the corresponding key on
    the event payload; missing keys are simply skipped.
    """
    if not isinstance(event, dict):
        return {}
    return {b: event[b] for b in stage.output_bindings if b in event}


def _build_trigger_config(stage: TriggerStage, project_root: Optional[Path] = None) -> dict:
    """Merge stage's trigger_config with global email settings if applicable."""
    config = dict(stage.trigger_config)
    if stage.trigger_method in EMAIL_TRIGGER_METHODS:
        email_cfg = _get_email_config(project_root=project_root)
        for key in ("host", "port", "username", "password_env", "poll_interval", "label"):
            if key not in config and key in email_cfg:
                config[key] = email_cfg[key]
    return config


def _spawn_stage(
    script_path: Path,
    stage_index: int,
    event_data: dict,
    stage_context: Optional[str],
    exec_id: str,
) -> int:
    """Spawn a subprocess to execute a single trigger stage.

    Returns the process exit code.
    """
    lamia_bin = find_lamia_bin()
    cmd = lamia_bin.split() + [
        str(script_path),
        "--trigger-stage", str(stage_index),
        "--trigger-exec-id", exec_id,
    ]

    env = os.environ.copy()
    env["LAMIA_TRIGGER_EVENT"] = json.dumps(event_data)
    if stage_context:
        env["LAMIA_STAGE_CONTEXT"] = stage_context

    result = subprocess.run(cmd, env=env, capture_output=False)
    return result.returncode


def run_local_trigger(
    script_path: Path,
    stages: List[TriggerStage],
    project_root: Optional[Path] = None,
) -> None:
    """Main orchestration loop — foreground, lightweight.

    Watches for events for stage 0, spawns subprocesses for each stage,
    handles multi-stage continuation with full isolation.
    """
    if project_root is None:
        project_root = Path.cwd()

    script_name = str(script_path.name)
    root_str = str(project_root)
    existing = next(
        (t for t in list_active_triggers()
         if t.get("script") == script_name and t.get("project_root") == root_str),
        None,
    )
    trigger_id = existing["id"] if existing else generate_unique_id()
    save_active_trigger(trigger_id, script_name, root_str, "reactive", os.getpid())

    print(f"Trigger active: {trigger_id} ({script_path.name})", file=sys.stderr)
    print(f"  stages: {len(stages)}", file=sys.stderr)
    for i, stage in enumerate(stages):
        print(f"  stage {i}: {stage.trigger_method}", file=sys.stderr)
    print(f"  Ctrl+C to stop\n", file=sys.stderr)

    stopped = threading.Event()

    def _signal_handler(signum, frame):
        stopped.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_EXECUTIONS)

    first_stage = stages[0]
    source = _create_event_source(first_stage.trigger_method, trigger_id)
    trigger_config = _build_trigger_config(first_stage, project_root=project_root)
    source.start(trigger_config)

    # Shared broker cache: continuation stages (N>=1) get routed through a broker
    # keyed on (trigger_method, config) so N concurrent executions don't each spin
    # up their own source and receive fanned-out events.
    brokers: Dict[str, _ContinuationBroker] = {}
    brokers_lock = threading.Lock()

    try:
        while not stopped.is_set():
            event = source.wait_for_event(timeout_seconds=5)
            if event is None:
                continue
            executor.submit(
                _handle_execution,
                script_path=script_path,
                stages=stages,
                trigger_id=trigger_id,
                initial_event=event,
                stopped=stopped,
                project_root=project_root,
                brokers=brokers,
                brokers_lock=brokers_lock,
            )
    finally:
        source.stop()
        executor.shutdown(wait=False)
        with brokers_lock:
            for broker in brokers.values():
                broker.stop()
            brokers.clear()
        remove_active_trigger(trigger_id)
        print(f"\nTrigger stopped: {trigger_id}", file=sys.stderr)


def _handle_execution(
    script_path: Path,
    stages: List[TriggerStage],
    trigger_id: str,
    initial_event: dict,
    stopped: threading.Event,
    project_root: Optional[Path] = None,
    brokers: Optional[Dict[str, "_ContinuationBroker"]] = None,
    brokers_lock: Optional[threading.Lock] = None,
) -> None:
    """Handle one full execution (all stages) for a single event."""
    exec_id = uuid.uuid4().hex[:12]
    total_stages = len(stages)
    current_event = initial_event
    stage_context: Optional[str] = None
    accumulated_bindings: dict = {}

    deadline = datetime.now(timezone.utc) + timedelta(seconds=CONTINUATION_TIMEOUT_SECONDS)

    save_execution(trigger_id, exec_id, {
        "exec_id": exec_id,
        "current_stage": 0,
        "deadline": deadline.isoformat(),
    })

    for stage_idx in range(total_stages):
        if stopped.is_set():
            break

        if stage_idx > 0:
            stage = stages[stage_idx]
            continuation_event = _wait_for_continuation(
                stage=stage,
                trigger_id=trigger_id,
                exec_id=exec_id,
                deadline=deadline,
                stopped=stopped,
                project_root=project_root,
                brokers=brokers,
                brokers_lock=brokers_lock,
            )
            if continuation_event is None:
                logger.warning(f"[{exec_id}] Timeout waiting for stage {stage_idx}")
                append_failed_event(
                    trigger_id,
                    initial_event,
                    f"Timeout waiting for stage {stage_idx} continuation event",
                )
                break
            current_event = continuation_event

        exit_code = _run_stage_with_retry(
            script_path=script_path,
            stage_index=stage_idx,
            event_data=current_event,
            stage_context=stage_context,
            exec_id=exec_id,
            trigger_id=trigger_id,
            stopped=stopped,
        )

        if exit_code == EXIT_CODE_REJECT:
            logger.info(f"[{exec_id}] Stage {stage_idx} rejected event")
            break
        if exit_code != 0:
            break

        # Accumulate this stage's output bindings so downstream stages can
        # reference names bound here (issue #5).
        stage_bindings = _bindings_from_event(stages[stage_idx], current_event)
        accumulated_bindings.update(stage_bindings)
        stage_context = json.dumps({
            "stage": stage_idx,
            "event": current_event,
            "bindings": accumulated_bindings,
        })
        save_execution(trigger_id, exec_id, {
            "exec_id": exec_id,
            "current_stage": stage_idx + 1,
            "deadline": deadline.isoformat(),
        })

    remove_execution(trigger_id, exec_id)


def _run_stage_with_retry(
    script_path: Path,
    stage_index: int,
    event_data: dict,
    stage_context: Optional[str],
    exec_id: str,
    trigger_id: str,
    stopped: threading.Event,
) -> int:
    """Run a stage subprocess with retry logic. Returns final exit code."""
    retry_count = 0

    while not stopped.is_set():
        exit_code = _spawn_stage(script_path, stage_index, event_data, stage_context, exec_id)

        if exit_code == 0:
            return 0
        if exit_code == EXIT_CODE_REJECT:
            return EXIT_CODE_REJECT

        retry_count += 1
        if retry_count >= MAX_EXCEPTION_RETRIES:
            logger.error(
                f"[{exec_id}] Stage {stage_index} failed after {retry_count} retries"
            )
            append_failed_event(trigger_id, event_data, f"Stage {stage_index} failed after {retry_count} retries")
            return exit_code

        logger.warning(
            f"[{exec_id}] Stage {stage_index} failed (attempt {retry_count}/{MAX_EXCEPTION_RETRIES}), retrying..."
        )

    return 1


def _wait_for_continuation(
    stage: TriggerStage,
    trigger_id: str,
    exec_id: str,
    deadline: datetime,
    stopped: threading.Event,
    project_root: Optional[Path] = None,
    brokers: Optional[Dict[str, "_ContinuationBroker"]] = None,
    brokers_lock: Optional[threading.Lock] = None,
) -> Optional[dict]:
    """Wait for a continuation event via a shared broker (issue #2: no fanout)."""
    trigger_config = _build_trigger_config(stage, project_root=project_root)

    if brokers is not None and brokers_lock is not None:
        key = _broker_key(stage.trigger_method, trigger_config)
        with brokers_lock:
            broker = brokers.get(key)
            if broker is None:
                source = _create_event_source(stage.trigger_method, trigger_id)
                broker = _ContinuationBroker(source, trigger_config)
                brokers[key] = broker
        while not stopped.is_set():
            remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0:
                return None
            wait_time = min(5, remaining)
            event = broker.wait_for_event(timeout_seconds=int(wait_time))
            if event is not None:
                return event
        return None

    # Fallback path (no shared broker cache) — used by unit tests that patch
    # `_create_event_source`. One source per call, but no cross-execution sharing.
    source = _create_event_source(stage.trigger_method, trigger_id)
    source.start(trigger_config)
    try:
        while not stopped.is_set():
            remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0:
                return None
            wait_time = min(5, remaining)
            event = source.wait_for_event(timeout_seconds=int(wait_time))
            if event is not None:
                return event
    finally:
        source.stop()
    return None
