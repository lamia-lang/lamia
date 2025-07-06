import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import asyncio
from pathlib import Path

from lamia.engine.engine import LamiaEngine
from lamia.engine.config_manager import ConfigManager
from lamia.adapters.llm.base import LLMResponse, BaseLLMAdapter
from lamia.adapters.llm.strategy import ValidationStrategy, RetryConfig
from lamia.validation.validator_registry import ValidatorRegistry


@pytest.mark.asyncio
async def test_init_must_start_with_empty_config():
    """Test LamiaEngine initialization with empty config"""
    config = {}
    engine = LamiaEngine(config)
    
    assert isinstance(engine.config_manager, ConfigManager)
    assert engine.adapter is None
    assert engine.validation_strategy is None

    await engine.start()

@pytest.mark.asyncio
async def test_start_with_remote_provider():
    """Test start method with remote provider"""
    config = {
        "default_model": "openai",
        "models": {"openai": {"default_model": "gpt-3.5-turbo"}},
        "api_keys": {"openai": "test-key"}
    }
    engine = LamiaEngine(config)
    
    mock_adapter = Mock()
    mock_adapter.initialize = AsyncMock()
    
    with patch('lamia.engine.engine.create_adapter_from_config', return_value=mock_adapter):
        result = await engine.start()
        
        assert result is True
        assert engine.adapter == mock_adapter
        mock_adapter.initialize.assert_called_once()

@pytest.mark.asyncio
async def test_start_with_local_provider():
    """Test start method with local provider"""
    config = {
        "default_model": "ollama",
        "models": {"ollama": {"default_model": "llama2"}}
    }
    engine = LamiaEngine(config)
    
    result = await engine.start()
    
    assert result is True
    assert engine.adapter is None  # Local providers are lazily initialized

    mock_local_adapter = Mock()
    mock_local_adapter.initialize = AsyncMock()
    mock_local_adapter.close = AsyncMock()
    mock_local_adapter.generate = AsyncMock(return_value=None)

    with patch('lamia.engine.engine.create_adapter_from_config', return_value=mock_local_adapter):
      result = await engine.generate("Hello")
      assert engine.adapter is not None # Local adapter should be initialized after the first generate() is called

@pytest.mark.asyncio
async def test_start_adapter_initialization_failure():
    """Test start method when adapter initialization fails"""
    config = {
        "default_model": "openai",
        "models": {"openai": {"default_model": "gpt-3.5-turbo"}},
        "api_keys": {"openai": "test-key"}
    }
    engine = LamiaEngine(config)
    
    mock_adapter = Mock()
    mock_adapter.initialize = AsyncMock(side_effect=RuntimeError("Init failed"))
    mock_adapter.close = AsyncMock()
    
    with patch('lamia.engine.engine.create_adapter_from_config', return_value=mock_adapter):
        result = await engine.start()
        
        mock_adapter.initialize.assert_called_once()
        assert result is False
        assert engine.adapter == mock_adapter
        await engine.stop()
        mock_adapter.close.assert_called_once()

@pytest.mark.asyncio
async def test_start_config_error():
    """Test start method when config has errors"""
    config = {
        "default_model": "openai",
        "models": {"openai": {"default_model": "gpt-3.5-turbo"}},
        "api_keys": {"openai": "test-key"}
    }
    engine = LamiaEngine(config)
    
    # Mock create_adapter_from_config to raise an exception
    with patch('lamia.engine.engine.create_adapter_from_config', side_effect=Exception("Config error")):
        result = await engine.start()
        
        assert result is False

@pytest.mark.asyncio
async def test_start_validation_engine_start_error():
    """Test start method when validation engine fails to start errors"""
    config = {
        "default_model": "openai",
        "models": {"openai": {"default_model": "gpt-3.5-turbo"}},
        "api_keys": {"openai": "test-key"},
        "validation": {
            "enabled": True,
            "max_retries": 2,
        }
    }
    engine = LamiaEngine(config)
    
    # Mock create_adapter_from_config to raise an exception
    with patch('lamia.engine.engine.ValidationStrategy.__init__', side_effect=Exception("Validation Config error")):
        result = await engine.start()
        
        assert result is False

@pytest.mark.asyncio
async def test_stop_with_adapter():
    """Test stop method with active adapter"""
    config = {"default_model": "openai"}
    engine = LamiaEngine(config)
    
    mock_adapter = Mock()
    mock_adapter.close = AsyncMock()
    engine.adapter = mock_adapter
    
    await engine.stop()
    
    mock_adapter.close.assert_called_once()

@pytest.mark.asyncio
async def test_stop_without_adapter():
    """Test stop method without adapter"""
    config = {"default_model": "openai"}
    engine = LamiaEngine(config)
    
    # Should not raise any exception
    await engine.stop()

@pytest.mark.asyncio
async def test_stop_adapter_close_error():
    """Test stop method when adapter close fails"""
    config = {"default_model": "openai"}
    engine = LamiaEngine(config)
    
    mock_adapter = Mock()
    mock_adapter.close = AsyncMock(side_effect=RuntimeError("Close failed"))
    engine.adapter = mock_adapter
    
    # Should not raise exception, just log error
    await engine.stop()
    
    mock_adapter.close.assert_called_once()

@pytest.mark.asyncio
async def test_generate_with_existing_adapter():
    """Test generate method with existing adapter"""
    config = {
        "default_model": "openai",
        "models": {"openai": {"default_model": "gpt-3.5-turbo", "temperature": 0.7, "max_tokens": 100}}
    }
    engine = LamiaEngine(config)
    
    mock_adapter = Mock()
    expected_response = LLMResponse(
        text="Hello world",
        raw_response=None,
        usage={},
        model="gpt-3.5-turbo"
    )
    mock_adapter.generate = AsyncMock(return_value=expected_response)
    engine.adapter = mock_adapter
    
    result = await engine.generate("Hello")
    
    assert result == expected_response
    mock_adapter.generate.assert_called_once_with(
        "Hello",
        temperature=0.7,
        max_tokens=100
    )

@pytest.mark.asyncio
async def test_generate_with_lazy_adapter_initialization():
    """Test generate method with lazy adapter initialization"""
    config = {
        "default_model": "ollama",
        "models": {"ollama": {"default_model": "llama2", "temperature": 0.8}}
    }
    engine = LamiaEngine(config)
    
    mock_adapter = Mock()
    expected_response = LLMResponse(
        text="Hello world",
        raw_response=None,
        usage={},
        model="llama2"
    )
    mock_adapter.generate = AsyncMock(return_value=expected_response)
    mock_adapter.initialize = AsyncMock()
    
    with patch('lamia.engine.engine.create_adapter_from_config', return_value=mock_adapter):
        result = await engine.generate("Hello")
        
        assert result == expected_response
        assert engine.adapter == mock_adapter
        mock_adapter.initialize.assert_called_once()
        mock_adapter.generate.assert_called_once_with(
            "Hello",
            temperature=0.8,
            max_tokens=None
        )

@pytest.mark.asyncio
async def test_generate_with_parameter_overrides():
    """Test generate method with parameter overrides"""
    config = {
        "default_model": "openai",
        "models": {"openai": {"default_model": "gpt-3.5-turbo", "temperature": 0.7, "max_tokens": 100}}
    }
    engine = LamiaEngine(config)
    
    mock_adapter = Mock()
    expected_response = LLMResponse(
        text="Hello world",
        raw_response=None,
        usage={},
        model="gpt-3.5-turbo"
    )
    mock_adapter.generate = AsyncMock(return_value=expected_response)
    engine.adapter = mock_adapter
    
    result = await engine.generate("Hello", temperature=0.9, max_tokens=200)
    
    assert result == expected_response
    mock_adapter.generate.assert_called_once_with(
        "Hello",
        temperature=0.9,
        max_tokens=200
    )

@pytest.mark.asyncio
async def test_generate_with_validation_strategy():
    """Test generate method with validation strategy enabled"""
    config = {
        "default_model": "openai",
        "models": {"openai": {"default_model": "gpt-3.5-turbo"}},
        "validation": {
            "enabled": True,
            "max_retries": 2,
            "fallback_models": [],
            "validators": [{"type": "html"}]
        }
    }
    engine = LamiaEngine(config)
    
    mock_adapter = Mock()
    mock_strategy = Mock()
    expected_response = LLMResponse(
        text="Validated response",
        raw_response=None,
        usage={},
        model="gpt-3.5-turbo"
    )
    mock_strategy.execute_with_retries = AsyncMock(return_value=expected_response)
    
    engine.adapter = mock_adapter
    engine.validation_strategy = mock_strategy
    
    result = await engine.generate("Hello", temperature=0.8)
    
    assert result == expected_response
    mock_strategy.execute_with_retries.assert_called_once()
    call_args = mock_strategy.execute_with_retries.call_args
    assert call_args.kwargs['primary_adapter'] == mock_adapter
    assert call_args.kwargs['prompt'] == "Hello"
    assert call_args.kwargs['temperature'] == 0.8
    assert call_args.kwargs['max_tokens'] is None

@pytest.mark.asyncio
async def test_generate_calls_execute_with_retries_once():
    """Ensure LamiaEngine.generate delegates to ValidationStrategy.execute_with_retries when validation is enabled."""
    config = {
        "default_model": "openai",
        "models": {"openai": {"default_model": "gpt-3.5-turbo"}},
        "api_keys": {"openai": "test-key"},
        "validation": {
            "enabled": True,
            "max_retries": 2,
            "fallback_models": [],
            "validators": [{"type": "html"}],
        },
    }

    dummy_response = LLMResponse(
        text="Validated response",
        raw_response=None,
        usage={},
        model="openai",
    )

    stub_adapter = MagicMock()
    stub_adapter.initialize = AsyncMock()
    stub_adapter.close = AsyncMock()
    stub_adapter.generate = AsyncMock(return_value=dummy_response)
    stub_adapter.has_context_memory = True

    with patch("lamia.engine.engine.create_adapter_from_config", return_value=stub_adapter), \
          patch.object(
              ValidationStrategy,
              "execute_with_retries",
              new=AsyncMock(return_value=dummy_response),
          ) as mock_execute, \
          patch('lamia.engine.engine.ValidatorRegistry') as MockRegistry, \
          patch('lamia.engine.engine.ValidationStrategy') as MockStrategy:
        
        mock_registry_instance = Mock()
        mock_registry_instance.get_registry = AsyncMock(return_value={"html": Mock()})
        MockRegistry.return_value = mock_registry_instance
        
        mock_strategy_instance = Mock()
        mock_strategy_instance.execute_with_retries = mock_execute
        MockStrategy.return_value = mock_strategy_instance
        
        engine = LamiaEngine(config)
        await engine.start()

        response = await engine.generate("Hello, Lamia!")

        # ValidationStrategy.execute_with_retries should have been awaited exactly once
        mock_execute.assert_awaited_once()
        assert response == dummy_response

        await engine.stop()

@pytest.mark.asyncio
async def test_generate_propagates_errors_from_execute_with_retries():
    """If ValidationStrategy.execute_with_retries raises, LamiaEngine.generate should propagate the error."""
    config = {
        "default_model": "openai",
        "models": {"openai": {"default_model": "gpt-3.5-turbo"}},
        "api_keys": {"openai": "test-key"},
        "validation": {
            "enabled": True,
            "max_retries": 2,
            "fallback_models": [],
            "validators": [{"type": "html"}],
        },
    }

    stub_adapter = MagicMock()
    stub_adapter.initialize = AsyncMock()
    stub_adapter.close = AsyncMock()
    stub_adapter.generate = AsyncMock()
    stub_adapter.has_context_memory = True

    with patch("lamia.engine.engine.create_adapter_from_config", return_value=stub_adapter), \
          patch.object(
              ValidationStrategy,
              "execute_with_retries",
              new=AsyncMock(side_effect=RuntimeError("Boom")),
          ) as mock_execute, \
          patch('lamia.engine.engine.ValidatorRegistry') as MockRegistry, \
          patch('lamia.engine.engine.ValidationStrategy') as MockStrategy:
        
        mock_registry_instance = Mock()
        mock_registry_instance.get_registry = AsyncMock(return_value={"html": Mock()})
        MockRegistry.return_value = mock_registry_instance
        
        mock_strategy_instance = Mock()
        mock_strategy_instance.execute_with_retries = mock_execute
        MockStrategy.return_value = mock_strategy_instance
        
        engine = LamiaEngine(config)
        await engine.start()

        with pytest.raises(RuntimeError):
            await engine.generate("This will fail")

        mock_execute.assert_awaited_once()
        await engine.stop()

@pytest.mark.asyncio
async def test_context_manager_success():
    """Test using LamiaEngine as async context manager successfully"""
    config = {
        "default_model": "openai",
        "models": {"openai": {"default_model": "gpt-3.5-turbo"}},
        "api_keys": {"openai": "test-key"}
    }
    
    mock_adapter = Mock()
    mock_adapter.initialize = AsyncMock()
    mock_adapter.close = AsyncMock()
    
    with patch('lamia.engine.engine.create_adapter_from_config', return_value=mock_adapter):
        async with LamiaEngine(config) as engine:
            assert engine.adapter == mock_adapter
            mock_adapter.initialize.assert_called_once()
        
        mock_adapter.close.assert_called_once()

@pytest.mark.asyncio
async def test_context_manager_start_failure():
    """Test context manager when start fails"""
    config = {
        "default_model": "openai",
        "models": {"openai": {"default_model": "gpt-3.5-turbo"}},
        "api_keys": {"openai": "test-key"}
    }
    
    mock_adapter = Mock()
    mock_adapter.initialize = AsyncMock(side_effect=RuntimeError("Start failed"))
    mock_adapter.close = AsyncMock()
    
    with patch('lamia.engine.engine.create_adapter_from_config', return_value=mock_adapter):
        # The engine.start() method catches exceptions and returns False, so we need to check the result
        engine = LamiaEngine(config)
        result = await engine.start()
        assert result is False

@pytest.mark.asyncio
async def test_context_manager_exception_in_body():
    """Test context manager when exception occurs in body"""
    config = {
        "default_model": "openai",
        "models": {"openai": {"default_model": "gpt-3.5-turbo"}},
        "api_keys": {"openai": "test-key"}
    }
    
    mock_adapter = Mock()
    mock_adapter.initialize = AsyncMock()
    mock_adapter.close = AsyncMock()
    
    with patch('lamia.engine.engine.create_adapter_from_config', return_value=mock_adapter):
        with pytest.raises(ValueError):
            async with LamiaEngine(config) as engine:
                raise ValueError("Test error")
        
        # Should still clean up
        mock_adapter.close.assert_called_once()

@pytest.mark.asyncio
async def test_generate_missing_model_config():
    """Test generate method when model config is missing"""
    config = {
        "default_model": "openai",
        "models": {}  # Missing model config
    }
    engine = LamiaEngine(config)
    
    with pytest.raises(ValueError):
        await engine.generate("Hello")

@pytest.mark.asyncio
async def test_generate_adapter_initialization_failure():
    """Test generate method when adapter initialization fails"""
    config = {
        "default_model": "ollama",
        "models": {"ollama": {"default_model": "llama2"}}
    }
    engine = LamiaEngine(config)
    
    mock_adapter = Mock()
    mock_adapter.initialize = AsyncMock(side_effect=RuntimeError("Init failed"))
    
    with patch('lamia.engine.engine.create_adapter_from_config', return_value=mock_adapter):
        with pytest.raises(RuntimeError):
            await engine.generate("Hello") 