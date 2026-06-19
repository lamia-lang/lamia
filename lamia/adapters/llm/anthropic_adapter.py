from typing import Optional, Dict, Any, Type
import asyncio
import aiohttp
import logging

from .base import BaseLLMAdapter, LLMResponse, LLMModel, make_strict_schema, sanitize_api_error, raise_for_status, raise_for_connection_error, raise_for_sdk_error
from pydantic import BaseModel

logger = logging.getLogger(__name__)

try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    AsyncAnthropic = None

class AnthropicAdapter(BaseLLMAdapter):
    """Anthropic API adapter with SDK support and HTTP fallback."""
    
    API_URL = "https://api.anthropic.com/v1/messages"
    MODELS_URL = "https://api.anthropic.com/v1/models"
    API_VERSION = "2023-06-01"
    
    @classmethod
    def name(cls) -> str:
        return "anthropic"
    
    @classmethod
    def env_var_names(cls) -> list[str]:
        """Anthropic uses the standard ANTHROPIC_API_KEY that most applications use."""
        return ["ANTHROPIC_API_KEY"]
    
    @classmethod
    def is_remote(cls) -> bool:
        return True

    @classmethod
    async def models(cls, api_key: str = "") -> list[dict]:
        """Fetch available models from Anthropic's /v1/models endpoint."""
        if ANTHROPIC_AVAILABLE:
            client = AsyncAnthropic(api_key=api_key)
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
                raise RuntimeError(f"Failed to fetch Anthropic models via SDK: {sanitize_api_error(str(e))}")
            finally:
                await client.close()

        headers = {
            "x-api-key": api_key,
            "anthropic-version": cls.API_VERSION,
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(cls.MODELS_URL) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"Anthropic API error ({response.status}): {sanitize_api_error(error_text)}")
                    data = await response.json()
                    return [
                        {"id": m["id"], **{k: v for k, v in m.items() if k != "id"}}
                        for m in data.get("data", [])
                    ]
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to fetch Anthropic models: {e}")

    @property
    def supports_structured_output(self) -> bool:
        return True
    
    def __init__(self, api_key: str):
        self.api_key = api_key

        self.client = None
        self.session = None

        if ANTHROPIC_AVAILABLE:
            self.client = AsyncAnthropic(api_key=self.api_key)
            self._use_sdk = True
        else:
            self._use_sdk = False
            self.session = aiohttp.ClientSession(
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": self.API_VERSION,
                    "Content-Type": "application/json"
                }
            )
            
    async def _close_session(self) -> None:
        """Close the stale session so the next retry lazily creates a fresh one."""
        if self._use_sdk:
            return
        try:
            if self.session and not self.session.closed:
                await self.session.close()
        except Exception:
            pass
        self.session = None

    async def close(self):
        if self._use_sdk and self.client:
            await self.client.close()
        elif self.session:
            await self.session.close()

    async def generate(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """Generate a response using Anthropic's API."""
        if self._use_sdk:
            if response_model is not None:
                return await self._generate_with_sdk(prompt, model, response_model=response_model)
            return await self._generate_with_sdk(prompt, model)
        else:
            if response_model is not None:
                return await self._generate_with_http(prompt, model, response_model=response_model)
            return await self._generate_with_http(prompt, model)
            
    async def _generate_with_sdk(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """Generate response using the Anthropic SDK."""
        request_kwargs: Dict[str, Any] = {
            "model": model.get_model_name_without_provider(),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": model.max_tokens or 1000,
        }
        # Some Anthropic models reject requests that include both temperature and top_p.
        # If top_p is explicitly set and temperature is not, send top_p only.
        if model.top_p is not None and model.temperature is None:
            request_kwargs["top_p"] = model.top_p
        else:
            request_kwargs["temperature"] = model.temperature if model.temperature is not None else 0.7

        if response_model is not None:
            request_kwargs["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": make_strict_schema(response_model),
                }
            }

        try:
            response = await self.client.messages.create(**request_kwargs)
        except Exception as e:
            raise_for_sdk_error(e, "Anthropic API error")

        return LLMResponse(
            text=response.content[0].text,
            raw_response=response,
            model=model.name,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        )
            
    async def _generate_with_http(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """Generate response using direct HTTP calls."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": self.API_VERSION,
                    "Content-Type": "application/json"
                }
            )
        payload = {
            "model": model.get_model_name_without_provider(),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": model.max_tokens or 1000,
        }
        # Some Anthropic models reject requests that include both temperature and top_p.
        # If top_p is explicitly set and temperature is not, send top_p only.
        if model.top_p is not None and model.temperature is None:
            payload["top_p"] = model.top_p
        else:
            payload["temperature"] = model.temperature if model.temperature is not None else 0.7

        if response_model is not None:
            payload["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": make_strict_schema(response_model),
                }
            }
        
        try:
            async with self.session.post(self.API_URL, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise_for_status(response.status, error_text, "Anthropic API error")

                data = await response.json()

                return LLMResponse(
                    text=data["content"][0]["text"],
                    raw_response=data,
                    usage=data.get("usage", {}),
                    model=model.name,
                )

        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ConnectionError) as e:
            await self._close_session()
            raise_for_connection_error(e, "Failed to communicate with Anthropic API")