from typing import Optional, Dict, Any, Set
import aiohttp
import json
from lamia import LLMModel
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
    def get_supported_providers(cls) -> Set[str]:
        return cls._supported_providers
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = None

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
        model: LLMModel
    ) -> LLMResponse:
        """Generate a response using Lamia's API."""
        if not self.session:
            raise RuntimeError("Adapter not initialized. Call initialize() first.")
        
        # Build request payload according to Lamia API spec
        payload = {
            "model": model,
            "prompt": prompt,
            "params": {
                "temperature": model.temperature,
                "max_tokens": model.max_tokens, 
                "top_p": model.top_p,
                "top_k": model.top_k,
                "frequency_penalty": model.frequency_penalty,
                "presence_penalty": model.presence_penalty,
                "seed": model.seed,
            }
        }
        if model.stop_sequences is not None:
            payload["params"]["stop_sequences"] = model.stop_sequences
            
        
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
    
    async def close(self) -> None:
        """Cleanup HTTP session."""
        if self.session:
            await self.session.close() 