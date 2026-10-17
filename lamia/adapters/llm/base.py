from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type, get_args
import copy
import re
from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema
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


_ANTHROPIC_REJECTED = frozenset({
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "multipleOf",
    "minLength", "maxLength",
    "minItems", "maxItems",
    "uniqueItems",
})


def strip_for_anthropic(schema: dict) -> dict:
    """Return a deep copy of *schema* with keywords Anthropic rejects removed.

    Anthropic's structured-output endpoint returns 400 for constraint
    keywords like ``minimum``, ``maxLength``, etc.  Other providers
    (OpenAI, Ollama) accept or silently ignore them, so this function
    is called only on the Anthropic code-path.

    ``pattern`` is intentionally kept — Anthropic accepts it.
    """
    result = copy.deepcopy(schema)
    stack: list = [result]

    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue

        for key in _ANTHROPIC_REJECTED & node.keys():
            del node[key]

        for value in node.values():
            if isinstance(value, dict):
                stack.append(value)
            elif isinstance(value, list):
                stack.extend(value)

    return result


def has_value_constraints(model: Type[BaseModel]) -> bool:
    """Return True when *model* declares any value constraint on a field.

    Value constraints are the bounds Pydantic emits for field arguments
    such as ``ge``, ``max_length`` or ``pattern``, as opposed to the
    structural keywords (``type``, ``required``, ``properties``).

    The keyword set is a property of Pydantic's schema output and is
    independent of what any single provider accepts.

    Both the generated schema and the field metadata are inspected, because
    Pydantic keeps some constraints off the schema entirely.

    Returns True whenever the model cannot be inspected with certainty. An
    unneeded hint costs a few prompt tokens; a missing one costs a retry.
    """
    constraint_keys = _pydantic_constraint_keywords()
    if not constraint_keys:
        return True

    try:
        schema = model.model_json_schema()
    except Exception:
        return True

    defs = schema.get("$defs", {})
    seen: set = set()
    stack: list = [schema]

    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue

        ref = node.get("$ref")
        if ref is not None:
            ref_name = ref.rsplit("/", 1)[-1]
            if ref_name not in defs:
                return True
            if ref_name not in seen:
                seen.add(ref_name)
                stack.append(defs[ref_name])
            continue

        if constraint_keys & node.keys():
            return True

        for key, value in node.items():
            if key == "$defs":
                continue
            if isinstance(value, dict):
                stack.append(value)
            elif isinstance(value, list):
                stack.extend(value)

    # Pydantic enforces some constraints without exporting a keyword for them,
    # and which ones reach the schema varies by version, so the field metadata
    # is consulted as well.
    seen_models: set = set()
    models: list = [model]

    while models:
        current = models.pop()
        if current in seen_models:
            continue
        seen_models.add(current)

        for field in current.model_fields.values():
            if field.metadata:
                return True

            annotations: list = [field.annotation]
            while annotations:
                annotation = annotations.pop()
                if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                    models.append(annotation)
                else:
                    annotations.extend(get_args(annotation))

    return False


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

    # ─── Abstract methods ────────────────────────────────────────────────

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

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """Generate a response to a single prompt.

        APIs that follow the OpenAI chat completions convention can derive
        from ``OpenAICompatibleAdapter`` instead of implementing this.
        """
        pass

    # ─── Public overridable methods ──────────────────────────────────────

    @classmethod
    def env_var_names(cls) -> list[str]:
        """Return list of environment variable names to try, in order of precedence."""
        return [f"{cls.name().upper()}_API_KEY"]

    async def async_initialize(self) -> None:
        """Initialize async resources. Override for custom startup behavior."""

    async def generate_messages(
        self,
        messages: List[Dict[str, str]],
        model: LLMModel,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """Generate the next assistant reply to a user/assistant conversation.

        *messages* are ``{"role": "user" | "assistant", "content": str}`` dicts,
        starting with a user message.  The default joins them into one prompt,
        marking assistant turns with ``Assistant:``, for :meth:`generate`;
        adapters whose API accepts role-tagged messages override it.
        """
        return await self.generate(self._join_messages(messages), model, response_model)

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

    @staticmethod
    def _join_messages(messages: List[Dict[str, str]]) -> str:
        parts = []
        for message in messages:
            if message["role"] == "assistant":
                parts.append(f"Assistant: {message['content']}")
            else:
                parts.append(message["content"])
        return "\n\n".join(parts)

    # ─── Context manager protocol ───────────────────────────────────────

    async def __aenter__(self):
        await self.async_initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


def _pydantic_constraint_keywords() -> frozenset:
    """Collect the JSON Schema keywords Pydantic emits for field constraints.

    ``ValidationsMapping`` groups translate Pydantic field arguments (``ge``,
    ``max_length``, ...) into JSON Schema keywords. The type-derived keywords
    are added separately: they come from an annotation such as ``Set``,
    ``datetime`` or ``Enum`` rather than from a field argument, so the mapping
    has no entry for them. An empty result means the mapping could not be
    read, and callers then assume constraints are present.
    """
    type_derived = {"uniqueItems", "format", "enum", "const"}
    try:
        groups = [
            group for group in vars(GenerateJsonSchema.ValidationsMapping).values()
            if isinstance(group, dict) and all(isinstance(v, str) for v in group.values())
        ]
    except AttributeError:
        return frozenset()
    if not groups:
        return frozenset()
    return frozenset(
        {keyword for group in groups for keyword in group.values()} | type_derived
    )
