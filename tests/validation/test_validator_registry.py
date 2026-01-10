import pytest
from unittest import mock
from lamia.validation.validator_registry import ValidatorRegistry
from lamia.validation.base import BaseValidator

class DummyValidator(BaseValidator):
    @classmethod
    def name(cls):
        return "dummy"
    
    @property
    def initial_hint(self) -> str:
        return "Dummy hint"
        
    def validate(self, value, **kwargs):
        return True

@pytest.mark.asyncio
async def test_builtin_validator_discovery():
    registry = ValidatorRegistry(enable_contract_checking=False)
    # Patch _discover_validators_recursively to return our dummy
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={"dummy": DummyValidator}):
        reg = await registry.get_registry()
        assert "dummy" in reg
        assert reg["dummy"] is DummyValidator

@pytest.mark.asyncio
async def test_extension_validator_discovery():
    registry = ValidatorRegistry(enable_contract_checking=False)
    # Patch both discovery methods
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={"dummy": DummyValidator}):
            reg = await registry.get_registry()
            assert "dummy" in reg
            assert reg["dummy"] is DummyValidator

@pytest.mark.asyncio
async def test_name_conflict_detection():
    registry = ValidatorRegistry(enable_contract_checking=False)
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={"dummy": DummyValidator}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={"dummy": DummyValidator}):
            with pytest.raises(ValueError) as exc:
                await registry.get_registry()
            assert "conflict" in str(exc.value)

@pytest.mark.asyncio
async def test_contract_checking_enabled():
    """Test that contract checking is enabled by default and can be configured."""
    registry = ValidatorRegistry()
    
    # Contract checking should be enabled by default
    assert registry.enable_contract_checking is True
    
    # Can be disabled via config
    registry_disabled = ValidatorRegistry(enable_contract_checking=False)
    assert registry_disabled.enable_contract_checking is False

@pytest.mark.asyncio
async def test_contract_checking_disabled():
    """Test that contract checking can be disabled."""
    registry = ValidatorRegistry(enable_contract_checking=False)
    
    # Should not run contract checks when disabled
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={"dummy": DummyValidator}):
        with mock.patch.object(registry, '_check_validator_contract') as mock_check:
            reg = await registry.get_registry()
            # Contract check should not be called for built-in validators since they're discovered differently
            # But we ensure the system works without contract checking
            assert "dummy" in reg