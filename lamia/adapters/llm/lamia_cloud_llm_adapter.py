"""Cloud LLM adapter — calls lamia-cloud's independent interface.

Similar to OllamaAdapter calling the local ollama server, this adapter
calls lamia-cloud's CloudService interface. lamia-cloud is treated as an
external plugin that knows nothing about lamia's internals.

The adapter is activated when lamia-cloud is installed AND the environment
is detected as a cloud environment (is_on_cloud() returns True).
"""
import logging
from typing import Optional, Type

from pydantic import BaseModel

from lamia.adapters.llm.base import BaseLLMAdapter, LLMModel, LLMResponse, make_strict_schema

logger = logging.getLogger(__name__)

try:
    from lamia_cloud import get_cloud_service, is_on_cloud, CloudLLMRequest
    LAMIA_CLOUD_AVAILABLE = True
except ImportError:
    LAMIA_CLOUD_AVAILABLE = False


def cloud_is_available() -> bool:
    """Check if the cloud adapter should be used (lamia-cloud installed + on cloud)."""
    if not LAMIA_CLOUD_AVAILABLE:
        return False
    return is_on_cloud()


class LamiaCloudLLMAdapter(BaseLLMAdapter):
    """Adapter that routes LLM calls through lamia-cloud's CloudService.

    Translates between lamia's types (LLMModel, LLMResponse) and
    lamia-cloud's independent types (CloudLLMRequest, CloudLLMResponse).
    """

    @classmethod
    def name(cls) -> str:
        return "lamia-cloud"

    @classmethod
    def env_var_names(cls) -> list[str]:
        return []

    @classmethod
    def is_remote(cls) -> bool:
        return True

    @property
    def supports_structured_output(self) -> bool:
        return True

    def __init__(self, api_key: str = ""):
        self._service = get_cloud_service()

    async def async_initialize(self) -> None:
        pass

    async def close(self) -> None:
        await self._service.close()

    async def generate(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """Translate lamia types -> lamia-cloud request, call service, translate back."""
        schema = None
        if response_model is not None:
            schema = make_strict_schema(response_model)

        request = CloudLLMRequest(
            prompt=prompt,
            model=model.get_model_name_without_provider(),
            provider=model.get_provider_name(),
            max_tokens=model.max_tokens or 1000,
            temperature=model.temperature,
            top_p=model.top_p,
            response_schema=schema,
        )

        response = await self._service.generate(request)

        return LLMResponse(
            text=response.text,
            raw_response=response.raw,
            model=model.name,
            usage=response.usage,
        )
