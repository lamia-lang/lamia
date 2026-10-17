"""Tests for sending user/assistant conversations through LLM adapters."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from lamia import LLMModel
from lamia.adapters.llm.anthropic_adapter import AnthropicAdapter
from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse
from lamia.adapters.llm.lamia_adapter import LamiaAdapter
from lamia.adapters.llm.openai_adapter import OpenAIAdapter
from lamia.adapters.llm.openai_compatible_adapter import OpenAICompatibleAdapter
from lamia.adapters.llm.openrouter_adapter import OpenRouterAdapter
from lamia.adapters.retry.adapter_wrappers.retrying_llm_adapter import RetryingLLMAdapter

CONVERSATION = [
    {"role": "user", "content": "List the files"},
    {"role": "assistant", "content": '{"tool": "list_files", "args": {}}'},
    {"role": "user", "content": "Tool results JSON:\n{}"},
]
JOINED_CONVERSATION = (
    "List the files\n\n"
    'Assistant: {"tool": "list_files", "args": {}}\n\n'
    "Tool results JSON:\n{}"
)


class ZeroConfigAdapter(OpenAICompatibleAdapter):
    API_URL = "https://api.example.com/v1/chat/completions"

    @classmethod
    def name(cls) -> str:
        return "zero-config"

    @classmethod
    def is_remote(cls) -> bool:
        return True


class CustomGenerateAdapter(BaseLLMAdapter):
    def __init__(self):
        self.prompts = []

    @classmethod
    def name(cls) -> str:
        return "custom"

    @classmethod
    def is_remote(cls) -> bool:
        return True

    async def close(self) -> None:
        pass

    async def generate(self, prompt, model, response_model=None):
        self.prompts.append(prompt)
        return LLMResponse(text="ok", raw_response=None, usage={}, model=model.name)


def _chat_completion(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}], "usage": {}}


async def test_openai_compatible_adapter_sends_native_messages():
    adapter = ZeroConfigAdapter()
    adapter._post_json = AsyncMock(return_value=_chat_completion("done"))

    response = await adapter.generate_messages(CONVERSATION, LLMModel(name="zero-config:m"))

    url, payload = adapter._post_json.call_args.args
    assert url == ZeroConfigAdapter.API_URL
    assert payload["messages"] == CONVERSATION
    assert response.text == "done"


async def test_adapter_overriding_generate_receives_joined_prompt():
    adapter = CustomGenerateAdapter()

    await adapter.generate_messages(CONVERSATION, LLMModel(name="custom:m"))

    assert adapter.prompts == [JOINED_CONVERSATION]


async def test_retrying_adapter_forwards_messages():
    inner = ZeroConfigAdapter()
    inner.generate_messages = AsyncMock(
        return_value=LLMResponse(text="ok", raw_response=None, usage={}, model="m")
    )
    model = LLMModel(name="zero-config:m")

    await RetryingLLMAdapter(inner).generate_messages(CONVERSATION, model)

    inner.generate_messages.assert_awaited_once_with(CONVERSATION, model=model, response_model=None)


class MockPostContext:
    def __init__(self, response_data: dict):
        self.response = AsyncMock()
        self.response.status = 200
        self.response.json = AsyncMock(return_value=response_data)

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


def _openai_adapter():
    with patch("lamia.adapters.llm.openai_adapter.OPENAI_AVAILABLE", True), \
            patch("lamia.adapters.llm.openai_adapter.AsyncOpenAI") as client_class:
        client = client_class.return_value
        completion = Mock()
        completion.choices = [Mock(message=Mock(content="ok"))]
        client.chat.completions.create = AsyncMock(return_value=completion)
        adapter = OpenAIAdapter(api_key="key")
    return adapter, lambda: [c.kwargs["messages"] for c in client.chat.completions.create.await_args_list]


def _anthropic_adapter():
    with patch("lamia.adapters.llm.anthropic_adapter.ANTHROPIC_AVAILABLE", True), \
            patch("lamia.adapters.llm.anthropic_adapter.AsyncAnthropic") as client_class:
        client = client_class.return_value
        message = Mock()
        message.content = [Mock(text="ok")]
        message.usage.input_tokens = 1
        message.usage.output_tokens = 1
        client.messages.create = AsyncMock(return_value=message)
        adapter = AnthropicAdapter(api_key="key")
    return adapter, lambda: [c.kwargs["messages"] for c in client.messages.create.await_args_list]


def _session_adapter(adapter, response_data):
    adapter.session = Mock()
    adapter.session.closed = False
    adapter.session.post = Mock(side_effect=lambda *args, **kwargs: MockPostContext(response_data))
    return adapter, lambda: [c.kwargs["json"]["messages"] for c in adapter.session.post.call_args_list]


def _openrouter_adapter():
    return _session_adapter(OpenRouterAdapter(api_key="key"), {"choices": [{"message": {"content": "ok"}}], "usage": {}})


def _lamia_adapter():
    return _session_adapter(LamiaAdapter(api_key="key"), {"choices": [{"message": {"content": "ok"}}], "usage": {}})


def _zero_config_adapter():
    return _session_adapter(ZeroConfigAdapter(), {"choices": [{"message": {"content": "ok"}}], "usage": {}})


@pytest.mark.parametrize(
    "make_adapter",
    [_openai_adapter, _anthropic_adapter, _openrouter_adapter, _lamia_adapter, _zero_config_adapter],
)
async def test_chat_adapters_send_prompt_and_conversation_as_messages(make_adapter):
    adapter, sent_messages = make_adapter()
    model = LLMModel(name="openai:m")

    await adapter.generate("Hello", model)
    await adapter.generate_messages(CONVERSATION, model)

    assert sent_messages() == [[{"role": "user", "content": "Hello"}], CONVERSATION]
