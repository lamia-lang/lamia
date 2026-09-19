"""OpenRouter adapter for Lamia."""

import asyncio
import logging
import os
from typing import Optional, Type

import aiohttp
from pydantic import BaseModel

from lamia import LLMModel
from lamia.adapters.llm.base import (
    BaseLLMAdapter,
    LLMResponse,
    raise_for_connection_error,
    raise_for_status,
)

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = os.getenv(
    "OPENROUTER_API_URL",
    "https://openrouter.ai/api/v1",
).rstrip("/")


class OpenRouterAdapter(BaseLLMAdapter):
    """OpenRouter LLM adapter."""

    @classmethod
    def name(cls) -> str:
        return "openrouter"

    @classmethod
    def is_remote(cls) -> bool:
        return True

    def __init__(self, api_key: str = "", api_url: str = OPENROUTER_API_URL):
        self.api_key = api_key
        self.api_url = api_url
        self.session: Optional[aiohttp.ClientSession] = None

    @classmethod
    async def models(cls, api_key: str = "") -> list[dict]:
        models_url = f"{OPENROUTER_API_URL}/models"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    models_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    if isinstance(data, dict) and isinstance(data.get("data"), list):
                        return [
                            {"id": m["id"], "provider": "openrouter"}
                            for m in data["data"]
                            if m.get("id")
                        ]
                    if isinstance(data, list):
                        return [
                            {"id": m["id"], "provider": "openrouter"}
                            for m in data
                            if isinstance(m, dict) and m.get("id")
                        ]
                    return []
        except Exception:
            return []

    async def async_initialize(self) -> None:
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=120),
            )

    async def generate(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        if self.session is None:
            await self.async_initialize()
        assert self.session is not None

        model_name = model.get_model_name_without_provider()

        payload: dict = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
        }
        if model.temperature is not None:
            payload["temperature"] = model.temperature
        if model.max_tokens is not None:
            payload["max_tokens"] = model.max_tokens
        if model.top_p is not None:
            payload["top_p"] = model.top_p

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with self.session.post(
                f"{self.api_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise_for_status(response.status, error_text, "OpenRouter API error")
                data = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ConnectionError) as exc:
            await self._close_session()
            raise_for_connection_error(exc, "OpenRouter connection error")

        usage_data = data.get("usage", {})
        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            raw_response=data,
            usage={
                "prompt_tokens": usage_data.get("prompt_tokens", 0),
                "completion_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            },
            model=model_name,
        )

    async def _close_session(self) -> None:
        try:
            if self.session and not self.session.closed:
                await self.session.close()
        except Exception:
            pass
        self.session = None

    async def close(self) -> None:
        await self._close_session()
