"""Tests for how LLMManager sends single prompts and conversations to the adapter."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from lamia import LLMModel
from lamia._internal_types.model_retry import ModelWithRetries
from lamia.adapters.llm.base import LLMResponse
from lamia.engine.config_provider import ConfigProvider
from lamia.engine.managers.llm.files_context_manager import files
from lamia.engine.managers.llm.llm_manager import LLMManager
from lamia.interpreter.commands import LLMCommand
from lamia.validation.base import BaseValidator, ValidationResult

HISTORY = [
    {"role": "user", "content": "List the files"},
    {"role": "assistant", "content": '{"tool": "list_files", "args": {}}'},
]


@pytest.fixture
def adapter():
    adapter = Mock()
    adapter.supports_structured_output = False
    adapter.generate = AsyncMock(return_value=LLMResponse(text="ok", raw_response=None, usage={}, model="m"))
    adapter.generate_messages = AsyncMock(return_value=LLMResponse(text="ok", raw_response=None, usage={}, model="m"))
    return adapter


@pytest.fixture
def manager(adapter):
    model = LLMModel(name="openai:gpt-4o")
    with patch.object(LLMManager, "_check_all_required_providers"), \
            patch.object(LLMManager, "_check_all_required_api_keys"):
        manager = LLMManager(ConfigProvider({"model_chain": [ModelWithRetries(model, 1)]}))
    manager.create_adapter_from_config = AsyncMock(return_value=adapter)
    return manager


async def test_single_prompt_goes_through_generate(manager, adapter):
    await manager.execute(LLMCommand("Hello"))

    assert adapter.generate.await_args.args == ("Hello",)
    adapter.generate_messages.assert_not_awaited()


async def test_conversation_goes_through_generate_messages(manager, adapter):
    await manager.execute(LLMCommand("Tool results JSON:\n{}", history=HISTORY))

    assert adapter.generate_messages.await_args.args == (
        [*HISTORY, {"role": "user", "content": "Tool results JSON:\n{}"}],
    )
    adapter.generate.assert_not_awaited()


async def test_history_is_sent_as_given(manager, adapter):
    history = [
        {"role": "user", "content": "Summarize {@notes.txt}"},
        {"role": "assistant", "content": "Sure"},
    ]

    await manager.execute(LLMCommand("Continue", history=history))

    assert adapter.generate_messages.await_args.args[0][:2] == history


async def test_file_references_are_sent_as_given(manager, adapter, tmp_path):
    (tmp_path / "notes.txt").write_text("remember this")

    with files(str(tmp_path)):
        await manager.execute(LLMCommand("Summarize {@notes.txt}"))

    assert adapter.generate.await_args.args == ("Summarize {@notes.txt}",)


async def test_failed_attempts_are_sent_as_turns_on_retry(adapter):
    manager = _manager([ModelWithRetries(LLMModel(name="openai:gpt-4o"), 2)], [adapter])
    adapter.generate.return_value = LLMResponse(text="bad", raw_response=None, usage={}, model="m")
    adapter.generate_messages.return_value = LLMResponse(text="good", raw_response=None, usage={}, model="m")

    await manager.execute(LLMCommand("Summarize"), validator=_validator())

    assert adapter.generate.await_args.args == ("Return JSON.\n\nSummarize",)
    assert adapter.generate_messages.await_args.args == ([
        {"role": "user", "content": "Return JSON.\n\nSummarize"},
        {"role": "assistant", "content": "bad"},
        {"role": "user", "content": RETRY_MESSAGE},
    ],)


async def test_fallback_model_receives_earlier_failed_attempts():
    first = _adapter("bad")
    second = _adapter("good")
    manager = _manager(
        [ModelWithRetries(LLMModel(name="openai:gpt-4o"), 1), ModelWithRetries(LLMModel(name="anthropic:claude-sonnet-4-5"), 1)],
        [first, second],
    )

    await manager.execute(LLMCommand("Summarize", history=HISTORY), validator=_validator())

    assert second.generate_messages.await_args.args == ([
        *HISTORY,
        {"role": "user", "content": "Return JSON.\n\nSummarize"},
        {"role": "assistant", "content": "bad"},
        {"role": "user", "content": RETRY_MESSAGE},
    ],)


async def test_fallback_model_gets_its_own_schema_hints(monkeypatch):
    first = _adapter("bad")
    first.supports_structured_output = True
    second = _adapter("good")
    manager = _manager(
        [ModelWithRetries(LLMModel(name="openai:gpt-4o"), 1), ModelWithRetries(LLMModel(name="ollama:llama3"), 1)],
        [first, second],
    )
    monkeypatch.setattr(LLMManager, "_extract_response_model", staticmethod(lambda validator: Mock()))
    monkeypatch.setattr("lamia.engine.managers.llm.llm_manager.has_value_constraints", lambda model: False)

    await manager.execute(LLMCommand("Summarize"), validator=_validator())

    assert first.generate.await_args.args == ("Summarize",)
    assert second.generate_messages.await_args.args[0][0]["content"] == "Return JSON.\n\nSummarize"


RETRY_MESSAGE = "Previous response failed validation. Issue: not JSON. Hint: use braces. Please try again."


def _adapter(text):
    adapter = Mock()
    adapter.supports_structured_output = False
    response = LLMResponse(text=text, raw_response=None, usage={}, model="m")
    adapter.generate = AsyncMock(return_value=response)
    adapter.generate_messages = AsyncMock(return_value=response)
    return adapter


def _manager(model_chain, adapters):
    with patch.object(LLMManager, "_check_all_required_providers"), \
            patch.object(LLMManager, "_check_all_required_api_keys"):
        manager = LLMManager(ConfigProvider({"model_chain": model_chain}))
    manager.create_adapter_from_config = AsyncMock(side_effect=adapters)
    return manager


def _validator():
    async def validate(text, execution_context=None):
        if text == "good":
            return ValidationResult(is_valid=True, raw_text=text, validated_text=text)
        return ValidationResult(is_valid=False, raw_text=text, error_message="not JSON", hint="use braces")

    validator = Mock(spec=BaseValidator)
    validator.initial_hint = "Return JSON."
    validator.validate = validate
    return validator
