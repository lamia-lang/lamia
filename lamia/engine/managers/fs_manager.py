from lamia.engine.managers import Manager
from lamia.engine.config_provider import ConfigProvider
from lamia.validation.base import ValidationResult, BaseValidator

class FSManager(Manager):
    def __init__(self, config_provider: ConfigProvider, validator: BaseValidator):
        self.config_provider = config_provider

    async def execute(self, file_path: str, validator: BaseValidator) -> ValidationResult:
        with open(file_path, 'r') as file:
            file_content = file.read()

        validation_result = await validator.validate(file_content)

        return validation_result