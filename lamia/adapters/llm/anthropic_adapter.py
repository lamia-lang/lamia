from typing import Optional, Dict, Any
import aiohttp
import json

from ...utils.dependencies import import_optional
from .base import BaseLLMAdapter, LLMResponse

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
        self._has_context_memory = None  # User cannot set this for now

        # Try to import Anthropic SDK (and auto-install if allowed).
        anthropic_module, success, _ = import_optional(
            "anthropic",
            min_version="0.5.0"
        )

        if success and anthropic_module is not None:
            self.client = anthropic_module.AsyncAnthropic(api_key=self.api_key)
            self._use_sdk = True
        else:
            # Fall back to HTTP client
            print("Using HTTP fallback for Anthropic API")
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
        *,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1000,
        stop_sequences: Optional[list[str]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response using Anthropic's API."""
        
        if self._use_sdk:
            return await self._generate_with_sdk(prompt, temperature, max_tokens, stop_sequences, **kwargs)
        else:
            return await self._generate_with_http(prompt, temperature, max_tokens, stop_sequences, **kwargs)
            
    async def _generate_with_sdk(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        stop_sequences: Optional[list[str]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response using the Anthropic SDK."""
        response = await self.client.messages.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            stop_sequences=stop_sequences,
            **kwargs
        )
        
        return LLMResponse(
            text=response.content[0].text,
            raw_response=response,
            model=self.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        )
            
    async def _generate_with_http(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        stop_sequences: Optional[list[str]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response using direct HTTP calls."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        if stop_sequences is not None:
            payload["stop_sequences"] = stop_sequences
        payload.update(kwargs)
        
        try:
            async with self.session.post(self.API_URL, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Anthropic API error: {error_text}")
                    
                data = await response.json()
                
                return LLMResponse(
                    text=data["content"][0]["text"],
                    model=self.model,
                    usage=data.get("usage", {})
                )
                
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to communicate with Anthropic API: {str(e)}")

    @property
    def has_context_memory(self) -> bool:
        if self._has_context_memory is not None:
            return self._has_context_memory
        # All Anthropic chat models (Claude, etc.) have context memory
        return True 