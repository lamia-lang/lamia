"""Tests for LLMManager."""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import os
from lamia.engine.managers.llm.llm_manager import LLMManager
from lamia.engine.config_provider import ConfigProvider
from lamia.engine.managers.llm.providers import ProviderRegistry
from lamia._internal_types.model_retry import ModelWithRetries
from lamia import LLMModel
from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse
from lamia.validation.base import ValidationResult, BaseValidator, TrackingContext
from lamia.interpreter.command_types import CommandType
from lamia.interpreter.commands import LLMCommand
from lamia.errors import MissingAPIKeysError
from lamia.adapters.retry.factory import RetriableAdapterFactory


def _create_mock_adapter(provider_name: str, is_remote: bool = True):
    """Helper to create a properly configured mock adapter."""
    mock_adapter_class = MagicMock()
    mock_adapter_class.name.return_value = provider_name
    mock_adapter_class.is_remote.return_value = is_remote
    
    # Create mock instance that will be returned when adapter_class() is called
    mock_instance = MagicMock()
    mock_instance.async_initialize = AsyncMock()
    mock_adapter_class.return_value = mock_instance
    
    return mock_adapter_class, mock_instance


class TestLLMManagerInitialization:
    """Test LLMManager initialization."""
    
    def test_initialization_with_valid_config(self):
        """Test initialization with valid config."""
        mock_model = Mock(spec=LLMModel)
        mock_model.get_provider_name.return_value = "openai"
        mock_model_with_retries = Mock(spec=ModelWithRetries)
        mock_model_with_retries.model = mock_model
        
        config_dict = {'model_chain': [mock_model_with_retries]}
        config_provider = ConfigProvider(config_dict)
        
        with patch.object(LLMManager, '_check_all_required_providers'):
            with patch.object(LLMManager, '_check_all_required_api_keys'):
                manager = LLMManager(config_provider)
        
        assert manager.config_provider == config_provider
        assert isinstance(manager.provider_registry, ProviderRegistry)
        assert manager._adapter_cache == {}
    
    def test_initialization_calls_api_key_check(self):
        """Test that initialization checks API keys."""
        mock_model = Mock(spec=LLMModel)
        mock_model.get_provider_name.return_value = "openai"
        mock_model_with_retries = Mock(spec=ModelWithRetries)
        mock_model_with_retries.model = mock_model
        
        config_dict = {'model_chain': [mock_model_with_retries]}
        config_provider = ConfigProvider(config_dict)
        
        with patch.object(LLMManager, '_check_all_required_providers'):
            with patch.object(LLMManager, '_check_all_required_api_keys') as mock_check:
                LLMManager(config_provider)
            
            mock_check.assert_called_once()
    
    def test_initialization_rejects_unknown_provider(self):
        """Test that initialization rejects unknown providers."""
        mock_model = Mock(spec=LLMModel)
        mock_model.get_provider_name.return_value = "unknown_provider"
        mock_model_with_retries = Mock(spec=ModelWithRetries)
        mock_model_with_retries.model = mock_model
        
        config_dict = {'model_chain': [mock_model_with_retries]}
        config_provider = ConfigProvider(config_dict)
        
        with pytest.raises(ValueError, match="not supported"):
            LLMManager(config_provider)
    
    def test_get_needed_providers_single_model(self):
        """Test getting needed providers with single model."""
        mock_model = Mock(spec=LLMModel)
        mock_model.get_provider_name.return_value = "openai"
        mock_model_with_retries = Mock(spec=ModelWithRetries)
        mock_model_with_retries.model = mock_model
        
        config_dict = {'model_chain': [mock_model_with_retries]}
        config_provider = ConfigProvider(config_dict)
        
        with patch.object(LLMManager, '_check_all_required_providers'):
            with patch.object(LLMManager, '_check_all_required_api_keys'):
                manager = LLMManager(config_provider)
        
        needed = manager._get_needed_providers()
        assert needed == {"openai"}
    
    def test_get_needed_providers_multiple_models(self):
        """Test getting needed providers with multiple models."""
        mock_model1 = Mock(spec=LLMModel)
        mock_model1.get_provider_name.return_value = "openai"
        mock_model_with_retries1 = Mock(spec=ModelWithRetries)
        mock_model_with_retries1.model = mock_model1
        
        mock_model2 = Mock(spec=LLMModel)
        mock_model2.get_provider_name.return_value = "anthropic"
        mock_model_with_retries2 = Mock(spec=ModelWithRetries)
        mock_model_with_retries2.model = mock_model2
        
        config_dict = {'model_chain': [mock_model_with_retries1, mock_model_with_retries2]}
        config_provider = ConfigProvider(config_dict)
        
        with patch.object(LLMManager, '_check_all_required_providers'):
            with patch.object(LLMManager, '_check_all_required_api_keys'):
                manager = LLMManager(config_provider)
        
        needed = manager._get_needed_providers()
        assert needed == {"openai", "anthropic"}
    
    def test_get_needed_providers_no_model_chain(self):
        """Test getting needed providers with no model chain."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        
        with patch.object(LLMManager, '_check_all_required_providers'):
            with patch.object(LLMManager, '_check_all_required_api_keys'):
                manager = LLMManager(config_provider)
        
        needed = manager._get_needed_providers()
        assert needed == set()


class TestLLMManagerAPIKeyResolution:
    """Test API key resolution logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        
        with patch.object(LLMManager, '_check_all_required_api_keys'):
            self.manager = LLMManager(self.config_provider)
    
    @patch('lamia.adapters.llm.lamia_adapter.LamiaAdapter.get_supported_providers')
    def test_resolve_api_key_lamia_provider_config_key(self, mock_supported):
        """Test resolving API key for Lamia-supported provider with config key."""
        mock_supported.return_value = ["openai"]
        
        self.config_provider._config['api_keys'] = {'lamia': 'lamia-key'}
        
        result = self.manager._resolve_api_key("openai")
        assert result == ("lamia-key", True)
    
    @patch('lamia.adapters.llm.lamia_adapter.LamiaAdapter.get_supported_providers')
    def test_resolve_api_key_lamia_provider_env_key(self, mock_supported):
        """Test resolving API key for Lamia-supported provider with env key."""
        mock_supported.return_value = ["openai"]
        
        with patch.object(self.manager.provider_registry, 'get_api_key_from_env') as mock_env:
            mock_env.side_effect = lambda provider: "lamia-env-key" if provider == "lamia" else None
            
            result = self.manager._resolve_api_key("openai")
            assert result == ("lamia-env-key", True)
    
    @patch('lamia.adapters.llm.lamia_adapter.LamiaAdapter.get_supported_providers')
    def test_resolve_api_key_provider_config_key(self, mock_supported):
        """Test resolving API key with provider-specific config key."""
        mock_supported.return_value = ["openai"]
        
        self.config_provider._config['api_keys'] = {'openai': 'openai-key'}
        
        result = self.manager._resolve_api_key("openai")
        assert result == ("openai-key", False)
    
    @patch('lamia.adapters.llm.lamia_adapter.LamiaAdapter.get_supported_providers')
    def test_resolve_api_key_provider_env_key(self, mock_supported):
        """Test resolving API key with provider-specific env key."""
        mock_supported.return_value = ["openai"]
        
        with patch.object(self.manager.provider_registry, 'get_api_key_from_env') as mock_env:
            mock_env.side_effect = lambda provider: "openai-env-key" if provider == "openai" else None
            
            result = self.manager._resolve_api_key("openai")
            assert result == ("openai-env-key", False)
    
    def test_resolve_api_key_no_key_needed(self):
        """Test resolving API key for provider that doesn't need one."""
        with patch.object(self.manager.provider_registry, 'get_env_var_names') as mock_env_vars:
            mock_env_vars.return_value = []  # No env vars needed
            
            result = self.manager._resolve_api_key("local_provider")
            assert result == (None, False)
    
    def test_resolve_api_key_missing_required(self):
        """Test resolving API key when required key is missing."""
        with patch.object(self.manager.provider_registry, 'get_api_key_from_env', return_value=None):
            with patch.object(self.manager.provider_registry, 'get_env_var_names') as mock_env_vars:
                mock_env_vars.return_value = ["OPENAI_API_KEY"]
                
                with pytest.raises(MissingAPIKeysError):
                    self.manager._resolve_api_key("openai")


class TestLLMManagerAPIKeyChecking:
    """Test API key checking during initialization."""
    
    def test_check_all_required_api_keys_success(self):
        """Test successful API key checking."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        
        with patch.object(LLMManager, '_get_needed_providers') as mock_needed:
            mock_needed.return_value = {"openai"}
            
            with patch.object(LLMManager, '_resolve_api_key') as mock_resolve:
                mock_resolve.return_value = ("test-key", False)
                
                # Should not raise
                manager = LLMManager(config_provider)
                mock_resolve.assert_called_once_with("openai")
    
    def test_check_all_required_api_keys_missing(self):
        """Test API key checking with missing keys."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        
        with patch.object(LLMManager, '_get_needed_providers') as mock_needed:
            mock_needed.return_value = {"openai", "anthropic"}
            
            with patch.object(LLMManager, '_resolve_api_key') as mock_resolve:
                mock_resolve.side_effect = [
                    ("test-key", False),  # openai succeeds
                    MissingAPIKeysError([("anthropic", "ANTHROPIC_API_KEY")])  # anthropic fails
                ]
                
                with pytest.raises(MissingAPIKeysError) as exc_info:
                    LLMManager(config_provider)
                
                assert ("anthropic", "ANTHROPIC_API_KEY") in exc_info.value.missing


class TestLLMManagerAdapterCreation:
    """Test adapter creation and caching."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        
        with patch.object(LLMManager, '_check_all_required_api_keys'):
            self.manager = LLMManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_create_adapter_from_config_remote_with_retries(self):
        """Test creating remote adapter with retries."""
        mock_model = Mock(spec=LLMModel)
        mock_model.get_provider_name.return_value = "openai"
        
        mock_adapter_class = Mock()
        mock_adapter_class.is_remote.return_value = True
        mock_adapter = Mock(spec=BaseLLMAdapter)
        mock_adapter_class.return_value = mock_adapter
        
        with patch.object(self.manager, '_resolve_api_key') as mock_resolve:
            mock_resolve.return_value = ("test-key", False)
            
            with patch.object(self.manager.provider_registry, 'get_adapter_class') as mock_get_class:
                mock_get_class.return_value = mock_adapter_class
                
                with patch.object(RetriableAdapterFactory, 'create_llm_adapter') as mock_factory:
                    mock_retriable = Mock(spec=BaseLLMAdapter)
                    mock_factory.return_value = mock_retriable
                    
                    result = await self.manager.create_adapter_from_config(mock_model)
                    
                    # Verify adapter creation
                    mock_adapter_class.assert_called_once_with(api_key="test-key")
                    mock_adapter.async_initialize.assert_called_once()
                    
                    # Verify retry wrapping
                    mock_factory.assert_called_once()
                    
                    # Verify caching
                    assert self.manager._adapter_cache["openai"] == mock_retriable
                    assert result == mock_retriable
    
    @pytest.mark.asyncio
    async def test_create_adapter_from_config_local_without_retries(self):
        """Test creating local adapter without retries."""
        mock_model = Mock(spec=LLMModel)
        mock_model.get_provider_name.return_value = "local_model"
        
        mock_adapter_class = Mock()
        mock_adapter_class.is_remote.return_value = False
        mock_adapter = Mock(spec=BaseLLMAdapter)
        mock_adapter_class.return_value = mock_adapter
        
        with patch.object(self.manager, '_resolve_api_key') as mock_resolve:
            mock_resolve.return_value = (None, False)
            
            with patch.object(self.manager.provider_registry, 'get_adapter_class') as mock_get_class:
                mock_get_class.return_value = mock_adapter_class
                
                result = await self.manager.create_adapter_from_config(mock_model, with_retries=False)
                
                # Verify adapter creation
                mock_adapter_class.assert_called_once_with()
                mock_adapter.async_initialize.assert_called_once()
                
                # Should return raw adapter without caching when with_retries=False
                assert result == mock_adapter
    
    @pytest.mark.asyncio
    async def test_create_adapter_from_config_caching(self):
        """Test adapter caching works correctly."""
        mock_model = Mock(spec=LLMModel)
        mock_model.get_provider_name.return_value = "openai"
        
        # Pre-populate cache
        mock_cached_adapter = Mock(spec=BaseLLMAdapter)
        self.manager._adapter_cache["openai"] = mock_cached_adapter
        
        result = await self.manager.create_adapter_from_config(mock_model)
        
        # Should return cached adapter without creating new one
        assert result == mock_cached_adapter
    
    @pytest.mark.asyncio
    async def test_create_adapter_from_config_lamia_adapter(self):
        """Test creating adapter using LamiaAdapter."""
        mock_model = Mock(spec=LLMModel)
        mock_model.get_provider_name.return_value = "openai"
        
        with patch.object(self.manager, '_resolve_api_key') as mock_resolve:
            mock_resolve.return_value = ("lamia-key", True)  # use_lamia_adapter = True
            
            with patch('lamia.engine.managers.llm.llm_manager.LamiaAdapter') as mock_lamia_class:
                mock_lamia_adapter = Mock(spec=BaseLLMAdapter)
                mock_lamia_class.return_value = mock_lamia_adapter
                mock_lamia_class.is_remote.return_value = True
                
                with patch.object(RetriableAdapterFactory, 'create_llm_adapter') as mock_factory:
                    mock_retriable = Mock(spec=BaseLLMAdapter)
                    mock_factory.return_value = mock_retriable
                    
                    result = await self.manager.create_adapter_from_config(mock_model)
                    
                    # Should use LamiaAdapter
                    mock_lamia_class.assert_called_once_with(api_key="lamia-key")


class TestLLMManagerExecution:
    """Test LLMManager execution methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        
        with patch.object(LLMManager, '_check_all_required_api_keys'):
            self.manager = LLMManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_execute_basic_command(self):
        """Test basic command execution."""
        command = LLMCommand(prompt="Hello world")
        
        mock_result = ValidationResult(
            is_valid=True,
            raw_text="Hi there!",
            validated_text="Hi there!",
            execution_context=Mock()
        )
        
        with patch.object(self.manager, '_execute_with_retries') as mock_execute:
            mock_execute.return_value = mock_result
            
            with patch.object(self.manager, '_inject_file_references') as mock_inject:
                mock_inject.return_value = "Hello world"
                
                result = await self.manager.execute(command)
                
                assert result == mock_result
                mock_inject.assert_called_once_with("Hello world")
                mock_execute.assert_called_once_with(prompt="Hello world", validator=None)
    
    @pytest.mark.asyncio
    async def test_execute_with_validator(self):
        """Test command execution with validator."""
        command = LLMCommand(prompt="Hello world")
        validator = Mock(spec=BaseValidator)
        
        mock_result = ValidationResult(
            is_valid=True,
            raw_text="Hi there!",
            validated_text="Hi there!",
            execution_context=Mock()
        )
        
        with patch.object(self.manager, '_execute_with_retries') as mock_execute:
            mock_execute.return_value = mock_result
            
            with patch.object(self.manager, '_inject_file_references') as mock_inject:
                mock_inject.return_value = "Hello world"
                
                result = await self.manager.execute(command, validator=validator)
                
                assert result == mock_result
                mock_execute.assert_called_once_with(prompt="Hello world", validator=validator)
    
    def test_inject_file_references_with_context(self):
        """Test file reference injection with active context."""
        mock_context = Mock()
        mock_context.inject_file_references.return_value = "Hello world with files"
        
        with patch('lamia.engine.managers.llm.llm_manager.get_active_files_context') as mock_get_context:
            mock_get_context.return_value = mock_context
            
            result = self.manager._inject_file_references("Hello world")
            
            assert result == "Hello world with files"
            mock_context.inject_file_references.assert_called_once_with("Hello world")
    
    def test_inject_file_references_without_context(self):
        """Test file reference injection without active context."""
        with patch('lamia.engine.managers.llm.llm_manager.get_active_files_context') as mock_get_context:
            mock_get_context.return_value = None
            
            result = self.manager._inject_file_references("Hello world")
            
            assert result == "Hello world"


class TestLLMManagerExecutionWithRetries:
    """Test execution with retry and fallback logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_model1 = Mock(spec=LLMModel)
        self.mock_model1.name = "gpt-4"
        self.mock_model1.get_provider_name.return_value = "openai"
        self.mock_model_with_retries1 = Mock(spec=ModelWithRetries)
        self.mock_model_with_retries1.model = self.mock_model1
        self.mock_model_with_retries1.retries = 3
        
        self.mock_model2 = Mock(spec=LLMModel)
        self.mock_model2.name = "claude-3"
        self.mock_model2.get_provider_name.return_value = "anthropic"
        self.mock_model_with_retries2 = Mock(spec=ModelWithRetries)
        self.mock_model_with_retries2.model = self.mock_model2
        self.mock_model_with_retries2.retries = 2
        
        config_dict = {'model_chain': [self.mock_model_with_retries1, self.mock_model_with_retries2]}
        self.config_provider = ConfigProvider(config_dict)
        
        with patch.object(LLMManager, '_check_all_required_providers'):
            with patch.object(LLMManager, '_check_all_required_api_keys'):
                self.manager = LLMManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_execute_with_retries_first_model_success(self):
        """Test execution succeeds with first model."""
        mock_validator = Mock(spec=BaseValidator)
        mock_validator.initial_hint = "Please be helpful"
        
        mock_result = ValidationResult(
            is_valid=True,
            raw_text="Success",
            validated_text="Success",
            execution_context=Mock()
        )
        
        # Mock adapter creation to bypass provider registry issues
        mock_adapter = Mock(spec=BaseLLMAdapter)
        self.manager._adapter_cache[self.mock_model1] = mock_adapter
        
        with patch.object(self.manager, '_generate_and_validate') as mock_generate:
            mock_generate.return_value = mock_result
            
            result = await self.manager._execute_with_retries("Hello", validator=mock_validator)
            
            assert result == mock_result
            mock_generate.assert_called_once()
            
            # Should call with hinted prompt
            call_args = mock_generate.call_args
            assert "Please be helpful" in call_args.kwargs['prompt']
            assert "Hello" in call_args.kwargs['prompt']
    
    @pytest.mark.asyncio
    async def test_execute_with_retries_fallback_to_second_model(self):
        """Test execution falls back to second model when first fails."""
        mock_result = ValidationResult(
            is_valid=True,
            raw_text="Success from second model",
            validated_text="Success from second model",
            execution_context=Mock()
        )
        
        mock_adapter1 = Mock(spec=BaseLLMAdapter)
        mock_adapter2 = Mock(spec=BaseLLMAdapter)
        
        with patch.object(self.manager, 'create_adapter_from_config') as mock_create:
            mock_create.side_effect = [mock_adapter1, mock_adapter2]
            
            with patch.object(self.manager, '_generate_and_validate') as mock_generate:
                mock_generate.side_effect = [None, mock_result]  # First model fails, second succeeds
                
                result = await self.manager._execute_with_retries("Hello")
                
                assert result == mock_result
                assert mock_generate.call_count == 2
    
    @pytest.mark.asyncio
    async def test_execute_with_retries_all_models_fail(self):
        """Test execution when all models fail."""
        mock_adapter1 = Mock(spec=BaseLLMAdapter)
        mock_adapter2 = Mock(spec=BaseLLMAdapter)
        
        with patch.object(self.manager, 'create_adapter_from_config') as mock_create:
            mock_create.side_effect = [mock_adapter1, mock_adapter2]
            
            with patch.object(self.manager, '_generate_and_validate') as mock_generate:
                mock_generate.return_value = None  # All models fail
                
                with pytest.raises(ValueError, match="All models failed"):
                    await self.manager._execute_with_retries("Hello")
    
    @pytest.mark.asyncio
    async def test_execute_with_retries_uses_cached_adapters(self):
        """Test that cached adapters are reused."""
        mock_adapter1 = Mock(spec=BaseLLMAdapter)
        self.manager._adapter_cache[self.mock_model1] = mock_adapter1
        
        mock_result = ValidationResult(
            is_valid=True,
            raw_text="Success",
            validated_text="Success",
            execution_context=Mock()
        )
        
        with patch.object(self.manager, '_generate_and_validate') as mock_generate:
            mock_generate.return_value = mock_result
            
            with patch.object(self.manager, 'create_adapter_from_config') as mock_create:
                await self.manager._execute_with_retries("Hello")
                
                # Should not create new adapter since one is cached
                mock_create.assert_not_called()
                
                # Should use cached adapter
                call_args = mock_generate.call_args
                assert call_args.kwargs['adapter'] == mock_adapter1


class TestLLMManagerGenerateAndValidate:
    """Test generate and validate functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        
        with patch.object(LLMManager, '_check_all_required_api_keys'):
            self.manager = LLMManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_generate_and_validate_success_no_validator(self):
        """Test successful generation without validator."""
        mock_adapter = Mock(spec=BaseLLMAdapter)
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "gpt-4"
        
        mock_response = Mock(spec=LLMResponse)
        mock_response.text = "Generated response"
        mock_response.usage = {"tokens": 100}
        mock_response.model = "gpt-4"
        
        mock_adapter.generate.return_value = mock_response
        
        result = await self.manager._generate_and_validate(
            adapter=mock_adapter,
            model=mock_model,
            prompt="Hello"
        )
        
        assert result is not None
        assert result.is_valid is True
        assert result.raw_text == "Generated response"
        assert result.validated_text == "Generated response"
        assert result.execution_context is not None
        assert result.execution_context.data_provider_name == "gpt-4"
        assert result.execution_context.command_type == CommandType.LLM
    
    @pytest.mark.asyncio
    async def test_generate_and_validate_success_with_validator(self):
        """Test successful generation with validator."""
        mock_adapter = Mock(spec=BaseLLMAdapter)
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "gpt-4"
        
        mock_response = Mock(spec=LLMResponse)
        mock_response.text = "Generated response"
        mock_response.usage = {"tokens": 100}
        mock_response.model = "gpt-4"
        mock_adapter.generate.return_value = mock_response
        
        mock_validator = Mock(spec=BaseValidator)
        mock_validation_result = ValidationResult(
            is_valid=True,
            raw_text="Generated response",
            validated_text="Validated response",
            execution_context=Mock()
        )
        mock_validator.validate.return_value = mock_validation_result
        
        result = await self.manager._generate_and_validate(
            adapter=mock_adapter,
            model=mock_model,
            prompt="Hello",
            validator=mock_validator
        )
        
        assert result == mock_validation_result
        mock_validator.validate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_and_validate_validation_failures_with_retries(self):
        """Test validation failures with retries."""
        mock_adapter = Mock(spec=BaseLLMAdapter)
        mock_adapter.has_context_memory = False
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "gpt-4"
        
        mock_response = Mock(spec=LLMResponse)
        mock_response.text = "Generated response"
        mock_response.usage = {"tokens": 100}
        mock_response.model = "gpt-4"
        mock_adapter.generate.return_value = mock_response
        
        mock_validator = Mock(spec=BaseValidator)
        
        # First two attempts fail validation, third succeeds
        failed_result = ValidationResult(
            is_valid=False,
            raw_text="Generated response",
            validated_text=None,
            execution_context=Mock(),
            error_message="Validation failed",
            hint="Try again"
        )
        success_result = ValidationResult(
            is_valid=True,
            raw_text="Generated response",
            validated_text="Success",
            execution_context=Mock()
        )
        
        mock_validator.validate.side_effect = [failed_result, failed_result, success_result]
        
        result = await self.manager._generate_and_validate(
            adapter=mock_adapter,
            model=mock_model,
            prompt="Hello",
            validator=mock_validator,
            max_attempts=3
        )
        
        assert result == success_result
        assert mock_adapter.generate.call_count == 3
        assert mock_validator.validate.call_count == 3
    
    @pytest.mark.asyncio
    async def test_generate_and_validate_max_attempts_exhausted(self):
        """Test when all retry attempts are exhausted."""
        mock_adapter = Mock(spec=BaseLLMAdapter)
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "gpt-4"
        
        mock_response = Mock(spec=LLMResponse)
        mock_response.text = "Generated response"
        mock_response.usage = {"tokens": 100}
        mock_response.model = "gpt-4"
        mock_adapter.generate.return_value = mock_response
        
        mock_validator = Mock(spec=BaseValidator)
        failed_result = ValidationResult(
            is_valid=False,
            raw_text="Generated response",
            validated_text=None,
            execution_context=Mock(),
            error_message="Validation failed",
            hint="Try again"
        )
        mock_validator.validate.return_value = failed_result
        
        result = await self.manager._generate_and_validate(
            adapter=mock_adapter,
            model=mock_model,
            prompt="Hello",
            validator=mock_validator,
            max_attempts=2
        )
        
        assert result is None  # All attempts exhausted
        assert mock_adapter.generate.call_count == 2
    
    @pytest.mark.asyncio
    async def test_generate_and_validate_context_memory_retry_logic(self):
        """Test retry logic for adapters with context memory."""
        mock_adapter = Mock(spec=BaseLLMAdapter)
        mock_adapter.has_context_memory = True
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "gpt-4"
        
        mock_response = Mock(spec=LLMResponse)
        mock_response.text = "Generated response"
        mock_response.usage = {"tokens": 100}
        mock_response.model = "gpt-4"
        mock_adapter.generate.return_value = mock_response
        
        mock_validator = Mock(spec=BaseValidator)
        failed_result = ValidationResult(
            is_valid=False,
            raw_text="Generated response",
            validated_text=None,
            execution_context=Mock(),
            error_message="Validation failed",
            hint="Try again"
        )
        success_result = ValidationResult(
            is_valid=True,
            raw_text="Generated response",
            validated_text="Success",
            execution_context=Mock()
        )
        
        mock_validator.validate.side_effect = [failed_result, success_result]
        
        result = await self.manager._generate_and_validate(
            adapter=mock_adapter,
            model=mock_model,
            prompt="Original prompt",
            validator=mock_validator,
            max_attempts=2
        )
        
        assert result == success_result
        
        # Check retry prompts - with context memory, should only send retry message
        call_args_list = mock_adapter.generate.call_args_list
        assert len(call_args_list) == 2
        
        # First call with original prompt
        assert call_args_list[0][0][0] == "Original prompt"
        
        # Second call should be retry message only (not including original prompt)
        retry_prompt = call_args_list[1][0][0]
        assert "Validation failed" in retry_prompt
        assert "Try again" in retry_prompt
        assert "Original prompt" not in retry_prompt  # Should NOT include original with context memory


class TestLLMManagerCleanup:
    """Test LLMManager cleanup and resource management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        
        with patch.object(LLMManager, '_check_all_required_api_keys'):
            self.manager = LLMManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_close_cleans_up_adapters(self):
        """Test that close method cleans up all cached adapters."""
        mock_adapter1 = Mock(spec=BaseLLMAdapter)
        mock_adapter2 = Mock(spec=BaseLLMAdapter)
        
        self.manager._adapter_cache = {
            "adapter1": mock_adapter1,
            "adapter2": mock_adapter2
        }
        
        await self.manager.close()
        
        # All adapters should be closed
        mock_adapter1.close.assert_called_once()
        mock_adapter2.close.assert_called_once()
        
        # Cache should be cleared
        assert self.manager._adapter_cache == {}


class TestLLMManagerIntegration:
    """Test integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_full_execution_flow(self):
        """Test complete execution flow from command to result."""
        # Setup models
        mock_model = Mock(spec=LLMModel)
        mock_model.name = "gpt-4"
        mock_model.get_provider_name.return_value = "openai"
        mock_model_with_retries = Mock(spec=ModelWithRetries)
        mock_model_with_retries.model = mock_model
        mock_model_with_retries.retries = 2
        
        # Setup config
        config_dict = {
            'model_chain': [mock_model_with_retries],
            'api_keys': {'openai': 'test-key'}
        }
        config_provider = ConfigProvider(config_dict)
        
        # Create manager
        with patch.object(LLMManager, '_check_all_required_providers'):
            with patch.object(LLMManager, '_check_all_required_api_keys'):
                manager = LLMManager(config_provider)
        
        # Setup mocks
        mock_adapter_class = Mock()
        mock_adapter_class.is_remote.return_value = True
        mock_adapter = Mock(spec=BaseLLMAdapter)
        mock_adapter_class.return_value = mock_adapter
        
        mock_response = Mock(spec=LLMResponse)
        mock_response.text = "Hello there!"
        mock_response.usage = {"tokens": 50}
        mock_response.model = "gpt-4"
        mock_adapter.generate.return_value = mock_response
        
        # Setup validator
        mock_validator = Mock(spec=BaseValidator)
        mock_validator.initial_hint = "Be helpful"
        mock_validation_result = ValidationResult(
            is_valid=True,
            raw_text="Hello there!",
            validated_text="Hello there!",
            execution_context=Mock()
        )
        mock_validator.validate.return_value = mock_validation_result
        
        with patch.object(manager.provider_registry, 'get_adapter_class') as mock_get_class:
            mock_get_class.return_value = mock_adapter_class
            
            with patch.object(RetriableAdapterFactory, 'create_llm_adapter') as mock_factory:
                mock_retriable = Mock(spec=BaseLLMAdapter)
                mock_retriable.generate = mock_adapter.generate
                mock_factory.return_value = mock_retriable
                
                # Execute command
                command = LLMCommand(prompt="Say hello")
                result = await manager.execute(command, validator=mock_validator)
                
                # Verify result
                assert result == mock_validation_result
                
                # Verify adapter was created and cached
                assert "openai" in manager._adapter_cache
                
                # Verify prompt included hint
                call_args = mock_retriable.generate.call_args
                prompt = call_args[0][0]
                assert "Be helpful" in prompt
                assert "Say hello" in prompt

class TestLLMManagerEndToEnd:
    """End-to-end integration tests with real ConfigProvider."""

    def test_check_api_keys_direct(self):
        """Test check_api_key with direct OpenAI API key"""
        cm = _create_config_provider(
            [{"name": "openai", "max_retries": 3}, {"name": "anthropic", "max_retries": 2}],
            api_keys={"openai": "test-openai-key", "anthropic": "test-anthropic-key"}
        )
        
        manager = LLMManager(cm)
        assert manager._resolve_api_key("openai") == ("test-openai-key", False)
        assert manager._resolve_api_key("anthropic") == ("test-anthropic-key", False)

    def test_check_api_key_direct_does_not_override_lamia_proxy(self):
        """Test lamia proxy API key takes precedence over direct provider key"""
        cm = _create_config_provider(
            [{"name": "openai", "max_retries": 3}],
            api_keys={"openai": "direct-key", "lamia": "proxy-key"}
        )
        
        manager = LLMManager(cm)
        result = manager._resolve_api_key("openai")
        assert result == ("proxy-key", True)

    def test_check_api_key_env_fallback(self):
        """Test check_api_key falls back to environment variable"""
        cm = _create_config_provider([{"name": "openai", "max_retries": 3}])
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            manager = LLMManager(cm)
            result = manager._resolve_api_key("openai")
            assert result == ("env-key", False)

    def test_check_api_key_missing_raises_error(self):
        """Test check_api_key raises MissingAPIKeysError when key is missing"""
        cm = _create_config_provider([{"name": "openai", "max_retries": 3}])
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(MissingAPIKeysError) as exc_info:
                manager = LLMManager(cm)
            
            assert "openai" in str(exc_info.value)
            assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_check_api_key_unknown_provider(self):
        """Test check_api_key with unknown provider"""
        cm = _create_config_provider([{"name": "unknown", "max_retries": 3}])
        
        with pytest.raises(ValueError) as exc_info:
            manager = LLMManager(cm)

        assert "The following providers are not supported: unknown" in str(exc_info.value)

    def test_missing_api_keys_error_message_single(self):
        """Test MissingAPIKeysError with single missing key"""
        missing = [("openai", "OPENAI_API_KEY")]
        error = MissingAPIKeysError(missing)

        assert "openai" in str(error)
        assert "OPENAI_API_KEY" in str(error)
        assert error.missing == missing

    def test_missing_api_keys_error_message_multiple(self):
        """Test MissingAPIKeysError with multiple missing keys"""
        missing = [("openai", "OPENAI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")]
        error = MissingAPIKeysError(missing)

        assert "openai" in str(error)
        assert "anthropic" in str(error)
        assert "OPENAI_API_KEY" in str(error)
        assert "ANTHROPIC_API_KEY" in str(error)

    def test_check_all_required_api_keys_success(self):
        """Test check_all_required_api_keys with all keys present"""
        cm = _create_config_provider(
            [{"name": "openai", "max_retries": 3}, {"name": "anthropic", "max_retries": 2}],
            api_keys={"openai": "key1", "anthropic": "key2"}
        )
        
        manager = LLMManager(cm)
        # Should not raise any exception
        manager._check_all_required_api_keys({"openai", "anthropic"})

    def test_check_all_required_api_keys_lamia_proxy(self):
        """Test check_all_required_api_keys with lamia key as proxy"""
        cm = _create_config_provider(
            [{"name": "openai", "max_retries": 3}, {"name": "anthropic", "max_retries": 2}],
            api_keys={"lamia": "proxy-key"}
        )
        
        manager = LLMManager(cm)
        # Should not raise any exception
        manager._check_all_required_api_keys({"openai", "anthropic"})

    def test_check_all_required_api_keys_ollama_no_key_needed(self):
        """Test check_all_required_api_keys with ollama (no key needed)"""
        cm = _create_config_provider([{"name": "ollama", "max_retries": 3}])
        
        manager = LLMManager(cm)
        # Should not raise any exception
        manager._check_all_required_api_keys({"ollama"})

    @patch.dict(os.environ, {}, clear=True)
    def test_check_all_required_api_keys_missing_primary(self):
        """Test check_all_required_api_keys with missing primary model key"""
        cm = _create_config_provider([{"name": "openai", "max_retries": 3}])
        
        with pytest.raises(MissingAPIKeysError) as exc_info:
            manager = LLMManager(cm)
        
        assert "openai" in str(exc_info.value)

    @patch.dict(os.environ, {}, clear=True)
    def test_check_all_required_api_keys_missing_fallback(self):
        """Test check_all_required_api_keys with missing fallback model key"""
        cm = _create_config_provider(
            [{"name": "openai", "max_retries": 3}, {"name": "anthropic", "max_retries": 2}],
            api_keys={"openai": "key1"}
        )
        
        with pytest.raises(MissingAPIKeysError) as exc_info:
            manager = LLMManager(cm)
        
        assert "anthropic" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_openai(self):
        """Test create_adapter_from_config with OpenAI"""
        cm = _create_config_provider(
            [{"name": "openai:gpt-3.5-turbo", "max_retries": 3}],
            api_keys={"openai": "test-key"}
        )
        
        mock_adapter_class, mock_instance = _create_mock_adapter("openai", is_remote=True)
        with patch('lamia.engine.managers.llm.providers.OpenAIAdapter', mock_adapter_class):
            manager = LLMManager(cm)
            model = LLMModel(name="openai:gpt-3.5-turbo")
            result = await manager.create_adapter_from_config(model, with_retries=False)
            mock_adapter_class.assert_called_once_with(api_key="test-key")
            assert result == mock_instance

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_anthropic(self):
        """Test create_adapter_from_config with Anthropic"""
        cm = _create_config_provider(
            [{"name": "anthropic:claude-3-opus-20240229", "max_retries": 3}],
            api_keys={"anthropic": "test-key"}
        )
        
        mock_adapter_class, mock_instance = _create_mock_adapter("anthropic", is_remote=True)
        with patch('lamia.engine.managers.llm.providers.AnthropicAdapter', mock_adapter_class):
            manager = LLMManager(cm)
            model = LLMModel(name="anthropic:claude-3-opus-20240229")
            result = await manager.create_adapter_from_config(model, with_retries=False)
            mock_adapter_class.assert_called_once_with(api_key="test-key")
            assert result == mock_instance

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_ollama(self):
        """Test create_adapter_from_config with Ollama"""
        from lamia.adapters.llm.local import OllamaAdapter
        
        cm = _create_config_provider(
            [{"name": "ollama:llama2", "max_retries": 3}],
            providers={"ollama": {"default_model": "llama2"}}
        )
        
        with patch.object(OllamaAdapter, '_start_ollama_service', return_value=True):
            manager = LLMManager(cm)
            model = LLMModel(name="ollama:llama2")
            result = await manager.create_adapter_from_config(model, with_retries=False)
            assert isinstance(result, OllamaAdapter)
            assert result.base_url == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_with_different_model(self):
        """Test create_adapter_from_config with different model in chain"""
        cm = _create_config_provider(
            [{"name": "openai:gpt-3.5-turbo", "max_retries": 3},
             {"name": "anthropic:claude-3-opus-20240229", "max_retries": 2}],
            api_keys={"openai": "key1", "anthropic": "key2"}
        )
        
        mock_openai_class, mock_openai_instance = _create_mock_adapter("openai", is_remote=True)
        mock_anthropic_class, mock_anthropic_instance = _create_mock_adapter("anthropic", is_remote=True)
        
        with patch('lamia.engine.managers.llm.providers.OpenAIAdapter', mock_openai_class):
            with patch('lamia.engine.managers.llm.providers.AnthropicAdapter', mock_anthropic_class):
                manager = LLMManager(cm)
                model = LLMModel(name="anthropic:claude-3-opus-20240229")
                result = await manager.create_adapter_from_config(model, with_retries=False)
                mock_anthropic_class.assert_called_once_with(api_key="key2")
                assert result == mock_anthropic_instance

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_unsupported_model(self):
        """Test create_adapter_from_config with unsupported model"""
        cm = _create_config_provider([{"name": "unsupported:some-model", "max_retries": 3}])
        
        with pytest.raises(ValueError, match="not supported"):
            manager = LLMManager(cm)

    @pytest.mark.asyncio
    async def test_create_adapter_from_config_missing_api_key(self):
        """Test create_adapter_from_config with missing API key - should raise during init"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(MissingAPIKeysError):
                cm = _create_config_provider([{"name": "openai:gpt-3.5-turbo", "max_retries": 3}])
                manager = LLMManager(cm)

    @pytest.mark.asyncio
    async def test_lamia_api_key_from_env(self, monkeypatch):
        """Test that LAMIA_API_KEY from env is used as proxy"""
        monkeypatch.setenv("LAMIA_API_KEY", "env-lamia-key")
        cm = _create_config_provider([{"name": "openai:gpt-3.5-turbo", "max_retries": 3}])
        
        mock_openai_class, _ = _create_mock_adapter("openai", is_remote=True)
        mock_lamia_class, mock_lamia_instance = _create_mock_adapter("lamia", is_remote=True)
        mock_lamia_class.get_supported_providers.return_value = {"openai", "anthropic"}
        
        with patch('lamia.engine.managers.llm.providers.OpenAIAdapter', mock_openai_class):
            with patch('lamia.engine.managers.llm.llm_manager.LamiaAdapter', mock_lamia_class):
                manager = LLMManager(cm)
                model = LLMModel(name="openai:gpt-3.5-turbo")
                result = await manager.create_adapter_from_config(model, with_retries=False)
                # The adapter should have been created using the proxy key from the env variable
                mock_lamia_class.assert_called_once_with(api_key="env-lamia-key")
                assert result == mock_lamia_instance
        
        monkeypatch.delenv("LAMIA_API_KEY", raising=False)

    @pytest.mark.asyncio
    async def test_ollama_adapter_extended_config(self):
        """Test Ollama adapter with extended configuration"""
        from lamia.adapters.llm.local import OllamaAdapter
        
        cm = _create_config_provider(
            [{"name": "ollama:llama2", "max_retries": 3}],
            providers={
                "ollama": {
                    "default_model": "llama2",
                    "base_url": "http://localhost:11434",
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    "context_size": 4096,
                    "num_ctx": 4096,
                    "num_gpu": 50,
                    "num_thread": 8,
                    "repeat_penalty": 1.1,
                    "top_k": 40,
                    "top_p": 0.9
                }
            }
        )
        with patch.object(OllamaAdapter, '_start_ollama_service', return_value=True):
            manager = LLMManager(cm)
            model = LLMModel(name="ollama:llama2")
            adapter = await manager.create_adapter_from_config(model, with_retries=False)
            assert isinstance(adapter, OllamaAdapter)
            assert adapter.base_url == "http://localhost:11434"


def _create_config_provider(model_chain_specs, api_keys=None, providers=None):
    """Helper to create ConfigProvider with proper ModelWithRetries objects."""
    model_chain = []
    for spec in model_chain_specs:
        if isinstance(spec, dict):
            model_name = spec["name"]
            max_retries = spec.get("max_retries", 1)
        else:
            model_name = spec
            max_retries = 1
        
        model = LLMModel(name=model_name)
        model_chain.append(ModelWithRetries(model, max_retries))
    
    config = {
        "model_chain": model_chain,
        "api_keys": api_keys or {},
        "providers": providers or {}
    }
    return ConfigProvider(config)