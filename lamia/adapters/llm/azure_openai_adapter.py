from typing import Optional, Dict, Any
import aiohttp
import openai
from .base import BaseLLMAdapter, LLMResponse

class AzureOpenAIAdapter(BaseLLMAdapter):
    """Azure OpenAI API adapter with multiple environment variable support."""
    
    @classmethod
    def name(cls) -> str:
        return "azure-openai"
    
    @classmethod
    def env_var_names(cls) -> list[str]:
        """Azure OpenAI supports multiple env var names for maximum compatibility."""
        return [
            "AZURE_OPENAI_API_KEY",    # Most specific
            "AZURE_OPENAI_KEY",        # Alternative Azure naming
            "OPENAI_API_KEY"           # Fallback for drop-in replacement scenarios
        ]
    
    @classmethod
    def is_remote(cls) -> bool:
        return True
    
    def __init__(self, api_key: str, model: str = "gpt-35-turbo", azure_endpoint: str = None):
        self.api_key = api_key
        self.model = model
        self.azure_endpoint = azure_endpoint
        self._has_context_memory = None
        self._use_sdk = True
        self.client = None
        self.session = None

    async def initialize(self) -> None:
        """Initialize Azure OpenAI client."""
        if self._use_sdk:
            self.client = openai.AsyncAzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.azure_endpoint,
                api_version="2024-02-15-preview"
            )
        else:
            # HTTP fallback for Azure
            self.session = aiohttp.ClientSession(
                headers={
                    "api-key": self.api_key,
                    "Content-Type": "application/json"
                }
            )
        return self
    
    async def generate(self, 
                      prompt: str, 
                      temperature: float = 0.7, 
                      max_tokens: int = 1000) -> LLMResponse:
        """Generate a response using Azure OpenAI's API."""
        if self._use_sdk:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return LLMResponse(
                text=response.choices[0].message.content,
                raw_response=response,
                model=f"azure/{self.model}",
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            )
        else:
            # HTTP fallback implementation would go here
            raise NotImplementedError("HTTP fallback not implemented for Azure OpenAI")

    @property
    def has_context_memory(self) -> bool:
        if self._has_context_memory is not None:
            return self._has_context_memory
        # Azure OpenAI chat models have context memory
        return True
    
    async def close(self) -> None:
        if self._use_sdk and self.client:
            await self.client.close()
        elif self.session:
            await self.session.close()
