"""
Configuration building utilities for Lamia facade.

This module handles the complex logic of building configurations from
various sources (direct parameters, config files, etc.).
"""

import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import timedelta

from lamia import LLMModel
from lamia._internal_types.model_retry import ModelWithRetries
from lamia.types import ExternalOperationRetryConfig
from lamia.engine.config_provider import ConfigProvider

logger = logging.getLogger(__name__)


def construct_model(config: Dict[str, Any], model_chain_item: Dict[str, Any]) -> Optional[LLMModel]:
    """Construct an LLMModel from config and model chain item."""
    if "name" not in model_chain_item:
        raise ValueError("Model chain item must have a name")
    
    if ":" in model_chain_item["name"]:
        model_family_name = model_chain_item["name"].split(":")[1]
        model_full_name = model_chain_item["name"]
        provider_name = model_chain_item["name"].split(":")[0]
    else:
        if "providers" not in config:
            raise ValueError("Providers are not configured.")
        
        providers = config["providers"]
        provider_name = model_chain_item["name"]
        if provider_name not in providers:
            raise ValueError(f"Provider {provider_name} is not configured. Please provide the model full name, e.g. 'openai:gpt-4o'.")
        
        if not providers[provider_name]["enabled"]:
            logger.warning(f"Provider {provider_name} is not enabled. Please enable it in the config if you want to use it.")
            return None
        
        if "default_model" not in providers[provider_name]:
            raise ValueError(f"Provider {provider_name} does not have a default model. Please provide a default model in the config")
        
        model_family_name = providers[provider_name]["default_model"]
        model_full_name = f"{provider_name}:{model_family_name}"
    
    providers = config.get("providers", {})
    provider_settings = providers.get(provider_name, {})
    model_family_settings = provider_settings.get(model_family_name, {})
    get_model_param = lambda key: model_chain_item.get(key, None) or model_family_settings.get(key, None) or provider_settings.get(key, None)
    
    return LLMModel(
        name=model_full_name,
        temperature=get_model_param("temperature"),
        max_tokens=get_model_param("max_tokens"),
        top_p=get_model_param("top_p"),
        top_k=get_model_param("top_k"),
        frequency_penalty=get_model_param("frequency_penalty"),
        presence_penalty=get_model_param("presence_penalty"),
        seed=get_model_param("seed")
    )


def build_config_from_dict(config: Dict[str, Any]) -> Tuple[List[LLMModel], Optional[ExternalOperationRetryConfig]]:
    """Build models and retry config from a config dictionary."""
    models = []
    if "model_chain" in config:
        model_chain = config['model_chain']
        for index, model_chain_item in enumerate(model_chain):
            try:
                model = construct_model(config, model_chain_item)
                if model is not None:  # Gracefully handle disabled providers
                    models.append(model)
            except ValueError as e:
                raise ValueError(f"Model chain item {index} with name '{model_chain_item.get('name', 'unknown')}' excluded. Reason: {e}")

    if len(models) == 0:
        logger.warning("No valid LLM model found in the model chain. LLM operations will not be possible.")
        
    # Convert the config dictionary to ExternalOperationRetryConfig
    retry_config_settings = config.get("retry_config", {})
    if not retry_config_settings.get('enabled', True):
        retry_config = None
    else:
        max_total_duration = retry_config_settings.get('max_total_duration')
        if max_total_duration is not None:
            max_total_duration = timedelta(seconds=max_total_duration)
            
        retry_config = ExternalOperationRetryConfig(
            max_attempts=retry_config_settings.get('max_attempts', 3),
            base_delay=retry_config_settings.get('base_delay', 1.0),
            max_delay=retry_config_settings.get('max_delay', 60.0),
            exponential_base=retry_config_settings.get('exponential_base', 2.0),
            max_total_duration=max_total_duration
        ) 

    return models, retry_config


def build_config_from_models(
    models: Tuple[Union[Union[str, LLMModel], Tuple[Union[str, LLMModel], int]], ...],
    api_keys: Optional[dict], 
    retry_config: Optional[ExternalOperationRetryConfig],
) -> ConfigProvider:
    """Build a ConfigProvider from model specifications."""
    DEFAULT_LLM_RETRIES = 1
    # Convert the *models* var-tuple into a proper list for iteration.
    incoming_models = list(models) if models else []

    # If nothing was supplied default to a local Ollama setup.
    if not incoming_models:
        incoming_models = ["ollama"]

    models_and_retries: List[ModelWithRetries] = []
    for item in incoming_models:
        retries = DEFAULT_LLM_RETRIES

        # Unpack `(something, retries)`
        if isinstance(item, tuple):
            item, retries = item  # type: ignore[misc]

        # Turn strings into ``Model`` instances
        if isinstance(item, str):
            item = LLMModel(name=item)  # When only the model name is provided, the model params are set to None automatically
        elif not isinstance(item, LLMModel):
            raise TypeError(
                "Each model spec must be a str, Model or (spec, retries) tuple"
            )

        models_and_retries.append(ModelWithRetries(item, retries))

    # Assemble the final config dict
    config_dict: Dict[str, Any] = {
        "model_chain": models_and_retries,
        "api_keys": api_keys,
        "retry_config": retry_config,
    }    

    return ConfigProvider(config_dict)