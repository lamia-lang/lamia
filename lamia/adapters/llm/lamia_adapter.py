from typing import Optional, Dict, Any, Set, Type
import asyncio
import logging
import os
import aiohttp
from lamia import LLMModel
from .base import BaseLLMAdapter, LLMResponse, make_strict_schema, sanitize_api_error
from .anthropic_adapter import AnthropicAdapter
from .openai_adapter import OpenAIAdapter
from .local.ollama_adapter import OllamaAdapter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class LamiaAdapter(BaseLLMAdapter):
    """Lamia API adapter that proxies requests to multiple providers."""

    # Supported providers that Lamia can proxy requests to
    _supported_providers: Set[str] = {"openai", "anthropic"}
    
    @classmethod
    def name(cls) -> str:
        return "lamia"
    
    @classmethod
    def env_var_names(cls) -> list[str]:
        """Lamia uses LAMIA_API_KEY environment variable."""
        return ["LAMIA_API_KEY"]
    
    @classmethod
    def is_remote(cls) -> bool:
        return True

    @property
    def supports_structured_output(self) -> bool:
        return True
    
    @classmethod
    def get_supported_providers(cls) -> Set[str]:
        return cls._supported_providers
    
    def __init__(self, api_key: str, api_url: str = "http://209.151.237.90:3389"):
        self.api_key = api_key
        self.api_url = api_url
        self.session = None

    async def async_initialize(self) -> None:
        """Lazy resource creation to honour patched dependencies in tests."""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )

    def _get_endpoint_for_provider(self, provider: str) -> str:
        """Get the appropriate endpoint for the provider."""
        if provider == "anthropic":
            return f"{self.api_url}/v1/messages"
        elif provider == "openai":
            return f"{self.api_url}/v1/chat/completions"
        else:
            raise ValueError(f"Unsupported provider by Lamia proxy: {provider}")

    def _build_request_payload(
        self,
        prompt: str,
        model: LLMModel,
        provider: str,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> Dict[str, Any]:
        """Build request payload according to provider's format."""
        
        base_payload = {
            "model": model.get_model_name_without_provider(),
            "messages": [{"role": "user", "content": prompt}]
        }
        
        if provider == "anthropic":
            # Anthropic format
            payload = {
                **base_payload,
                "max_tokens": model.max_tokens or 1000,
            }
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
        else:
            # OpenAI format (default)
            payload = {
                **base_payload,
                "temperature": model.temperature or 0.7,
                "max_tokens": model.max_tokens or 1000,
            }
            if model.max_tokens is not None:
                payload["max_tokens"] = model.max_tokens
            if model.top_p is not None:
                payload["top_p"] = model.top_p
            if model.frequency_penalty is not None:
                payload["frequency_penalty"] = model.frequency_penalty
            if model.presence_penalty is not None:
                payload["presence_penalty"] = model.presence_penalty
            if model.seed is not None:
                payload["seed"] = model.seed
            if response_model is not None:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_model.__name__,
                        "schema": make_strict_schema(response_model),
                        "strict": True,
                    },
                }
            #if model.stop_sequences is not None:
            #    payload["stop"] = model.stop_sequences
        
        return payload

    def _parse_response(self, data: Dict[str, Any], provider: str, model: LLMModel) -> LLMResponse:
        """Parse response according to provider's format."""
        
        if provider == "anthropic":
            # Anthropic response format
            if "content" in data and len(data["content"]) > 0:
                text = self._extract_anthropic_text(data["content"])
            else:
                raise RuntimeError("Invalid response format from Anthropic via Lamia")
            
            # Anthropic usage format
            usage = {}
            if "usage" in data:
                anthropic_usage = data["usage"]
                usage = {
                    "prompt_tokens": anthropic_usage.get("input_tokens", 0),
                    "completion_tokens": anthropic_usage.get("output_tokens", 0),
                    "total_tokens": anthropic_usage.get("input_tokens", 0) + anthropic_usage.get("output_tokens", 0)
                }
        else:
            # OpenAI response format (default)
            if "choices" in data and len(data["choices"]) > 0:
                text = data["choices"][0]["message"]["content"]
            else:
                raise RuntimeError("Invalid response format from OpenAI via Lamia")
            
            # OpenAI usage format
            usage = data.get("usage", {})
        
        return LLMResponse(
            text=text,
            raw_response=data,
            model=model,
            usage=usage
        )

    @staticmethod
    def _extract_anthropic_text(content_blocks: list[Dict[str, Any]]) -> str:
        for block in content_blocks:
            if block.get("type") == "text":
                return block.get("text", "")
        raise RuntimeError("Invalid Anthropic response format: no text block found")

    async def generate(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """Generate a response using Lamia's API."""
        if not self.session:
            raise RuntimeError("Adapter not initialized. Call async_initialize() first.")
        
        provider_name = model.get_provider_name()
        
        # Determine provider and endpoint based on model
        endpoint_url = self._get_endpoint_for_provider(provider_name)
        
        # Build request payload according to provider's format
        payload = self._build_request_payload(
            prompt,
            model,
            provider_name,
            response_model=response_model,
        )
        
        try:
            async with self.session.post(endpoint_url, json=payload) as response:
                if response.status == 401:
                    raise RuntimeError("Invalid Lamia API key")
                elif response.status == 400:
                    error_text = await response.text()
                    raise RuntimeError(f"Lamia API bad request: {sanitize_api_error(error_text)}")
                elif response.status == 402:
                    raise RuntimeError("Insufficient credits")
                elif response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Lamia API error ({response.status}): {sanitize_api_error(error_text)}")
                    
                data = await response.json()
                
                # Parse response according to provider format
                return self._parse_response(data, provider_name, model)
                
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to communicate with Lamia API: {str(e)}")

    @classmethod
    async def models(cls, api_key: str = "") -> list[dict]:
        """Aggregate models from all base adapters (anthropic, openai, ollama).

        For remote providers the call is only made when a corresponding API
        key is available (passed explicitly or found in the environment).
        Ollama is always attempted since it needs no key.  Failures on
        individual providers are logged and silently skipped so one
        unreachable provider does not block the rest.
        """
        base_adapters: list[type[BaseLLMAdapter]] = [
            AnthropicAdapter,
            OpenAIAdapter,
            OllamaAdapter,
        ]

        async def _fetch(adapter_cls: type[BaseLLMAdapter]) -> list[dict]:
            provider = adapter_cls.name()
            key = api_key
            if not key and adapter_cls.is_remote():
                for env_var in adapter_cls.env_var_names():
                    key = os.environ.get(env_var, "")
                    if key:
                        break
            if adapter_cls.is_remote() and not key:
                return []
            try:
                models = await adapter_cls.models(api_key=key)
                for m in models:
                    m["provider"] = provider
                return models
            except Exception as exc:
                logger.debug("models failed for %s: %s", provider, exc)
                return []

        results = await asyncio.gather(*[_fetch(a) for a in base_adapters])
        combined: list[dict] = []
        for batch in results:
            combined.extend(batch)
        return combined

    async def close(self) -> None:
        """Cleanup HTTP session."""
        if self.session:
            await self.session.close() 