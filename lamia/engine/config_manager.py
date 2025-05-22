import os
import yaml
from typing import Dict, Any, Optional

class ConfigManager:
    """
    Manages configuration settings for the Lamia project.
    Handles loading and accessing configuration from config.yaml.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the config manager.
        
        Args:
            config_path: Optional path to config file. If None, uses default location.
        """
        self.config_path = config_path or self._get_default_config_path()
        self.config: Dict[str, Any] = {}
        self.load_config()

    def _get_default_config_path(self) -> str:
        """Get the default path to the config file."""
        # Config is now in the root directory
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'config.yaml')

    def load_config(self) -> None:
        """Load configuration from the YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found at {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing config file: {e}")

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