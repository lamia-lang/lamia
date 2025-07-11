from typing import Optional, Dict, Any
import aiohttp
import openai
from .base import BaseLLMAdapter, LLMResponse

class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI API adapter with SDK support and HTTP fallback."""
    
    API_URL = "https://api.openai.com/v1/chat/completions"
    
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
    
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.model = model

        # Detect whether the OpenAI SDK is available. If not, fall back to raw HTTP.
        self._use_sdk = True
        self._has_context_memory = None  # User cannot set this for now

        try:
            # Prefer the official SDK when present
            self.client = openai.AsyncOpenAI(api_key=self.api_key)
            self.session = None
        except Exception:
            # SDK not available or failed to initialise – fall back to HTTP
            self._use_sdk = False
            self.client = None
            self.session = None  # Will be created in async_initialize

    async def async_initialize(self) -> None:
        """Lazy resource creation to honour patched dependencies in tests."""
        if self._use_sdk:
            # Ensure client is available (patch-friendly)
            if self.client is None:
                self.client = openai.AsyncOpenAI(api_key=self.api_key)
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
        *,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1000,
        stop_sequences: Optional[list[str]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response using OpenAI's API."""
        if self._use_sdk:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop_sequences,
                **kwargs
            )
            
            return LLMResponse(
                text=response.choices[0].message.content,
                raw_response=response,
                model=self.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            )
        else:
            # HTTP fallback
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if stop_sequences is not None:
                payload["stop"] = stop_sequences
            payload.update(kwargs)
            
            try:
                async with await self.session.post(self.API_URL, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"OpenAI API error: {error_text}")
                        
                    data = await response.json()
                    
                    return LLMResponse(
                        text=data["choices"][0]["message"]["content"],
                        raw_response=data,
                        model=self.model,
                        usage=data.get("usage", {})
                    )
                    
            except aiohttp.ClientError as e:
                raise RuntimeError(f"Failed to communicate with OpenAI API: {str(e)}")

    @property
    def has_context_memory(self) -> bool:
        if self._has_context_memory is not None:
            return self._has_context_memory
        # Infer from model name: chat models (gpt-*, turbo, etc.) have context memory
        chat_prefixes = ("gpt-", "text-davinci-003", "text-davinci-002")
        if self.model.startswith(chat_prefixes) or "turbo" in self.model:
            return True
        # Legacy completion models (e.g., text-davinci-003) are stateless
        return False
    
    async def close(self) -> None:
        """Cleanup any resources used by the adapter."""
        if self._use_sdk and self.client:
            await self.client.close()
        elif self.session:
            await self.session.close()