"""Tests for extension loading (adapters and validators)."""

import os
import shutil
import sys
import tempfile

import pytest

from lamia import LLMModel
from lamia._internal_types.model_retry import ModelWithRetries
from lamia.engine.config_provider import ConfigProvider
from lamia.engine.managers.llm.llm_manager import LLMManager
from lamia.interpreter.commands import LLMCommand
from lamia.validation.validator_registry import ValidatorRegistry


# --- Dummy extension adapter code ---
ADAPTER_CODE = '''
from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse
from lamia import LLMModel

class MyExtensionAdapter(BaseLLMAdapter):
    """Custom extension adapter for testing."""
    
    @classmethod
    def name(cls) -> str:
        return "my_extension"
    
    @classmethod
    def is_remote(cls) -> bool:
        return False
    
    @classmethod
    def env_var_names(cls) -> list[str]:
        return []  # No API key needed
    
    async def generate(self, prompt: str, model: LLMModel) -> LLMResponse:
        return LLMResponse(
            text=f"Echo: {prompt}",
            raw_response=None,
            usage={},
            model="my_extension"
        )
    
    async def close(self):
        pass
    
    @property
    def has_context_memory(self):
        return False
'''

# --- Dummy extension validator code ---
VALIDATOR_CODE = '''
from lamia.validation.base import BaseValidator, ValidationResult

class MyExtensionValidator(BaseValidator):
    """Custom extension validator for testing."""
    
    @classmethod
    def name(cls):
        return "my_extension_validator"
    
    @property
    def initial_hint(self):
        return "Always valid."
    
    async def validate(self, response, **kwargs):
        return ValidationResult(is_valid=True, validated_text=response)
'''


@pytest.fixture(scope="module")
def temp_extensions():
    """Create temporary extensions folder with adapter and validator."""
    temp_dir = tempfile.mkdtemp()
    adapters_dir = os.path.join(temp_dir, "adapters")
    validators_dir = os.path.join(temp_dir, "validators")
    os.makedirs(adapters_dir)
    os.makedirs(validators_dir)

    # Write dummy adapter
    with open(os.path.join(adapters_dir, "my_extension_adapter.py"), "w") as f:
        f.write(ADAPTER_CODE)

    # Write dummy validator
    with open(os.path.join(validators_dir, "my_extension_validator.py"), "w") as f:
        f.write(VALIDATOR_CODE)

    yield temp_dir
    shutil.rmtree(temp_dir)


class TestExtensionAdapterLoading:
    """Test loading of custom LLM adapters from extensions folder."""

    @pytest.mark.asyncio
    async def test_extension_adapter_loaded_and_usable(self, temp_extensions):
        """Test that custom adapter is loaded from extensions folder and can be used."""
        # Create config with the custom adapter
        config_provider = ConfigProvider({
            "model_chain": [
                ModelWithRetries(LLMModel("my_extension"), retries=1)
            ],
            "extensions_folder": temp_extensions,
        })

        # Patch sys.path so extension modules can be imported
        sys.path.insert(0, temp_extensions)
        try:
            llm_manager = LLMManager(config_provider)

            # Verify the adapter was registered
            adapter_class = llm_manager.provider_registry.get_adapter_class("my_extension")
            assert adapter_class.__name__ == "MyExtensionAdapter"

            # Create and use the adapter
            model = LLMModel("my_extension")
            adapter = await llm_manager.create_adapter_from_config(model, with_retries=False)
            assert adapter.__class__.__name__ == "MyExtensionAdapter"

            # Test generating with the adapter
            response = await adapter.generate("Hello", model)
            assert response.text == "Echo: Hello"
            assert response.model == "my_extension"
        finally:
            sys.path.remove(temp_extensions)
            await llm_manager.close()

    @pytest.mark.asyncio
    async def test_extension_adapter_execute_returns_validation_result(self, temp_extensions):
        """Test that executing with extension adapter returns ValidationResult."""
        config_provider = ConfigProvider({
            "model_chain": [
                ModelWithRetries(LLMModel("my_extension"), retries=1)
            ],
            "extensions_folder": temp_extensions,
        })

        sys.path.insert(0, temp_extensions)
        try:
            llm_manager = LLMManager(config_provider)
            command = LLMCommand("Test prompt")
            result = await llm_manager.execute(command)

            assert result.is_valid is True
            assert result.validated_text == "Echo: Test prompt"
            assert "Echo: Test prompt" in result.validated_text
        finally:
            sys.path.remove(temp_extensions)
            await llm_manager.close()


class TestExtensionValidatorLoading:
    """Test loading of custom validators from extensions folder."""

    def test_extension_validator_loaded(self, temp_extensions):
        """Test that custom validator is loaded from extensions folder."""
        # Change to temp dir so extensions can be found relative to cwd
        original_cwd = os.getcwd()
        os.chdir(temp_extensions)

        try:
            # Create registry with empty string to use relative path
            registry = ValidatorRegistry(extensions_folder="")

            # Load extension validators (called lazily)
            registry._load_user_validators()

            # Verify the validator was registered
            assert "my_extension_validator" in registry._user_validators
        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_extension_validator_usable(self, temp_extensions):
        """Test that loaded extension validator can be used."""
        original_cwd = os.getcwd()
        os.chdir(temp_extensions)

        try:
            registry = ValidatorRegistry(extensions_folder="")

            # Get and instantiate the validator (calls _load_user_validators internally)
            validator_class = registry.get_class_from_name("my_extension_validator")
            validator = validator_class()

            # Test the validator
            result = await validator.validate("test response")
            assert result.is_valid is True
            assert result.validated_text == "test response"
        finally:
            os.chdir(original_cwd)
