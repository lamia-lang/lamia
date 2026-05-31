from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Type
import re
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
    """Raise the appropriate ExternalOperationError for SDK/connection failures.

    Attempts to extract an HTTP status code from the exception message
    (SDKs like OpenAI/Anthropic embed them). Falls back to transient
    if no status code is found (network issues are retryable).
    """
    msg = f"{prefix}: {sanitize_api_error(str(error))}"
    status_match = re.search(r'\b([45]\d{2})\b', str(error))
    if status_match:
        status = int(status_match.group(1))
        if status == 429:
            raise ExternalOperationRateLimitError(msg)
        elif 400 <= status < 500:
            raise ExternalOperationPermanentError(msg)
        else:
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

        # Inline $ref before processing
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

        # anyOf / oneOf with object branches (e.g. Optional fields)
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
    
    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """Return the provider name (e.g., 'openai', 'anthropic', 'ollama')."""
        pass
    
    @classmethod
    def env_var_names(cls) -> list[str]:
        """Return list of environment variable names to try, in order of precedence.
        
        Default implementation generates from provider name: {PROVIDER_NAME}_API_KEY
        Override this method for providers that use different or multiple env var names.
        """
        return [f"{cls.name().upper()}_API_KEY"]
    
    @classmethod
    @abstractmethod
    def is_remote(cls) -> bool:
        """Return True if this adapter makes network calls, False for local."""
        pass

    async def async_initialize(self) -> None:
        """Initialize any necessary asynchronous resources for the adapter.

        Subclasses that require asynchronous start-up (e.g. opening network
        sessions, loading local models) should override this method.  Adapters
        that don't need special preparation can rely on this default no-op
        implementation.
        """
        return

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """Generate a response from the LLM.
        
        Pure adapter method - just implement the API call.
        
        Args:
            prompt: The input prompt text
            model: The LLM model configuration
            response_model: Optional Pydantic model for provider-native
                structured output when supported
            
        Returns:
            LLMResponse containing the generated text and metadata
        """
        pass

    @property
    def supports_structured_output(self) -> bool:
        """Whether this adapter passes response_model to the provider's API.

        Defaults to False (safe fallback — Lamia includes schema hints in the
        prompt).  Built-in adapters that implement provider-native structured
        output override this to True.  Custom adapters should override only
        after they actually handle the response_model parameter.
        """
        return False

    @classmethod
    async def models(cls, api_key: str = "") -> list[dict]:
        """Fetch available models from this provider.

        Returns a list of dicts with at least an ``id`` key.  Providers
        that expose richer metadata (created date, owned_by, etc.) may
        include additional keys.

        The default implementation returns an empty list.  Built-in
        adapters override this to query the provider's models endpoint.
        """
        return []

    @property
    def has_context_memory(self) -> bool:
        return False 

    @abstractmethod
    async def close(self) -> None:
        """Cleanup any resources used by the adapter."""
        pass

    async def __aenter__(self):
        await self.async_initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 