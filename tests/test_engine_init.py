import os
import pytest
from lamia.engine.engine import LamiaEngine

@pytest.mark.asyncio
async def test_single_model():
    os.environ['OPENAI_API_KEY'] = 'dummy'
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
    engine = LamiaEngine(config)
    await engine.start()
    response = await engine.generate("Hello, world!")
    assert isinstance(response.text, str)
    assert response.model == "openai"
    assert 'is_valid' in response.validation_result
    await engine.stop()

@pytest.mark.asyncio
async def test_multiple_models():
    os.environ['OPENAI_API_KEY'] = 'dummy'
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
    engine = LamiaEngine(config)
    await engine.start()
    response = await engine.generate("Test fallback")
    assert isinstance(response.text, str)
    assert response.model in ["openai", "ollama"]
    assert 'is_valid' in response.validation_result
    await engine.stop()

@pytest.mark.asyncio
async def test_custom_validator():
    os.environ['OPENAI_API_KEY'] = 'dummy'
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
    engine = LamiaEngine(config)
    await engine.start()
    prompt = "def foo():\n    return 1"
    response = await engine.generate(prompt)
    assert "def foo():" in response.text
    assert response.validation_result['is_valid']
    await engine.stop()

@pytest.mark.asyncio
async def test_validator_failure():
    os.environ['OPENAI_API_KEY'] = 'dummy'
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
    engine = LamiaEngine(config)
    await engine.start()
    prompt = "not html"
    response = await engine.generate(prompt)
    assert not response.validation_result['is_valid']
    assert "Invalid" in response.validation_result['error_message']
    await engine.stop()