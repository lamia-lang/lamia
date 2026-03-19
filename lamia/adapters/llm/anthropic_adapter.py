from typing import Optional, Dict, Any, Type
import aiohttp
import json

from .base import BaseLLMAdapter, LLMResponse, LLMModel
from pydantic import BaseModel

# Try to import Anthropic SDK at module level
try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    AsyncAnthropic = None

class AnthropicAdapter(BaseLLMAdapter):
    """Anthropic API adapter with SDK support and HTTP fallback."""
    
    API_URL = "https://api.anthropic.com/v1/messages"
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
    
    def __init__(self, api_key: str):
        self.api_key = api_key

        self.client = None
        self.session = None

        if ANTHROPIC_AVAILABLE:
            self.client = AsyncAnthropic(api_key=self.api_key)
            self._use_sdk = True
        else:
            # Fall back to HTTP client
            self._use_sdk = False
            self.session = aiohttp.ClientSession(
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": self.API_VERSION,
                    "Content-Type": "application/json"
                }
            )
            
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
            return await self._generate_with_sdk(prompt, model, response_model=response_model)
        else:
            return await self._generate_with_http(prompt, model, response_model=response_model)
            
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
            "temperature": model.temperature or 0.7,
            "max_tokens": model.max_tokens or 1000,
            "top_p": model.top_p or 1.0,
        }

        if response_model is not None:
            request_kwargs["tools"] = [{
                "name": "structured_response",
                "description": "Return structured response",
                "input_schema": response_model.model_json_schema(),
            }]
            request_kwargs["tool_choice"] = {"type": "tool", "name": "structured_response"}

        response = await self.client.messages.create(**request_kwargs)

        if response_model is not None:
            text = self._extract_tool_input_text_from_sdk_response(response)
        else:
            text = response.content[0].text
        
        return LLMResponse(
            text=text,
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
        payload = {
            "model": model.get_model_name_without_provider(),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": model.max_tokens or 1000,
            "temperature": model.temperature or 0.7,
            "top_p": model.top_p or 1.0
        }

        if response_model is not None:
            payload["tools"] = [{
                "name": "structured_response",
                "description": "Return structured response",
                "input_schema": response_model.model_json_schema(),
            }]
            payload["tool_choice"] = {"type": "tool", "name": "structured_response"}
        
        try:
            async with self.session.post(self.API_URL, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Anthropic API error: {error_text}")
                    
                data = await response.json()

                if response_model is not None:
                    text = self._extract_tool_input_text_from_http_response(data)
                else:
                    text = data["content"][0]["text"]
                
                return LLMResponse(
                    text=text,
                    raw_response=data,
                    usage=data.get("usage", {}),
                    model=model.name,
                )
                
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to communicate with Anthropic API: {str(e)}")

    @staticmethod
    def _extract_tool_input_text_from_sdk_response(response: Any) -> str:
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                return json.dumps(block.input)
        raise RuntimeError("Anthropic structured output expected a tool_use block but none was returned")

    @staticmethod
    def _extract_tool_input_text_from_http_response(data: Dict[str, Any]) -> str:
        for block in data.get("content", []):
            if block.get("type") == "tool_use":
                return json.dumps(block.get("input", {}))
        raise RuntimeError("Anthropic structured output expected a tool_use block but none was returned")