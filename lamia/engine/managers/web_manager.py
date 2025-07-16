from lamia.engine.managers import Manager
from lamia.engine.validation_strategies.validation_strategy import ValidationStrategy
from lamia.engine.config_provider import ConfigProvider
from lamia.validation.base import ValidationResult

class WebManager(Manager):
    def __init__(self, config_provider: ConfigProvider, validation_strategy: ValidationStrategy):
        self.config_provider = config_provider
        self.validation_strategy = validation_strategy

    async def execute(self, web_url: str) -> ValidationResult:
        web_content = await self.fetch_web_content(web_url)

        validation_result = await self.validation_strategy.validate(web_content)

        return validation_result