import os
import tempfile
import yaml
import pytest
from unittest import mock
from lamia.cli import interactive_mode
from lamia.engine.engine import LamiaEngine

# Helper to create a temporary config file
def make_config(config_dict):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.yaml')
    with open(tmp.name, 'w') as f:
        yaml.safe_dump(config_dict, f)
    return tmp.name

class DummyResponse:
    def __init__(self, text, model="openai", is_valid=True, error_message=None):
        self.text = text
        self.model = model
        self.usage = 42
        self.validation_result = {
            'is_valid': is_valid,
            'error_message': error_message
        }

@pytest.mark.asyncio
async def test_interactive_mode_single_model(monkeypatch):
    config = {
        'default_model': 'openai',
        'models': {'openai': {'enabled': True}},
        'validation': {
            'enabled': True,
            'max_retries': 1,
            'fallback_models': [],
            'validators': [{'type': 'html'}]
        }
    }
    config_path = make_config(config)
    engine = LamiaEngine(config_path)
    await engine.start()
    # Simulate user entering a prompt and then 'SEND', then exit
    user_inputs = iter(["Hello, world!", "SEND", "exit"])
    monkeypatch.setattr('builtins.input', lambda *a, **kw: next(user_inputs))
    # Patch generate to return a dummy response
    with mock.patch.object(engine, 'generate', return_value=DummyResponse("<b>ok</b>")):
        with mock.patch('builtins.print') as mprint:
            with pytest.raises(SystemExit):
                await interactive_mode(engine)
            # Check that the response was printed
            found = any("<b>ok</b>" in str(call) for call in mprint.call_args_list)
            assert found
    await engine.stop()
    os.unlink(config_path)

@pytest.mark.asyncio
async def test_interactive_mode_multiple_models(monkeypatch):
    config = {
        'default_model': 'openai',
        'models': {'openai': {'enabled': True}, 'ollama': {'enabled': True}},
        'validation': {
            'enabled': True,
            'max_retries': 1,
            'fallback_models': ['ollama'],
            'validators': [{'type': 'html'}]
        }
    }
    config_path = make_config(config)
    engine = LamiaEngine(config_path)
    await engine.start()
    user_inputs = iter(["Test fallback", "SEND", "exit"])
    monkeypatch.setattr('builtins.input', lambda *a, **kw: next(user_inputs))
    with mock.patch.object(engine, 'generate', return_value=DummyResponse("<b>fallback</b>", model="ollama")):
        with mock.patch('builtins.print') as mprint:
            with pytest.raises(SystemExit):
                await interactive_mode(engine)
            found = any("<b>fallback</b>" in str(call) for call in mprint.call_args_list)
            assert found
    await engine.stop()
    os.unlink(config_path)

@pytest.mark.asyncio
async def test_interactive_mode_custom_validator(monkeypatch):
    config = {
        'default_model': 'openai',
        'models': {'openai': {'enabled': True}},
        'validation': {
            'enabled': True,
            'max_retries': 1,
            'fallback_models': [],
            'validators': [{
                'type': 'code_python', 'language': 'python', 'strict': True
            }]
        }
    }
    config_path = make_config(config)
    engine = LamiaEngine(config_path)
    await engine.start()
    user_inputs = iter(["def foo():\n    return 1", "SEND", "exit"])
    monkeypatch.setattr('builtins.input', lambda *a, **kw: next(user_inputs))
    with mock.patch.object(engine, 'generate', return_value=DummyResponse("def foo():\n    return 1")):
        with mock.patch('builtins.print') as mprint:
            with pytest.raises(SystemExit):
                await interactive_mode(engine)
            found = any("def foo():" in str(call) for call in mprint.call_args_list)
            assert found
    await engine.stop()
    os.unlink(config_path)

@pytest.mark.asyncio
async def test_interactive_mode_validator_failure(monkeypatch):
    config = {
        'default_model': 'openai',
        'models': {'openai': {'enabled': True}},
        'validation': {
            'enabled': True,
            'max_retries': 1,
            'fallback_models': [],
            'validators': [{'type': 'html'}]
        }
    }
    config_path = make_config(config)
    engine = LamiaEngine(config_path)
    await engine.start()
    user_inputs = iter(["not html", "SEND", "exit"])
    monkeypatch.setattr('builtins.input', lambda *a, **kw: next(user_inputs))
    with mock.patch.object(engine, 'generate', return_value=DummyResponse("not html", is_valid=False, error_message="Invalid HTML")):
        with mock.patch('builtins.print') as mprint:
            with pytest.raises(SystemExit):
                await interactive_mode(engine)
            found = any("Invalid output" in str(call) for call in mprint.call_args_list)
            assert found
    await engine.stop()
    os.unlink(config_path) 