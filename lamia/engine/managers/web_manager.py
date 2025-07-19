from lamia.engine.managers import Manager
from lamia.engine.config_provider import ConfigProvider
from lamia.validation.base import ValidationResult, BaseValidator
import requests

class WebManager(Manager):
    def __init__(self, config_provider: ConfigProvider):
        self.config_provider = config_provider

    async def execute(self, web_url: str, validator: BaseValidator) -> ValidationResult:
        web_content = requests.get(web_url).text
        print("web_content", web_content)

        validation_result = await validator.validate(web_content)

        return validation_result