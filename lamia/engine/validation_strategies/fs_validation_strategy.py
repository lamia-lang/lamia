from __future__ import annotations

import logging

from ..managers import ValidationStrategy

logger = logging.getLogger(__name__)

class FSValidationStrategy(ValidationStrategy):
    """Validation strategy for filesystem-related operations.
    """