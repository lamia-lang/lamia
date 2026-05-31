from typing import Optional, Dict, Any, Type
import aiohttp
from .base import BaseLLMAdapter, LLMResponse, make_strict_schema, sanitize_api_error, raise_for_status, raise_for_connection_error
from lamia import LLMModel
from pydantic import BaseModel

# Try to import OpenAI SDK at module level
try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AsyncOpenAI = None

class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI API adapter with SDK support and HTTP fallback."""
    
    API_URL = "https://api.openai.com/v1/chat/completions"
    MODELS_URL = "https://api.openai.com/v1/models"
    
    @classmethod
    def name(cls) -> str:
        return "openai"
    
    @classmethod
    def env_var_names(cls) -> list[str]:
        """OpenAI uses the standard OPENAI_API_KEY that most applications use."""
        return ["OPENAI_API_KEY"]
    
    @classmethod
    def is_remote(cls) -> bool:
        return True

    @classmethod
    async def models(cls, api_key: str = "") -> list[dict]:
        """Fetch available models from OpenAI's /v1/models endpoint."""
        if OPENAI_AVAILABLE:
            client = AsyncOpenAI(api_key=api_key)
            try:
                response = await client.models.list()
                models = []
                for item in getattr(response, "data", []):
                    if isinstance(item, dict):
                        model_dict = dict(item)
                    elif callable(getattr(item, "model_dump", None)):
                        model_dict = item.model_dump()
                    else:
                        model_dict = {"id": getattr(item, "id", None)}
                    model_id = model_dict.get("id")
                    if model_id:
                        models.append({"id": model_id, **{k: v for k, v in model_dict.items() if k != "id"}})
                return models
            except Exception as e:
                raise RuntimeError(f"Failed to fetch OpenAI models via SDK: {sanitize_api_error(str(e))}")
            finally:
                await client.close()

        headers = {
            "Authorization": f"Bearer {api_key}",
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(cls.MODELS_URL) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"OpenAI API error ({response.status}): {sanitize_api_error(error_text)}")
                    data = await response.json()
                    return [
                        {"id": m["id"], **{k: v for k, v in m.items() if k != "id"}}
                        for m in data.get("data", [])
                    ]
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to fetch OpenAI models: {e}")

    @property
    def supports_structured_output(self) -> bool:
        return True
    
    def __init__(self, api_key: str):
        self.api_key = api_key

        self.client = None
        self.session = None

        if OPENAI_AVAILABLE:
            self.client = AsyncOpenAI(api_key=self.api_key)
            self._use_sdk = True
        else:
            # Fall back to HTTP client
            self._use_sdk = False
            self.session = None  # Will be created in async_initialize

    async def async_initialize(self) -> None:
        """Lazy resource creation to honour patched dependencies in tests."""
        if self._use_sdk:
            # Ensure client is available (patch-friendly)
            if self.client is None:
                self.client = AsyncOpenAI(api_key=self.api_key)
        else:
            # Ensure aiohttp session is created with patched ClientSession
            if self.session is None:
                self.session = aiohttp.ClientSession(
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                )
    
    async def generate(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """Generate a response using OpenAI's API."""
        response_format = None
        if response_model is not None:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": make_strict_schema(response_model),
                    "strict": True,
                },
            }

        if self._use_sdk:
            request_kwargs: Dict[str, Any] = {
                "model": model.get_model_name_without_provider(),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": model.temperature,
                "max_tokens": model.max_tokens,
                "top_p": model.top_p,
                "frequency_penalty": model.frequency_penalty,
                "presence_penalty": model.presence_penalty,
                "seed": model.seed,
            }
            if response_format is not None:
                request_kwargs["response_format"] = response_format

            try:
                response = await self.client.chat.completions.create(**request_kwargs)
            except Exception as e:
                raise_for_connection_error(e, "OpenAI API error")

            return LLMResponse(
                text=response.choices[0].message.content,
                raw_response=response,
                model=model.name,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
            )
        else:
            # HTTP fallback
            payload = {
                "model": model.get_model_name_without_provider(),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": model.temperature,
                "max_tokens": model.max_tokens,
                "top_p": model.top_p,
                "frequency_penalty": model.frequency_penalty,
                "presence_penalty": model.presence_penalty,
                "seed": model.seed,
            }
            if response_format is not None:
                payload["response_format"] = response_format

            try:
                async with self.session.post(self.API_URL, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise_for_status(response.status, error_text, "OpenAI API error")

                    data = await response.json()

                    return LLMResponse(
                        text=data["choices"][0]["message"]["content"],
                        raw_response=data,
                        model=model.name,
                        usage=data.get("usage", {})
                    )

            except aiohttp.ClientError as e:
                raise_for_connection_error(e, "Failed to communicate with OpenAI API")
    
    async def close(self) -> None:
        """Cleanup any resources used by the adapter."""
        if self._use_sdk and self.client:
            await self.client.close()
        elif self.session:
            await self.session.close()