from unittest import mock
from lamia import Lamia
from lamia.validation.validators import HTMLValidator, LengthValidator
from examples.custom_validators.code_validator import CodeValidator
import asyncio
from lamia.adapters.llm.openai_adapter import OpenAIAdapter
import pytest

@pytest.mark.integration
def test_api_key_propagated_to_adapter():
    api_keys = {"openai": "sk-test"}
    with mock.patch.object(OpenAIAdapter, "__init__", return_value=None) as mocked_init:
        lamia = Lamia("openai", api_keys=api_keys)
        # Manually start the engine; it's async
        asyncio.run(lamia._engine.start())

        mocked_init.assert_called_once_with(api_key="sk-test", model=mock.ANY)

def test_builtin_validators_are_applied():
    validator = HTMLValidator()
    lamia = Lamia("openai", validators=[validator])
    # Patch engine.generate to return a dummy response
    class DummyResponse:
        text = "<b>ok</b>"
    with mock.patch.object(lamia._engine, 'generate', return_value=DummyResponse()):
        with mock.patch.object(validator, 'validate', return_value=True) as mval:
            result = lamia.run("prompt")
            assert result == "<b>ok</b>"
            mval.assert_called_once_with("<b>ok</b>")

def test_custom_validator_class_is_applied():
    validator = CodeValidator(language="python", strict=True)
    lamia = Lamia("openai", validators=[validator])
    class DummyResponse:
        text = "def foo():\n    return 1"
    with mock.patch.object(lamia._engine, 'generate', return_value=DummyResponse()):
        with mock.patch.object(validator, 'validate', return_value=True) as mval:
            result = lamia.run("prompt")
            assert result == "def foo():\n    return 1"
            mval.assert_called_once_with("def foo():\n    return 1")

def test_multiple_validators_combination():
    validator1 = HTMLValidator()
    validator2 = LengthValidator(max_length=10)
    lamia = Lamia("openai", validators=[validator1, validator2])
    class DummyResponse:
        text = "<b>short</b>"
    with mock.patch.object(lamia._engine, 'generate', return_value=DummyResponse()):
        with mock.patch.object(validator1, 'validate', return_value=True) as mval1, \
             mock.patch.object(validator2, 'validate', return_value=True) as mval2:
            result = lamia.run("prompt")
            assert result == "<b>short</b>"
            mval1.assert_called_once_with("<b>short</b>")
            mval2.assert_called_once_with("<b>short</b>")

def test_validator_failure_raises_valueerror():
    validator = HTMLValidator()
    lamia = Lamia("openai", validators=[validator])
    class DummyResponse:
        text = "not html"
    with mock.patch.object(lamia._engine, 'generate', return_value=DummyResponse()):
        with mock.patch.object(validator, 'validate', return_value=False):
            result = lamia.run("prompt")
            assert "not html" in str(result)
