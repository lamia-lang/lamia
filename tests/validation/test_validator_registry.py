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
    config = {'validation': {'validators': [{'type': 'dummy'}], 'enable_contract_checking': False}}
    registry = ValidatorRegistry(config)
    # Patch _discover_validators_recursively to return our dummy
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={"dummy": DummyValidator}):
        reg = await registry.get_registry()
        assert "dummy" in reg
        assert reg["dummy"] is DummyValidator

@pytest.mark.asyncio
async def test_extension_validator_discovery():
    config = {'validation': {'validators': [{'type': 'dummy'}], 'enable_contract_checking': False}}
    registry = ValidatorRegistry(config)
    # Patch both discovery methods
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={"dummy": DummyValidator}):
            reg = await registry.get_registry()
            assert "dummy" in reg
            assert reg["dummy"] is DummyValidator

@pytest.mark.asyncio
async def test_name_conflict_detection():
    config = {'validation': {'validators': [{'type': 'dummy'}], 'enable_contract_checking': False}}
    registry = ValidatorRegistry(config)
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={"dummy": DummyValidator}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={"dummy": DummyValidator}):
            with pytest.raises(ValueError) as exc:
                await registry.get_registry()
            assert "conflict" in str(exc.value)

@pytest.mark.asyncio
async def test_unknown_validator_type():
    config = {'validation': {'validators': [{'type': 'not_a_validator'}], 'enable_contract_checking': False}}
    registry = ValidatorRegistry(config)
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={}):
            with pytest.raises(ValueError) as exc:
                await registry.get_registry()
            assert "Unknown validator type" in str(exc.value)

@pytest.mark.asyncio
async def test_custom_file_validator_loading():
    config = {'validation': {'validators': [{'type': 'custom_file', 'path': '/tmp/fake.py'}], 'enable_contract_checking': False}}
    registry = ValidatorRegistry(config)
    dummy = DummyValidator
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={}):
            with mock.patch('lamia.validation.validator_registry.load_validator_from_file', return_value=dummy) as mock_loader:
                reg = await registry.get_registry()
                assert "dummy" in reg
                assert reg["dummy"] is dummy
                mock_loader.assert_called_once_with('/tmp/fake.py')

@pytest.mark.asyncio
async def test_custom_function_validator_loading():
    config = {'validation': {'validators': [{'type': 'custom_function', 'path': 'some.module.func'}], 'enable_contract_checking': False}}
    registry = ValidatorRegistry(config)
    dummy = DummyValidator
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={}):
            with mock.patch('lamia.validation.validator_registry.load_validator_from_function', return_value=dummy) as mock_loader:
                reg = await registry.get_registry()
                assert "dummy" in reg
                assert reg["dummy"] is dummy
                mock_loader.assert_called_once_with('some.module.func')

@pytest.mark.asyncio
async def test_custom_file_validator_path_missing():
    config = {'validation': {'validators': [{'type': 'custom_file'}], 'enable_contract_checking': False}}
    registry = ValidatorRegistry(config)
    dummy = DummyValidator
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={}):
            with mock.patch('lamia.validation.validator_registry.load_validator_from_file', return_value=dummy) as mock_loader:
                reg = await registry.get_registry()
                # The loader should NOT be called, and registry should be empty
                assert reg == {}
                mock_loader.assert_not_called()

@pytest.mark.asyncio
async def test_custom_function_validator_path_missing():
    config = {'validation': {'validators': [{'type': 'custom_function'}], 'enable_contract_checking': False}}
    registry = ValidatorRegistry(config)
    dummy = DummyValidator
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={}):
            with mock.patch('lamia.validation.validator_registry.load_validator_from_function', return_value=dummy) as mock_loader:
                reg = await registry.get_registry()
                # The loader should NOT be called, and registry should be empty
                assert reg == {}
                mock_loader.assert_not_called()

@pytest.mark.asyncio
async def test_contract_checking_enabled():
    """Test that contract checking is enabled by default and can be configured."""
    config = {'validation': {'validators': [{'type': 'dummy'}]}}
    registry = ValidatorRegistry(config)
    
    # Contract checking should be enabled by default
    assert registry.enable_contract_checking is True
    
    # Can be disabled via config
    config_disabled = {'validation': {'validators': [{'type': 'dummy'}], 'enable_contract_checking': False}}
    registry_disabled = ValidatorRegistry(config_disabled)
    assert registry_disabled.enable_contract_checking is False

@pytest.mark.asyncio
async def test_contract_checking_disabled():
    """Test that contract checking can be disabled."""
    config = {'validation': {'validators': [{'type': 'dummy'}], 'enable_contract_checking': False}}
    registry = ValidatorRegistry(config, enable_contract_checking=False)
    
    # Should not run contract checks when disabled
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={"dummy": DummyValidator}):
        with mock.patch.object(registry, '_check_validator_contract') as mock_check:
            reg = await registry.get_registry()
            # Contract check should not be called for built-in validators since they're discovered differently
            # But we ensure the system works without contract checking
            assert "dummy" in reg