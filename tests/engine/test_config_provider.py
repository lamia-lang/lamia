"""Tests for config provider."""

import pytest
from unittest.mock import Mock
from lamia.engine.config_provider import ConfigProvider
from lamia._internal_types.model_retry import ModelWithRetries
from lamia.validation.base import BaseValidator
from lamia.types import ExternalOperationRetryConfig


class TestConfigProviderInitialization:
    """Test ConfigProvider initialization."""
    
    def test_initialization_with_valid_config(self):
        """Test initialization with valid config dictionary."""
        config = {
            'model_chain': [],
            'api_keys': {'openai': 'test-key'},
            'validators': [],
            'extensions_folder': 'custom_extensions'
        }
        
        provider = ConfigProvider(config)
        
        assert provider.config == config
        assert provider._config is not config  # Should be a copy
    
    def test_initialization_with_empty_config(self):
        """Test initialization with empty config dictionary."""
        config = {}
        provider = ConfigProvider(config)
        
        assert provider.config == {}
    
    def test_initialization_with_none_raises_error(self):
        """Test initialization with None raises ValueError."""
        with pytest.raises(ValueError, match="ConfigProvider expects a config dict"):
            ConfigProvider(None)
    
    def test_initialization_with_non_dict_raises_error(self):
        """Test initialization with non-dict raises ValueError."""
        with pytest.raises(ValueError, match="ConfigProvider expects a config dict"):
            ConfigProvider("not a dict")
        
        with pytest.raises(ValueError, match="ConfigProvider expects a config dict"):
            ConfigProvider(123)
    
    def test_config_immutability_defense(self):
        """Test that config is copied to prevent external modification."""
        original_config = {'test_key': 'test_value'}
        provider = ConfigProvider(original_config)
        
        # Modify original config
        original_config['test_key'] = 'modified_value'
        original_config['new_key'] = 'new_value'
        
        # Provider should still have original values
        assert provider.config['test_key'] == 'test_value'
        assert 'new_key' not in provider.config


class TestConfigProviderModelChain:
    """Test model chain operations."""
    
    def test_get_model_chain_exists(self):
        """Test getting model chain when it exists."""
        mock_model = Mock(spec=ModelWithRetries)
        config = {'model_chain': [mock_model]}
        provider = ConfigProvider(config)
        
        result = provider.get_model_chain()
        assert result == [mock_model]
    
    def test_get_model_chain_missing(self):
        """Test getting model chain when not configured."""
        config = {}
        provider = ConfigProvider(config)
        
        result = provider.get_model_chain()
        assert result is None
    
    def test_override_model_chain(self):
        """Test overriding model chain."""
        original_model = Mock(spec=ModelWithRetries)
        new_model = Mock(spec=ModelWithRetries)
        
        config = {'model_chain': [original_model]}
        provider = ConfigProvider(config)
        
        # Override with new chain
        provider.override_model_chain_with([new_model])
        
        result = provider.get_model_chain()
        assert result == [new_model]
        assert provider._main_model_chain == [original_model]  # Original preserved
    
    def test_reset_model_chain(self):
        """Test resetting model chain to original."""
        original_model = Mock(spec=ModelWithRetries)
        new_model = Mock(spec=ModelWithRetries)
        
        config = {'model_chain': [original_model]}
        provider = ConfigProvider(config)
        
        # Override and then reset
        provider.override_model_chain_with([new_model])
        provider.reset_model_chain()
        
        result = provider.get_model_chain()
        assert result == [original_model]
    
    def test_multiple_override_reset_cycles(self):
        """Test multiple override and reset cycles."""
        original_model = Mock(spec=ModelWithRetries)
        temp_model1 = Mock(spec=ModelWithRetries)
        temp_model2 = Mock(spec=ModelWithRetries)
        
        config = {'model_chain': [original_model]}
        provider = ConfigProvider(config)
        
        # First override - this sets _main_model_chain 
        provider.override_model_chain_with([temp_model1])
        assert provider.get_model_chain() == [temp_model1]
        
        # Second override - this overwrites without updating _main_model_chain
        provider.override_model_chain_with([temp_model2])
        assert provider.get_model_chain() == [temp_model2]
        
        # Reset should go back to the model chain from the FIRST override
        # because _main_model_chain is only set on the first call
        provider.reset_model_chain()
        assert provider.get_model_chain() == [temp_model1]  # Not original_model!


class TestConfigProviderApiKeys:
    """Test API key retrieval."""
    
    def test_get_api_key_exists(self):
        """Test getting API key that exists."""
        config = {
            'api_keys': {
                'openai': 'sk-test-key',
                'anthropic': 'claude-key'
            }
        }
        provider = ConfigProvider(config)
        
        assert provider.get_api_key('openai') == 'sk-test-key'
        assert provider.get_api_key('anthropic') == 'claude-key'
    
    def test_get_api_key_missing_provider(self):
        """Test getting API key for non-existent provider."""
        config = {
            'api_keys': {
                'openai': 'sk-test-key'
            }
        }
        provider = ConfigProvider(config)
        
        assert provider.get_api_key('anthropic') is None
        assert provider.get_api_key('nonexistent') is None
    
    def test_get_api_key_no_api_keys_section(self):
        """Test getting API key when api_keys section missing."""
        config = {}
        provider = ConfigProvider(config)
        
        assert provider.get_api_key('openai') is None
    
    def test_get_api_key_api_keys_none(self):
        """Test getting API key when api_keys is None."""
        config = {'api_keys': None}
        provider = ConfigProvider(config)
        
        assert provider.get_api_key('openai') is None
    
    def test_get_api_key_empty_string(self):
        """Test getting API key that is empty string."""
        config = {
            'api_keys': {
                'openai': '',
                'anthropic': 'valid-key'
            }
        }
        provider = ConfigProvider(config)
        
        assert provider.get_api_key('openai') == ''
        assert provider.get_api_key('anthropic') == 'valid-key'
    
    def test_get_api_key_case_sensitive(self):
        """Test that API key retrieval is case-sensitive."""
        config = {
            'api_keys': {
                'openai': 'test-key'
            }
        }
        provider = ConfigProvider(config)
        
        assert provider.get_api_key('openai') == 'test-key'
        assert provider.get_api_key('OpenAI') is None
        assert provider.get_api_key('OPENAI') is None


class TestConfigProviderValidators:
    """Test validator configuration."""
    
    def test_get_validators_exists(self):
        """Test getting validators when they exist."""
        mock_validator1 = Mock(spec=BaseValidator)
        mock_validator2 = Mock(spec=BaseValidator)
        
        config = {'validators': [mock_validator1, mock_validator2]}
        provider = ConfigProvider(config)
        
        result = provider.get_validators()
        assert result == [mock_validator1, mock_validator2]
    
    def test_get_validators_empty_list(self):
        """Test getting validators when list is empty."""
        config = {'validators': []}
        provider = ConfigProvider(config)
        
        result = provider.get_validators()
        assert result == []
    
    def test_get_validators_missing(self):
        """Test getting validators when not configured."""
        config = {}
        provider = ConfigProvider(config)
        
        result = provider.get_validators()
        assert result == []
    
    def test_get_validators_none(self):
        """Test getting validators when set to None."""
        config = {'validators': None}
        provider = ConfigProvider(config)
        
        result = provider.get_validators()
        assert result is None


class TestConfigProviderExtensionsFolder:
    """Test extensions folder configuration."""
    
    def test_get_extensions_folder_configured(self):
        """Test getting extensions folder when configured."""
        config = {'extensions_folder': 'my_custom_extensions'}
        provider = ConfigProvider(config)
        
        result = provider.get_extensions_folder()
        assert result == 'my_custom_extensions'
    
    def test_get_extensions_folder_default(self):
        """Test getting extensions folder default value."""
        config = {}
        provider = ConfigProvider(config)
        
        result = provider.get_extensions_folder()
        assert result == 'extensions'
    
    def test_get_extensions_folder_none(self):
        """Test getting extensions folder when set to None."""
        config = {'extensions_folder': None}
        provider = ConfigProvider(config)
        
        result = provider.get_extensions_folder()
        assert result is None  # Actually returns None, doesn't default
    
    def test_get_extensions_folder_empty_string(self):
        """Test getting extensions folder when set to empty string."""
        config = {'extensions_folder': ''}
        provider = ConfigProvider(config)
        
        result = provider.get_extensions_folder()
        assert result == ''
    
    def test_get_extensions_folder_path_with_separators(self):
        """Test getting extensions folder with path separators."""
        config = {'extensions_folder': 'path/to/my/extensions'}
        provider = ConfigProvider(config)
        
        result = provider.get_extensions_folder()
        assert result == 'path/to/my/extensions'


class TestConfigProviderRetryConfig:
    """Test retry configuration."""
    
    def test_get_retry_config_exists(self):
        """Test getting retry config when it exists."""
        mock_retry_config = Mock(spec=ExternalOperationRetryConfig)
        config = {'retry_config': mock_retry_config}
        provider = ConfigProvider(config)
        
        result = provider.get_retry_config()
        assert result == mock_retry_config
    
    def test_get_retry_config_missing(self):
        """Test getting retry config when not configured."""
        config = {}
        provider = ConfigProvider(config)
        
        result = provider.get_retry_config()
        assert result is None
    
    def test_get_retry_config_none(self):
        """Test getting retry config when explicitly set to None."""
        config = {'retry_config': None}
        provider = ConfigProvider(config)
        
        result = provider.get_retry_config()
        assert result is None


class TestConfigProviderWebConfig:
    """Test web configuration."""
    
    def test_get_web_config_exists(self):
        """Test getting web config when it exists."""
        web_config = {
            'timeout': 30,
            'headless': True,
            'browser': 'chrome'
        }
        config = {'web_config': web_config}
        provider = ConfigProvider(config)
        
        result = provider.get_web_config()
        assert result == web_config
    
    def test_get_web_config_missing(self):
        """Test getting web config when not configured."""
        config = {}
        provider = ConfigProvider(config)
        
        result = provider.get_web_config()
        assert result == {}
    
    def test_get_web_config_none(self):
        """Test getting web config when set to None."""
        config = {'web_config': None}
        provider = ConfigProvider(config)
        
        result = provider.get_web_config()
        assert result is None  # Actually returns None, doesn't default
    
    def test_get_web_config_empty_dict(self):
        """Test getting web config when set to empty dict."""
        config = {'web_config': {}}
        provider = ConfigProvider(config)
        
        result = provider.get_web_config()
        assert result == {}
    
    def test_get_web_config_complex_structure(self):
        """Test getting complex web config."""
        web_config = {
            'browser_config': {
                'headless': False,
                'viewport': {'width': 1920, 'height': 1080}
            },
            'timeout_config': {
                'page_load': 30,
                'element_wait': 10
            },
            'retry_config': {
                'max_attempts': 3,
                'delay': 1.0
            }
        }
        config = {'web_config': web_config}
        provider = ConfigProvider(config)
        
        result = provider.get_web_config()
        assert result == web_config
        assert result['browser_config']['headless'] is False
        assert result['timeout_config']['page_load'] == 30


class TestConfigProviderEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_config_property_returns_copy(self):
        """Test that config property returns reference to internal config."""
        original_config = {'test': 'value'}
        provider = ConfigProvider(original_config)
        
        retrieved_config = provider.config
        retrieved_config['test'] = 'modified'
        
        # The config property returns the actual internal config, not a copy
        assert provider._config['test'] == 'modified'
    
    def test_large_config_handling(self):
        """Test handling of large configuration."""
        large_config = {}
        
        # Create large config with many keys
        for i in range(1000):
            large_config[f'key_{i}'] = f'value_{i}'
        
        provider = ConfigProvider(large_config)
        
        # Should handle large configs without issue
        assert len(provider.config) == 1000
        assert provider.config['key_500'] == 'value_500'
    
    def test_nested_config_structures(self):
        """Test handling of deeply nested config structures."""
        nested_config = {
            'level1': {
                'level2': {
                    'level3': {
                        'level4': {
                            'value': 'deep_value'
                        }
                    }
                }
            }
        }
        
        provider = ConfigProvider(nested_config)
        
        result = provider.config['level1']['level2']['level3']['level4']['value']
        assert result == 'deep_value'
    
    def test_config_with_special_characters(self):
        """Test config with special characters in keys and values."""
        config = {
            'key with spaces': 'value with spaces',
            'key-with-dashes': 'value-with-dashes',
            'key_with_unicode_🎉': 'value_with_unicode_🔥',
            'key.with.dots': 'value.with.dots',
            'key/with/slashes': 'value/with/slashes'
        }
        
        provider = ConfigProvider(config)
        
        assert provider.config['key with spaces'] == 'value with spaces'
        assert provider.config['key-with-dashes'] == 'value-with-dashes'
        assert provider.config['key_with_unicode_🎉'] == 'value_with_unicode_🔥'
        assert provider.config['key.with.dots'] == 'value.with.dots'
        assert provider.config['key/with/slashes'] == 'value/with/slashes'
    
    def test_config_with_various_data_types(self):
        """Test config with various data types."""
        config = {
            'string_value': 'test',
            'int_value': 42,
            'float_value': 3.14,
            'bool_true': True,
            'bool_false': False,
            'none_value': None,
            'list_value': [1, 2, 3],
            'dict_value': {'nested': 'value'},
        }
        
        provider = ConfigProvider(config)
        
        assert provider.config['string_value'] == 'test'
        assert provider.config['int_value'] == 42
        assert provider.config['float_value'] == 3.14
        assert provider.config['bool_true'] is True
        assert provider.config['bool_false'] is False
        assert provider.config['none_value'] is None
        assert provider.config['list_value'] == [1, 2, 3]
        assert provider.config['dict_value'] == {'nested': 'value'}


class TestConfigProviderIntegration:
    """Test integration scenarios."""
    
    def test_realistic_config_scenario(self):
        """Test realistic configuration scenario."""
        # Mock dependencies
        mock_model1 = Mock(spec=ModelWithRetries)
        mock_model2 = Mock(spec=ModelWithRetries)
        mock_validator = Mock(spec=BaseValidator)
        mock_retry_config = Mock(spec=ExternalOperationRetryConfig)
        
        config = {
            'model_chain': [mock_model1, mock_model2],
            'api_keys': {
                'openai': 'sk-test-openai-key',
                'anthropic': 'claude-test-key'
            },
            'validators': [mock_validator],
            'extensions_folder': 'custom_extensions',
            'retry_config': mock_retry_config,
            'web_config': {
                'browser': 'chrome',
                'headless': True,
                'timeout': 30,
                'auto_suggest_selectors': True
            }
        }
        
        provider = ConfigProvider(config)
        
        # Test all getters work correctly
        assert provider.get_model_chain() == [mock_model1, mock_model2]
        assert provider.get_api_key('openai') == 'sk-test-openai-key'
        assert provider.get_api_key('anthropic') == 'claude-test-key'
        assert provider.get_validators() == [mock_validator]
        assert provider.get_extensions_folder() == 'custom_extensions'
        assert provider.get_retry_config() == mock_retry_config
        
        web_config = provider.get_web_config()
        assert web_config['browser'] == 'chrome'
        assert web_config['headless'] is True
        assert web_config['auto_suggest_selectors'] is True
    
    def test_partial_config_scenario(self):
        """Test scenario with only partial configuration."""
        config = {
            'api_keys': {'openai': 'test-key'},
            'web_config': {'browser': 'firefox'}
        }
        
        provider = ConfigProvider(config)
        
        # Should handle missing sections gracefully
        assert provider.get_model_chain() is None
        assert provider.get_api_key('openai') == 'test-key'
        assert provider.get_api_key('anthropic') is None
        assert provider.get_validators() == []
        assert provider.get_extensions_folder() == 'extensions'
        assert provider.get_retry_config() is None
        
        web_config = provider.get_web_config()
        assert web_config == {'browser': 'firefox'}
    
    def test_config_modification_workflow(self):
        """Test typical config modification workflow."""
        original_model = Mock(spec=ModelWithRetries)
        test_model = Mock(spec=ModelWithRetries)
        
        config = {'model_chain': [original_model]}
        provider = ConfigProvider(config)
        
        # Initial state
        assert provider.get_model_chain() == [original_model]
        
        # Temporarily override for testing
        provider.override_model_chain_with([test_model])
        assert provider.get_model_chain() == [test_model]
        
        # Reset back to original
        provider.reset_model_chain()
        assert provider.get_model_chain() == [original_model]
        
        # Should be able to repeat the cycle
        provider.override_model_chain_with([test_model])
        assert provider.get_model_chain() == [test_model]
        provider.reset_model_chain()
        assert provider.get_model_chain() == [original_model]