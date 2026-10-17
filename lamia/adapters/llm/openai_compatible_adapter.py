"""Base adapter for APIs that follow the OpenAI chat completions convention."""

import asyncio
from typing import Any, Dict, List, Optional, Type

import aiohttp
from pydantic import BaseModel

from lamia import LLMModel
from lamia.adapters.llm.base import (
    BaseLLMAdapter,
    LLMResponse,
    raise_for_connection_error,
    raise_for_status,
)

_SAMPLING_FIELDS = (
    "temperature",
    "max_tokens",
    "top_p",
    "frequency_penalty",
    "presence_penalty",
    "seed",
)


class OpenAICompatibleAdapter(BaseLLMAdapter):
    """Adapter for APIs that accept OpenAI chat completions requests.

    Subclasses set ``API_URL`` (the full ``/chat/completions`` endpoint) and
    the identity methods ``name()`` and ``is_remote()``.  ``self.api_key``,
    when set, is sent as a Bearer token.  Conversations are posted as native
    role-tagged ``messages``.
    """

    REQUEST_TIMEOUT_SECONDS: Optional[float] = None

    async def async_initialize(self) -> None:
        """Create the HTTP session."""
        self._get_or_create_session()

    async def generate(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """Generate a response to a single user prompt."""
        return await self.generate_messages([{"role": "user", "content": prompt}], model, response_model)

    async def generate_messages(
        self,
        messages: List[Dict[str, str]],
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """Post *messages* to ``API_URL`` and return the assistant reply."""
        payload = self._build_payload(messages, model, response_model)
        data = await self._post_json(self._resolve_api_url(), payload)
        return self._parse_response(data, model)

    async def close(self) -> None:
        """Close the HTTP session."""
        await self._close_session()

    def _build_payload(
        self,
        messages: List[Dict[str, str]],
        model: LLMModel,
        response_model: Optional[Type[BaseModel]],
    ) -> Dict[str, Any]:
        """Build the chat completions request body. Sampling fields left unset on *model* are omitted."""
        payload: Dict[str, Any] = {
            "model": model.get_model_name_without_provider(),
            "messages": list(messages),
        }
        for field in _SAMPLING_FIELDS:
            value = getattr(model, field, None)
            if value is not None:
                payload[field] = value
        return payload

    def _parse_response(self, data: Dict[str, Any], model: LLMModel) -> LLMResponse:
        """Convert a chat completions response body into an LLMResponse."""
        usage = data.get("usage") or {}
        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            raw_response=data,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            model=model.name,
        )

    def _request_headers(self) -> Dict[str, str]:
        """HTTP headers sent with each request. Adds Bearer auth when ``api_key`` is set."""
        headers = {"Content-Type": "application/json"}
        api_key = getattr(self, "api_key", None)
        if isinstance(api_key, str) and api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _resolve_api_url(self) -> str:
        url = getattr(self, "API_URL", None)
        if not isinstance(url, str) or not url.strip():
            raise RuntimeError(f"{self.__class__.__name__} must define a non-empty API_URL.")
        return url

    def _get_or_create_session(self) -> aiohttp.ClientSession:
        session = getattr(self, "session", None)
        if session is None:
            session_kwargs: Dict[str, Any] = {}
            if self.REQUEST_TIMEOUT_SECONDS is not None:
                session_kwargs["timeout"] = aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT_SECONDS)
            session = aiohttp.ClientSession(**session_kwargs)
            self.session = session
        return session

    async def _post_json(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST *payload* and classify failures into ExternalOperationError subclasses."""
        session = self._get_or_create_session()
        try:
            async with session.post(url, json=payload, headers=self._request_headers()) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise_for_status(response.status, error_text, f"{self.name()} API error")
                return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ConnectionError) as e:
            await self._close_session()
            raise_for_connection_error(e, f"Failed to communicate with {self.name()} API")

    async def _close_session(self) -> None:
        """Close the session so the next request creates a fresh one."""
        session = getattr(self, "session", None)
        try:
            if session is not None and not session.closed:
                await session.close()
        except Exception:
            pass
        self.session = None
