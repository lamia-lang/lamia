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

    async def validate(self, manager: Manager, content: str) -> Any:  # type: ignore[override]
        """Execute the *filesystem* operation and validate the result."""

        result = await manager.execute(content)

        # 2. If no validators configured – return result straight away
        if not self.validators:
            return result

        # 3. Decide on *text* that will be passed to validators
        if isinstance(result, str):
            text = result
        elif isinstance(result, (bytes, bytearray)):
            text = result.decode("utf-8", errors="ignore")
        else:
            text = str(result)

        # 4. Chain-validate
        validation_outcome: ValidationResult = await self.chain_validate(text)

        if validation_outcome.is_valid:
            # Propagate `validated_text` when a validator provides a cleaner
            # version of the response – fall back to original *text*
            return validation_outcome.validated_text or result

        # 5. Validation failed – decide according to strategy configuration
        logger.info(
            "Validation failed for filesystem result: %s", validation_outcome.error_message
        )
        if self.config.raise_on_failure:
            raise RuntimeError(validation_outcome.error_message)

        # If we do *not* raise, return the original result so the caller can
        # decide what to do with invalid data.
        return result 