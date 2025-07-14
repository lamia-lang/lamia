from __future__ import annotations

from dataclasses import dataclass
from lamia import LLMModel

__all__ = ["ModelWithRetries"]

@dataclass(frozen=True, slots=True)
class ModelWithRetries:
    """Immutable value object coupling an LLMModel with a retry budget.

    Private to Lamia implementation; external callers should not import from
    ``lamia._internal_types``.
    """

    model: LLMModel
    retries: int = 1 