import pytest
from unittest import mock
from lamia.validation.validator_registry import ValidatorRegistry
from lamia.validation.base import BaseValidator

class DummyValidator(BaseValidator):
    @classmethod
    def name(cls):
        return "dummy"
    def validate(self, value, **kwargs):
        return True

def test_builtin_validator_discovery():
    config = {'validation': {'validators': [{'type': 'dummy'}]}}
    registry = ValidatorRegistry(config)
    # Patch _discover_validators_recursively to return our dummy
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={"dummy": DummyValidator}):
        reg = registry.get_registry()
        assert "dummy" in reg
        assert reg["dummy"] is DummyValidator

def test_extension_validator_discovery():
    config = {'validation': {'validators': [{'type': 'dummy'}]}}
    registry = ValidatorRegistry(config)
    # Patch both discovery methods
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={"dummy": DummyValidator}):
            reg = registry.get_registry()
            assert "dummy" in reg
            assert reg["dummy"] is DummyValidator

def test_name_conflict_detection():
    config = {'validation': {'validators': [{'type': 'dummy'}]}}
    registry = ValidatorRegistry(config)
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={"dummy": DummyValidator}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={"dummy": DummyValidator}):
            with pytest.raises(ValueError) as exc:
                registry.get_registry()
            assert "conflict" in str(exc.value)

def test_unknown_validator_type():
    config = {'validation': {'validators': [{'type': 'not_a_validator'}]}}
    registry = ValidatorRegistry(config)
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={}):
            with pytest.raises(ValueError) as exc:
                registry.get_registry()
            assert "Unknown validator type" in str(exc.value)

def test_custom_file_validator_loading():
    config = {'validation': {'validators': [{'type': 'custom_file', 'path': '/tmp/fake.py'}]}}
    registry = ValidatorRegistry(config)
    dummy = DummyValidator
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={}):
            with mock.patch('lamia.validation.validator_registry.load_validator_from_file', return_value=dummy) as mock_loader:
                reg = registry.get_registry()
                assert "dummy" in reg
                assert reg["dummy"] is dummy
                mock_loader.assert_called_once_with('/tmp/fake.py')

def test_custom_function_validator_loading():
    config = {'validation': {'validators': [{'type': 'custom_function', 'path': 'some.module.func'}]}}
    registry = ValidatorRegistry(config)
    dummy = DummyValidator
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={}):
            with mock.patch('lamia.validation.validator_registry.load_validator_from_function', return_value=dummy) as mock_loader:
                reg = registry.get_registry()
                assert "dummy" in reg
                assert reg["dummy"] is dummy
                mock_loader.assert_called_once_with('some.module.func')

def test_custom_file_validator_path_missing():
    config = {'validation': {'validators': [{'type': 'custom_file'}]}}
    registry = ValidatorRegistry(config)
    dummy = DummyValidator
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={}):
            with mock.patch('lamia.validation.validator_registry.load_validator_from_file', return_value=dummy) as mock_loader:
                reg = registry.get_registry()
                # The loader should NOT be called, and registry should be empty
                assert reg == {}
                mock_loader.assert_not_called()

def test_custom_function_validator_path_missing():
    config = {'validation': {'validators': [{'type': 'custom_function'}]}}
    registry = ValidatorRegistry(config)
    dummy = DummyValidator
    with mock.patch.object(registry, '_discover_validators_recursively', return_value={}):
        with mock.patch.object(registry, '_discover_validators_in_path', return_value={}):
            with mock.patch('lamia.validation.validator_registry.load_validator_from_function', return_value=dummy) as mock_loader:
                reg = registry.get_registry()
                # The loader should NOT be called, and registry should be empty
                assert reg == {}
                mock_loader.assert_not_called()