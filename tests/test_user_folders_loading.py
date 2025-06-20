import os
import sys
import shutil
import tempfile
import pytest
from lamia.engine.engine import LamiaEngine
from lamia.engine.llm_manager import create_adapter_from_config

# --- Dummy extension adapter and validator code ---
ADAPTER_CODE = '''
from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse
import asyncio
class MyExtensionAdapter(BaseLLMAdapter):
    async def initialize(self):
        pass
    async def generate(self, prompt, temperature=0.7, max_tokens=None, stop_sequences=None, **kwargs):
        return LLMResponse(text=f"Echo: {prompt}", raw_response=None, usage={}, model="my_extension")
    async def close(self):
        pass
    @property
    def has_context_memory(self):
        return False
'''

VALIDATOR_CODE = '''
from lamia.validation.base import BaseValidator, ValidationResult
class MyExtensionValidator(BaseValidator):
    @classmethod
    def name(cls):
        return "my_extension_validator"
    @property
    def initial_hint(self):
        return "Always valid."
    async def validate(self, response, **kwargs):
        return ValidationResult(is_valid=True)
'''

@pytest.fixture(scope="module")
def temp_extensions():
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

def test_extension_adapter_and_validator_loading(temp_extensions):
    config = {
        "default_model": "MyExtensionAdapter",
        "models": {
            "MyExtensionAdapter": {
                "enabled": True,
                "default_model": "my_extension",
                "models": ["my_extension"]
            }
        },
        "extensions_folder": temp_extensions,
        "validation": {
            "enabled": True,
            "validators": [
                {"type": "my_extension_validator"}
            ]
        }
    }
    # Patch sys.path so extension modules can be imported
    sys.path.insert(0, temp_extensions)
    try:
        engine = LamiaEngine(config)
        # Adapter: should be available and instantiable
        adapter = create_adapter_from_config(engine.config_manager)
        assert adapter.__class__.__name__ == "MyExtensionAdapter"
        # Validator: should be in the registry
        registry = engine._get_validator_registry()
        assert "my_extension_validator" in registry
    finally:
        sys.path.remove(temp_extensions) 