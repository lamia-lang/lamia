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

DEFAULT_LLM_RETRIES = 1


def _construct_model_from_config(config: Dict[str, Any], model_chain_item: Dict[str, Any]) -> Optional[LLMModel]:
    """Construct an LLMModel from full config and model chain item.
    
    This handles the complex case where model_chain items reference providers
    and inherit settings from provider/model family configurations.
    """
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


def _parse_retry_config(retry_config_settings: Dict[str, Any]) -> Optional[ExternalOperationRetryConfig]:
    """Parse retry config from settings dict."""
    if not retry_config_settings.get('enabled', True):
        return None
    
    max_total_duration = retry_config_settings.get('max_total_duration')
    if max_total_duration is not None:
        max_total_duration = timedelta(seconds=max_total_duration)
        
    return ExternalOperationRetryConfig(
        max_attempts=retry_config_settings.get('max_attempts', 3),
        base_delay=retry_config_settings.get('base_delay', 1.0),
        max_delay=retry_config_settings.get('max_delay', 60.0),
        exponential_base=retry_config_settings.get('exponential_base', 2.0),
        max_total_duration=max_total_duration
    )


def _build_model_chain_from_config(config: Dict[str, Any]) -> List[ModelWithRetries]:
    """Build model chain from config dict with provider resolution."""
    models_and_retries: List[ModelWithRetries] = []
    
    if "model_chain" not in config:
        return models_and_retries
    
    model_chain = config['model_chain']
    for index, model_chain_item in enumerate(model_chain):
        try:
            model = _construct_model_from_config(config, model_chain_item)
            if model is not None:  # Gracefully handle disabled providers
                retries = model_chain_item.get('max_retries', DEFAULT_LLM_RETRIES)
                models_and_retries.append(ModelWithRetries(model, retries))
        except ValueError as e:
            raise ValueError(f"Model chain item {index} with name '{model_chain_item.get('name', 'unknown')}' excluded. Reason: {e}")
    
    if len(models_and_retries) == 0:
        logger.warning("No valid LLM model found in the model chain. LLM operations will not be possible.")
    
    return models_and_retries


def _build_model_chain_from_specs(
    models: Tuple[Union[Union[str, LLMModel], Tuple[Union[str, LLMModel], int]], ...]
) -> List[ModelWithRetries]:
    """Build model chain from simple model specs (programmatic API)."""
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
    
    return models_and_retries


def _assemble_config_provider(
    model_chain: List[ModelWithRetries],
    api_keys: Optional[dict],
    retry_config: Optional[ExternalOperationRetryConfig],
    web_config: Optional[Dict[str, Any]]
) -> ConfigProvider:
    """Assemble final ConfigProvider from components.
    
    This is the SINGLE place where config dict is assembled, ensuring
    all config options are always included.
    """
    config_dict: Dict[str, Any] = {
        "model_chain": model_chain,
        "api_keys": api_keys,
        "retry_config": retry_config,
        "web_config": web_config or {},
    }
    return ConfigProvider(config_dict)


def build_config_from_dict(config: Dict[str, Any]) -> ConfigProvider:
    """Build ConfigProvider from a configuration dictionary (e.g., from YAML).
    
    This handles the complex config format with providers, model settings inheritance,
    and retry config parsing.
    """
    model_chain = _build_model_chain_from_config(config)
    retry_config = _parse_retry_config(config.get("retry_config", {}))
    api_keys = config.get("api_keys")
    web_config = config.get("web_config")
    
    return _assemble_config_provider(model_chain, api_keys, retry_config, web_config)


def build_config_from_models(
    models: Tuple[Union[Union[str, LLMModel], Tuple[Union[str, LLMModel], int]], ...],
    api_keys: Optional[dict], 
    retry_config: Optional[ExternalOperationRetryConfig],
    web_config: Optional[Dict[str, Any]]
) -> ConfigProvider:
    """Build ConfigProvider from model specifications (programmatic API).
    
    This is the simple path for programmatic use where models are specified
    directly as strings, LLMModel objects, or (model, retries) tuples.
    """
    model_chain = _build_model_chain_from_specs(models)
    return _assemble_config_provider(model_chain, api_keys, retry_config, web_config)
