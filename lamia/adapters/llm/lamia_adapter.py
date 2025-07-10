from typing import Optional, Dict, Any, Set
import aiohttp
import json
from .base import BaseLLMAdapter, LLMResponse

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
    
    @classmethod
    def supports(cls, provider: str) -> bool:
        return provider in cls._supported_providers
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = None
        self._has_context_memory = None

    async def initialize(self) -> None:
        """Initialize HTTP session for Lamia API."""
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        return self

    async def generate(
        self,
        prompt: str,
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response using Lamia's API."""
        if not self.session:
            raise RuntimeError("Adapter not initialized. Call initialize() first.")
        
        # Build request payload according to Lamia API spec
        payload = {
            "model": model,
            "prompt": prompt,
            "params": {
                "temperature": temperature,
                "max_tokens": max_tokens, 
                **kwargs
            }
        }
        
        # Add max_tokens if specified
        if max_tokens is not None:
            payload["params"]["max_tokens"] = max_tokens
            
        
        try:
            async with self.session.post(
                f"{self.api_url}/llm/invoke",
                json=payload
            ) as response:
                if response.status == 401:
                    raise RuntimeError("Invalid Lamia API key")
                elif response.status == 400:
                    error_text = await response.text()
                    raise RuntimeError(f"Lamia API bad request: {error_text}")
                elif response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Lamia API error ({response.status}): {error_text}")
                    
                data = await response.json()
                
                return LLMResponse(
                    text=data["result"],
                    raw_response=data,
                    model=model,
                    usage=data.get("usage", {})
                )
                
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to communicate with Lamia API: {str(e)}")

    @property
    def has_context_memory(self) -> bool:
        """Context memory depends on the underlying provider being proxied."""
        return False
    
    async def close(self) -> None:
        """Cleanup HTTP session."""
        if self.session:
            await self.session.close() 