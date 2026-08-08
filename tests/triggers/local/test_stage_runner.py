"""Tests for lamia.triggers.local.stage_runner — single-stage subprocess execution."""

import json

import pytest

from lamia.triggers.local.stage_runner import run_single_stage


def _write_two_stage_script(tmp_path, tail: str = "pass"):
    """Write a script whose stage 0 binds `name`, stage 1 binds `subject`,
    and stage 1's body references BOTH names — which is only possible if the
    stage 0 binding survives into stage 1's namespace via LAMIA_STAGE_CONTEXT."""
    script = tmp_path / "cross_stage.lm"
    script.write_text(
        "trigger.file_created(name)\n"
        "_seen_name = name\n"
        "\n"
        "trigger.email_received(subject)\n"
        "combined = (name, subject)\n"
        f"{tail}\n"
    )
    return script


class TestStageContextCarriesPriorBindings:
    """Issue #5: stage N>=1 must see output bindings from earlier stages."""

    def test_stage_1_can_read_stage_0_binding(self, tmp_path, monkeypatch):
        script = _write_two_stage_script(tmp_path)

        # Orchestrator simulation for stage 1:
        #  - LAMIA_TRIGGER_EVENT: the CURRENT stage's event (email)
        #  - LAMIA_STAGE_CONTEXT: accumulated bindings from prior stages
        monkeypatch.setenv("LAMIA_TRIGGER_EVENT", json.dumps({"subject": "hi"}))
        monkeypatch.setenv(
            "LAMIA_STAGE_CONTEXT",
            json.dumps({"bindings": {"name": "report.pdf"}}),
        )

        with pytest.raises(SystemExit) as exc:
            run_single_stage(script, stage_index=1, exec_id="e1")
        assert exc.value.code == 0, (
            "stage 1 body references `name` from stage 0; without prior-binding "
            "propagation this raises NameError and exits non-zero"
        )

    def test_stage_0_binding_alone_still_works(self, tmp_path, monkeypatch):
        """Sanity check: stage 0 still gets its own binding populated from the current event."""
        script = _write_two_stage_script(tmp_path)
        monkeypatch.setenv("LAMIA_TRIGGER_EVENT", json.dumps({"name": "hello.txt"}))
        monkeypatch.delenv("LAMIA_STAGE_CONTEXT", raising=False)

        with pytest.raises(SystemExit) as exc:
            run_single_stage(script, stage_index=0, exec_id="e0")
        assert exc.value.code == 0
