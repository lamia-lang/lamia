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

    def _build_request_payload(self, prompt: str, model: LLMModel, provider: str) -> Dict[str, Any]:
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
                "temperature": model.temperature or 0.7,
            }
            if model.top_p is not None:
                payload["top_p"] = model.top_p
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
            #if model.stop_sequences is not None:
            #    payload["stop"] = model.stop_sequences
        
        return payload

    def _parse_response(self, data: Dict[str, Any], provider: str, model: LLMModel) -> LLMResponse:
        """Parse response according to provider's format."""
        
        if provider == "anthropic":
            # Anthropic response format
            if "content" in data and len(data["content"]) > 0:
                text = data["content"][0]["text"]
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

    async def generate(
        self,
        prompt: str,
        model: LLMModel
    ) -> LLMResponse:
        """Generate a response using Lamia's API."""
        if not self.session:
            raise RuntimeError("Adapter not initialized. Call async_initialize() first.")
        
        provider_name = model.get_provider_name()
        
        # Determine provider and endpoint based on model
        endpoint_url = self._get_endpoint_for_provider(provider_name)
        
        # Build request payload according to provider's format
        print(f"Building request payload for {provider_name} with model {model.name}")
        payload = self._build_request_payload(prompt, model, provider_name)
        
        try:
            async with self.session.post(endpoint_url, json=payload) as response:
                if response.status == 401:
                    raise RuntimeError("Invalid Lamia API key")
                elif response.status == 400:
                    error_text = await response.text()
                    raise RuntimeError(f"Lamia API bad request: {error_text}")
                elif response.status == 402:
                    raise RuntimeError("Insufficient credits")
                elif response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Lamia API error ({response.status}): {error_text}")
                    
                data = await response.json()
                
                # Parse response according to provider format
                return self._parse_response(data, provider_name, model)
                
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to communicate with Lamia API: {str(e)}")

    async def get_available_models(self) -> list[str]:
        """Fetch available models from Lamia API."""
        if not self.session:
            raise RuntimeError("Adapter not initialized. Call async_initialize() first.")
            
        models_url = f"{self.api_url}/v1/models"
        try:
            async with self.session.get(models_url) as response:
                if response.status == 401:
                    raise RuntimeError("Invalid Lamia API key")
                elif response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Lamia API error ({response.status}): {error_text}")
                
                data = await response.json()
                
                # Parse response according to server's ModelsResponse structure
                if "data" not in data:
                    raise RuntimeError("Invalid response format from Lamia API")
                
                # Extract model IDs from the response
                model_ids = []
                for model in data["data"]:
                    if "id" in model:
                        model_ids.append(model["id"])
                        # Also include aliases if present
                        if "aliases" in model and model["aliases"]:
                            model_ids.extend(model["aliases"])
                
                return model_ids
                
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to communicate with Lamia API: {str(e)}")
    
    async def close(self) -> None:
        """Cleanup HTTP session."""
        if self.session:
            await self.session.close() 