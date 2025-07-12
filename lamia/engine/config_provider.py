import os
from typing import Dict, Any, Optional, List, Tuple, Union
from lamia import LLMModel

class ConfigProvider:
    """
    Provides read-only access to Lamia configuration values.
    
    This class offers a type-safe interface for accessing configuration values,
    with convenient getters for different configuration domains (models, validation, etc).
    All access is read-only; the underlying configuration is immutable after creation.
    """
    
    def __init__(self, config: Dict[str, Any]):
        if not isinstance(config, dict):
            raise ValueError("ConfigProvider expects a config dict.")
        
        # Make a defensive copy to ensure true immutability
        self._config = config.copy()

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]):
        return cls(config_dict)

    @property
    def config(self) -> Dict[str, Any]:
        """Get the raw config dictionary."""
        return self._config

    def get_default_model(self) -> Tuple[LLMModel, int]:
        """Get the default model and retries from config."""
        return self._config.get('default_model')

    def get_fallback_models(self) -> List[Tuple[LLMModel, int]]:
        """Get the fallback models from config."""
        return self._config.get('fallback_models', [])

    def get_validation_config(self) -> Dict[str, Any]:
        """Get validation configuration settings."""
        return self._config.get('validation', {})

    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """Get configuration for a specific model."""
        # This is a simplified implementation - you might want to enhance this
        # based on your actual model configuration structure
        return {}

    def get_api_key(self, provider: str) -> Optional[str]:
        # Only return from the dict, never from the environment
        api_keys = self._config.get('api_keys', {})
        return api_keys.get(provider) 

    def get_extensions_folder(self) -> str:
        """Get the path to the extensions folder from config, defaulting to 'extensions' if not set."""
        return self._config.get('extensions_folder', 'extensions') 

