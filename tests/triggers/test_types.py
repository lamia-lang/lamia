"""Tests for lamia.triggers.types — the cloud-independent TriggerStage.

TriggerStage must stay structurally compatible with lamia_cloud.types.TriggerStage
(the deploy path passes lamia's TriggerStage instances straight into
lamia_cloud's TriggerDeploymentPlan via duck typing, with no conversion).
This is verified with a field-name contract test, same pattern as
ScriptCapabilities <-> SCRIPT_CAPABILITY_FIELDS.
"""

from dataclasses import fields

import pytest

from lamia.triggers.types import TriggerStage, trigger_stage_field_names


def test_trigger_stage_defaults():
    stage = TriggerStage(stage_index=0, trigger_method="email_received")
    assert stage.trigger_config == {}
    assert stage.output_bindings == []
    assert stage.script_source == ""


@pytest.mark.integration
def test_trigger_stage_field_names_match_lamia_cloud():
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    from lamia_cloud.types import TriggerStage as CloudTriggerStage

    cloud_field_names = tuple(f.name for f in fields(CloudTriggerStage))
    assert trigger_stage_field_names() == cloud_field_names, (
        "TriggerStage contract changed. If you add/rename/remove fields, "
        "update BOTH lamia.triggers.types.TriggerStage and "
        "lamia_cloud.types.TriggerStage — lamia's deploy path passes "
        "TriggerStage instances into lamia_cloud via duck typing."
    )
