from typing import Optional, Dict, Any
import aiohttp
import json

from ...utils.dependencies import import_optional
from .base import BaseLLMAdapter, LLMResponse

class AnthropicAdapter(BaseLLMAdapter):
    """Anthropic API adapter with SDK support and HTTP fallback."""
    
    API_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"
    
    def __init__(self, api_key: str, model: str = "claude-3-opus-20240229"):
        self.api_key = api_key
        self.model = model
        self.client = None
        self.session = None
        self._use_sdk = False
        
    async def __aenter__(self):
        # Try to import Anthropic SDK
        anthropic_module, success, error = import_optional(
            "anthropic", 
            min_version="0.5.0"
        )
        
        if success:
            self._use_sdk = True
            self.client = anthropic_module.AsyncAnthropic(api_key=self.api_key)
        else:
            print("Using HTTP fallback for Anthropic API")
            self.session = aiohttp.ClientSession(
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": self.API_VERSION,
                    "Content-Type": "application/json"
                }
            )
        
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._use_sdk and self.client:
            await self.client.close()
        elif self.session:
            await self.session.close()
            
    async def generate(self, 
                      prompt: str, 
                      temperature: float = 0.7, 
                      max_tokens: int = 1000) -> LLMResponse:
        """Generate a response using Anthropic's API."""
        
        if self._use_sdk:
            return await self._generate_with_sdk(prompt, temperature, max_tokens)
        else:
            return await self._generate_with_http(prompt, temperature, max_tokens)
            
    async def _generate_with_sdk(self, 
                               prompt: str, 
                               temperature: float, 
                               max_tokens: int) -> LLMResponse:
        """Generate response using the Anthropic SDK."""
        response = await self.client.messages.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return LLMResponse(
            text=response.content[0].text,
            model=self.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        )
            
    async def _generate_with_http(self, 
                                prompt: str, 
                                temperature: float, 
                                max_tokens: int) -> LLMResponse:
        """Generate response using direct HTTP calls."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
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