import os
from typing import Dict, Any, Optional, List, Tuple, Union
from lamia._internal_types.model_retry import ModelWithRetries

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
        self._primary_model = config.get('model_chain')[0]
        self._fallback_models = [model for model in config.get('model_chain')[1:]]

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]):
        return cls(config_dict)

    @property
    def config(self) -> Dict[str, Any]:
        """Get the raw config dictionary."""
        return self._config

    def get_primary_model(self) -> ModelWithRetries:
        """Get the primary model and retries from config."""
        return self._primary_model

    def get_fallback_models(self) -> List[ModelWithRetries]:
        """Get the fallback models from config."""
        return self._fallback_models

    def get_api_key(self, provider: str) -> Optional[str]:
        # Only return from the dict, never from the environment
        api_keys = self._config.get('api_keys', {})
        if api_keys is not None and provider in api_keys:
            return api_keys.get(provider) 
        return None
    
    def get_validators(self) -> List[Any]:
        """Get the validators from config."""
        return self._config.get('validators', [])

    def get_extensions_folder(self) -> str:
        """Get the path to the extensions folder from config, defaulting to 'extensions' if not set."""
        return self._config.get('extensions_folder', 'extensions') 

