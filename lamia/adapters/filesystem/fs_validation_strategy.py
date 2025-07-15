from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Type

from ...engine.interfaces import ValidationStrategy, Manager
from ...validation.base import BaseValidator, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class FSValidationConfig:
    validators: List[Dict[str, Any]] | None = None

class FSValidationStrategy(ValidationStrategy):
    """Validation strategy for filesystem-related operations.

    The strategy is deliberately simple – it just delegates the actual
    operation to the given *manager* (see :pymeth:`Manager.execute`) and
    afterwards runs the configured Lamia validators (if any) on the
    textual representation of the result.

    Right now Lamia does not impose a strict contract on what a
    *filesystem* manager must return: it could be raw bytes, a string or a
    complex structure.  The following heuristic is therefore used:

    1. If the result is already a :class:`str`, validators are executed on
       it directly.
    2. For *bytes* the data is decoded using *utf-8* with ``errors="ignore"``.
    3. Everything else is converted with ``str(result)``.

    If **all** validators pass, their (potentially transformed) output is
    returned; otherwise behaviour depends on *raise_on_failure*.
    """

    def __init__(
        self,
        config: FSValidationConfig | None,
        validator_registry: Dict[str, Type[BaseValidator]],
    ) -> None:
        config = config or FSValidationConfig()
        # Initialise base class (build validator instances)
        super().__init__(validator_registry, config.validators or [])

        self.config = config
        self._initialized = True