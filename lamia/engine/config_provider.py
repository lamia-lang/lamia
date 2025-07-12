import os
from typing import Dict, Any, Optional, List


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
        
        # Enrich api_keys from env if missing (this happens once, at creation)
        api_keys = self._config.get('api_keys', {}).copy()
        self._config['api_keys'] = api_keys

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]):
        return cls(config_dict)

    def get_default_model(self) -> str:
        """Get the default model name from config."""
        return self._config.get('default_model')

    def get_fallback_models(self) -> List[str]:
        """Get the fallback models from config."""
        return self._config.get('fallback_models', [])

    def get_validation_config(self) -> Dict[str, Any]:
        """Get validation configuration settings."""
        return self._config.get('validation', {})

    def get_default_model(self) -> str:
        """Get the default model name from config."""
        return self._config.get('default_model')

    def get_api_key(self, provider: str) -> Optional[str]:
        # Only return from the dict, never from the environment
        api_keys = self._config.get('api_keys', {})
        return api_keys.get(provider) 

    def get_extensions_folder(self) -> str:
        """Get the path to the extensions folder from config, defaulting to 'extensions' if not set."""
        return self._config.get('extensions_folder', 'extensions') 

