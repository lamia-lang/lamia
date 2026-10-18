from typing import Optional

from lamia.engine.config_provider import ConfigProvider
from lamia.engine.managers import Manager
from lamia.interpreter.command_types import CommandType
from lamia.interpreter.commands import ValueCommand
from lamia.serialization import serialize
from lamia.validation.base import BaseValidator, TrackingContext, ValidationResult


class ValueManager(Manager[ValueCommand]):
    """Serializes Python values to the format of the requested return type and validates the text."""

    def __init__(self, config_provider: ConfigProvider):
        self.config_provider = config_provider

    async def execute(
        self, command: ValueCommand, validator: Optional[BaseValidator] = None
    ) -> ValidationResult:
        text = serialize(command.value, command.return_type)
        context = TrackingContext(
            data_provider_name="python_value",
            command_type=CommandType.VALUE,
            metadata={"value_type": type(command.value).__name__},
        )
        if validator is None:
            return ValidationResult(is_valid=True, raw_text=text, typed_result=text, execution_context=context)
        result = await validator.validate(text, execution_context=context)
        result.raw_text = result.raw_text or text
        result.execution_context = context
        return result
