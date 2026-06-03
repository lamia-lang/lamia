from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Type
import asyncio
import re
import aiohttp
from pydantic import BaseModel
from lamia import LLMModel
from lamia.errors import (
    ExternalOperationTransientError,
    ExternalOperationPermanentError,
    ExternalOperationRateLimitError,
)

_SK_KEY_PATTERN = re.compile(r'sk-[\w*-]+')


def sanitize_api_error(message: str) -> str:
    """Replace sk-* secret key tokens in error messages with [REDACTED]."""
    return _SK_KEY_PATTERN.sub('[REDACTED]', message)


def raise_for_status(status: int, error_text: str, prefix: str) -> None:
    """Raise the appropriate ExternalOperationError subclass for an HTTP status."""
    msg = f"{prefix} (status {status}): {sanitize_api_error(error_text)}"
    if status == 429:
        raise ExternalOperationRateLimitError(msg)
    elif 400 <= status < 500:
        raise ExternalOperationPermanentError(msg)
    else:
        raise ExternalOperationTransientError(msg)


def raise_for_connection_error(error: Exception, prefix: str) -> None:
    """Raise transient external error for network/transport failures."""
    msg = f"{prefix}: {sanitize_api_error(str(error))}"
    raise ExternalOperationTransientError(msg)


def raise_for_sdk_error(error: Exception, prefix: str) -> None:
    """Raise typed external error from SDK exception metadata.

    Uses structured fields such as status/status_code instead of parsing
    exception strings.
    """
    msg = f"{prefix}: {sanitize_api_error(str(error))}"
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(error, "status", None)
    if status is None:
        response = getattr(error, "response", None)
        if response is not None:
            status = getattr(response, "status_code", None)
            if status is None:
                status = getattr(response, "status", None)

    if isinstance(status, int):
        if status == 429:
            raise ExternalOperationRateLimitError(msg)
        if 400 <= status < 500:
            raise ExternalOperationPermanentError(msg)
        raise ExternalOperationTransientError(msg)

    raise ExternalOperationTransientError(msg)


def make_strict_schema(model: Type[BaseModel]) -> dict:
    """Generate a JSON schema with additionalProperties: false on all objects.

    Most LLM providers (Anthropic, OpenAI strict mode) require every object
    node to explicitly forbid extra keys.  Pydantic's model_json_schema()
    does not set this, so we patch the tree after generation.  Also inlines
    any $defs references for maximum provider compatibility.
    """
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def _patch(node: Any) -> Any:
        if not isinstance(node, dict):
            return node

        if "$ref" in node:
            ref_name = node["$ref"].rsplit("/", 1)[-1]
            if ref_name in defs:
                node = defs[ref_name].copy()

        for key, value in list(node.items()):
            if isinstance(value, dict):
                node[key] = _patch(value)
            elif isinstance(value, list):
                node[key] = [_patch(item) for item in value]

        if node.get("type") == "object":
            node["additionalProperties"] = False

        for combiner in ("anyOf", "oneOf"):
            if combiner in node:
                node[combiner] = [_patch(branch) for branch in node[combiner]]

        return node

    return _patch(schema)


@dataclass
class LLMResponse:
    """Container for LLM response data."""
    text: str
    raw_response: Any
    usage: Dict[str, int]
    model: str


class BaseLLMAdapter(ABC):
    """Base interface for all LLM adapters."""

    # ─── Abstract identity methods ───────────────────────────────────────

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """Return the provider name (e.g., 'openai', 'anthropic', 'ollama')."""
        pass

    @classmethod
    @abstractmethod
    def is_remote(cls) -> bool:
        """Return True if this adapter makes network calls, False for local."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Cleanup any resources used by the adapter."""
        pass

    # ─── Public overridable methods ──────────────────────────────────────

    @classmethod
    def env_var_names(cls) -> list[str]:
        """Return list of environment variable names to try, in order of precedence."""
        return [f"{cls.name().upper()}_API_KEY"]

    async def async_initialize(self) -> None:
        """Initialize async resources.

        Default creates an HTTP session for adapters using the default
        generate() path.  Override for custom startup behavior.
        """
        if not hasattr(self, "API_URL"):
            return
        session = getattr(self, "session", None)
        if session is None:
            self.session = aiohttp.ClientSession(headers=self._request_headers())

    async def generate(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Default implementation for OpenAI-compatible HTTP APIs.  Posts a
        chat completions request to API_URL and returns the parsed response.
        Error classification (429/4xx/5xx) is handled automatically.

        Override this method entirely for non-OpenAI APIs or SDK adapters.
        """
        session = await self._get_or_create_session()
        url = self._resolve_api_url()
        payload = {
            "model": model.get_model_name_without_provider(),
            "messages": [{"role": "user", "content": prompt}],
        }
        data = await self._post_json(session, url, payload)
        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            raw_response=data,
            usage=data.get("usage", {}),
            model=model.name,
        )

    @property
    def supports_structured_output(self) -> bool:
        """Whether this adapter passes response_model to the provider's API."""
        return False

    @classmethod
    async def models(cls, api_key: str = "") -> list[dict]:
        """Fetch available models from this provider."""
        return []

    @property
    def has_context_memory(self) -> bool:
        return False

    # ─── Private helpers ─────────────────────────────────────────────────

    async def _get_or_create_session(self) -> "aiohttp.ClientSession":
        """Return existing HTTP session or create one lazily."""
        session = getattr(self, "session", None)
        if session is None:
            session = aiohttp.ClientSession(headers=self._request_headers())
            self.session = session
        return session

    def _resolve_api_url(self) -> str:
        """Resolve API endpoint URL."""
        url = getattr(self, "API_URL", None)
        if not isinstance(url, str) or not url.strip():
            raise RuntimeError(
                f"{self.__class__.__name__} must define non-empty API_URL "
                "or override generate()."
            )
        return url

    def _request_headers(self) -> dict:
        """Default HTTP headers. Adds Bearer auth when api_key is set."""
        headers = {"Content-Type": "application/json"}
        api_key = getattr(self, "api_key", None)
        if isinstance(api_key, str) and api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    async def _post_json(self, session: "aiohttp.ClientSession", url: str, payload: dict) -> dict:
        """POST JSON and classify HTTP errors into ExternalOperationError."""
        prefix = f"{self.name()} API error"
        try:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise_for_status(response.status, error_text, prefix)
                return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise_for_connection_error(e, f"Failed to communicate with {self.name()} API")

    # ─── Context manager protocol ───────────────────────────────────────

    async def __aenter__(self):
        await self.async_initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
