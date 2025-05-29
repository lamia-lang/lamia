import os
from typing import Dict, Any, Optional
import yaml

class ConfigManager:
    """
    Manages configuration settings for the Lamia project.
    Handles loading and accessing configuration from a config dict.
    On initialization, enriches api_keys from environment variables if missing in the dict.
    After initialization, all lookups are from the dict only.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the config manager.
        
        Args:
            config: Configuration dictionary.
        """
        if not isinstance(config, dict):
            raise ValueError("ConfigManager expects a config dict.")
        # Enrich api_keys from env if missing
        api_keys = config.get('api_keys', {}).copy() if config.get('api_keys') else {}
        for provider, env_var in {'openai': 'OPENAI_API_KEY', 'anthropic': 'ANTHROPIC_API_KEY'}.items():
            if provider not in api_keys and os.getenv(env_var):
                api_keys[provider] = os.getenv(env_var)
        config['api_keys'] = api_keys
        self.config: Dict[str, Any] = config

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]):
        return cls(config_dict)

    def get_config(self) -> Dict[str, Any]:
        """Get the entire configuration dictionary."""
        return self.config

    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific model.
        
        Args:
            model_name: Name of the model (e.g., 'openai', 'anthropic')
            
        Returns:
            Dict containing model configuration
        """
        models_config = self.config.get('models', {})
        model_config = models_config.get(model_name, {})
        
        if not model_config:
            raise ValueError(f"Configuration for model '{model_name}' not found")
            
        return model_config

    def get_validation_config(self) -> Dict[str, Any]:
        """Get validation configuration settings."""
        return self.config.get('validation', {})

    def get_default_model(self) -> str:
        """Get the default model name from config."""
        return self.config.get('default_model')

    def get_has_context_memory(self, provider: str, model_name: str) -> Optional[bool]:
        """
        Get has_context_memory override for a specific provider and model name from config.
        Returns None if not set.
        """
        models_config = self.config.get('models', {})
        provider_config = models_config.get(provider, {})
        models_list = provider_config.get('models', [])
        for entry in models_list:
            if isinstance(entry, dict) and entry.get('name') == model_name:
                return entry.get('has_context_memory')
            elif isinstance(entry, str) and entry == model_name:
                # No override, just a string
                return None
        return None 

    def get_api_key(self, provider: str) -> Optional[str]:
        # Only return from the dict, never from the environment
        api_keys = self.config.get('api_keys', {})
        return api_keys.get(provider) 