import os
import tempfile
import yaml
import pytest
from unittest import mock
from lamia import Lamia
from lamia.validation.validators import HTMLValidator, LengthValidator
from examples.custom_validators.code_validator import CodeValidator

# Helper to read YAML config from Lamia instance
def read_config(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def test_single_model_config():
    lamia = Lamia("openai")
    config = read_config(lamia._config_path)
    assert config['default_model'] == 'openai'
    assert 'openai' in config['models']
    assert config['validation']['fallback_models'] == []

def test_multiple_models_config():
    lamia = Lamia("openai", "ollama", "anthropic")
    config = read_config(lamia._config_path)
    assert config['default_model'] == 'openai'
    assert set(config['models'].keys()) == {"openai", "ollama", "anthropic"}
    assert config['validation']['fallback_models'] == ["ollama", "anthropic"]

def test_default_model_when_none_specified():
    lamia = Lamia()
    config = read_config(lamia._config_path)
    assert config['default_model'] == 'ollama'
    assert 'ollama' in config['models']

def test_api_keys_set_env(monkeypatch):
    api_keys = {"openai": "sk-test", "ollama_api_key": "abc123"}
    lamia = Lamia("openai", api_keys=api_keys)
    assert os.environ["OPENAI_API_KEY"] == "sk-test"
    assert os.environ["OLLAMA_API_KEY"] == "abc123"

def test_no_api_keys_does_not_set_env(monkeypatch):
    # Remove if present
    os.environ.pop("OPENAI_API_KEY", None)
    Lamia("openai")
    assert "OPENAI_API_KEY" not in os.environ

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
            with pytest.raises(ValueError) as exc:
                lamia.run("prompt")
            assert "Validator" in str(exc.value)

def test_temp_config_file_cleanup():
    lamia = Lamia("openai")
    path = lamia._config_path
    assert os.path.exists(path)
    del lamia
    # File should be deleted eventually (may not be immediate due to __del__)
    import time
    for _ in range(10):
        if not os.path.exists(path):
            break
        time.sleep(0.1)
    assert not os.path.exists(path) 