"""Run a single trigger stage in subprocess mode.

Called by the orchestrator via `lamia script.lm --trigger-stage N --trigger-exec-id X`.
Event data is passed via LAMIA_TRIGGER_EVENT environment variable.
Stage context from previous stages via LAMIA_STAGE_CONTEXT.
"""

import json
import os
import sys
from pathlib import Path

from lamia.actions.trigger import TriggerRejectError, TRIGGER_REJECT_EXIT_CODE
from lamia.triggers.extraction import extract_all_triggers


def run_single_stage(script_path: Path, stage_index: int, exec_id: str) -> None:
    """Execute a single stage of a triggered script.

    Injects trigger event data as local variables (output bindings),
    then exec's the stage source code.

    Exit codes:
        0 — success
        2 — trigger.reject() called
        1 — unhandled exception
    """
    stages = extract_all_triggers(script_path)
    if stage_index >= len(stages):
        print(f"Error: stage {stage_index} not found (script has {len(stages)} stages)", file=sys.stderr)
        sys.exit(1)

    stage = stages[stage_index]

    event_json = os.environ.get("LAMIA_TRIGGER_EVENT", "{}")
    try:
        event_data = json.loads(event_json)
    except json.JSONDecodeError:
        event_data = {}

    stage_context_json = os.environ.get("LAMIA_STAGE_CONTEXT", "")
    stage_context = {}
    if stage_context_json:
        try:
            stage_context = json.loads(stage_context_json)
        except json.JSONDecodeError:
            pass

    namespace: dict = {
        "__name__": "__main__",
        "__file__": str(script_path),
        "_trigger_event": event_data,
        "_trigger_exec_id": exec_id,
        "_trigger_stage_context": stage_context,
    }

    # Inject prior-stage output bindings first so the current stage can reference
    # names bound by earlier stages. Current-stage bindings then overlay (a
    # later stage that reuses the same name should get the new value).
    prior_bindings = stage_context.get("bindings", {}) if isinstance(stage_context, dict) else {}
    if isinstance(prior_bindings, dict):
        namespace.update(prior_bindings)

    for binding in stage.output_bindings:
        if binding in event_data:
            namespace[binding] = event_data[binding]

    try:
        exec(compile(stage.script_source, str(script_path), "exec"), namespace)
    except TriggerRejectError:
        sys.exit(TRIGGER_REJECT_EXIT_CODE)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error in stage {stage_index}: {e}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)
