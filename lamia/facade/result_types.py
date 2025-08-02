"""
Result types for Lamia facade operations.
"""

from dataclasses import dataclass
from typing import Any
from lamia.validation.base import TrackingContext


@dataclass
class LamiaResult:
    result_text: str
    typed_result: Any
    tracking_context: TrackingContext