"""Cloud-independent trigger types.

TriggerStage represents one stage of a triggered script (the code between
trigger.* boundaries). Splitting a script into stages is pure AST analysis
and has no cloud dependency — it's needed for local trigger execution too,
not just cloud deployment. lamia_cloud has its own structurally-identical
TriggerStage for the deploy path; the two are kept in sync via a field-name
contract test rather than sharing a class.
"""

from dataclasses import dataclass, field, fields
from typing import List


@dataclass
class TriggerStage:
    """One stage of a triggered script (code between trigger boundaries)."""

    stage_index: int
    trigger_method: str
    trigger_config: dict = field(default_factory=dict)
    output_bindings: List[str] = field(default_factory=list)
    script_source: str = ""


def trigger_stage_field_names() -> tuple[str, ...]:
    """Return ordered TriggerStage field names for contract tests."""
    return tuple(f.name for f in fields(TriggerStage))
