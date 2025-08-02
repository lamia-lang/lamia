from lamia.engine.managers import Manager
from lamia.engine.config_provider import ConfigProvider
from lamia.interpreter.commands import FileCommand
from lamia.validation.base import ValidationResult, BaseValidator
from typing import Optional

class FSManager(Manager[FileCommand]):
    def __init__(self, config_provider: ConfigProvider):
        self.config_provider = config_provider

    async def execute(self, command: FileCommand, validator: Optional[BaseValidator] = None) -> ValidationResult:
        with open(command.path, 'r') as file:
            file_content = file.read()

        validation_result = await validator.validate(file_content)

        return validation_result