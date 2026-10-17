"""OpenRouter adapter for Lamia."""

import logging
import os
from typing import Optional

import aiohttp

from lamia.adapters.llm.openai_compatible_adapter import OpenAICompatibleAdapter

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = os.getenv(
    "OPENROUTER_API_URL",
    "https://openrouter.ai/api/v1",
).rstrip("/")


class OpenRouterAdapter(OpenAICompatibleAdapter):
    """OpenRouter LLM adapter."""

    REQUEST_TIMEOUT_SECONDS = 120

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

    @property
    def API_URL(self) -> str:
        return f"{self.api_url}/chat/completions"

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
