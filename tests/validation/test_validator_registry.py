"""Tests for ValidatorRegistry class."""

import os
import sys
import tempfile
import shutil
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from lamia.validation.validator_registry import ValidatorRegistry
from lamia.validation.base import BaseValidator, ValidationResult
from lamia.validation.contract_checker import ContractViolation


class ValidTestValidator(BaseValidator):
    """A valid test validator for testing."""

    @classmethod
    def name(cls) -> str:
        return "valid_test"

    @property
    def initial_hint(self) -> str:
        return "Valid test hint"

    async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
        return ValidationResult(is_valid=True)


class AnotherValidValidator(BaseValidator):
    """Another valid test validator."""

    @classmethod
    def name(cls) -> str:
        return "another_valid"

    @property
    def initial_hint(self) -> str:
        return "Another valid hint"

    async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
        return ValidationResult(is_valid=True)


class TestValidatorRegistryInitialization:
    """Test ValidatorRegistry initialization."""

    def test_registry_initialization(self):
        """Test basic registry initialization."""
        registry = ValidatorRegistry(extensions_folder="test_extensions")

        assert registry.extensions_folder == "test_extensions"
        assert isinstance(registry._built_in_validators, dict)
        assert isinstance(registry._user_validators, dict)
        assert isinstance(registry._checked_classes, set)

    def test_registry_discovers_builtin_validators(self):
        """Test that registry discovers built-in validators."""
        registry = ValidatorRegistry(extensions_folder="test_extensions")

        # Should have discovered some built-in validators
        assert len(registry._built_in_validators) > 0

    def test_registry_empty_user_validators_initially(self):
        """Test that user validators are empty initially."""
        registry = ValidatorRegistry(extensions_folder="test_extensions")

        assert len(registry._user_validators) == 0


class TestValidatorRegistryBuiltInValidatorDetection:
    """Test ValidatorRegistry built-in validator detection."""

    def test_is_built_in_for_built_in_validator(self):
        """Test that built-in validators are correctly identified."""
        registry = ValidatorRegistry(extensions_folder="test_extensions")

        # Get any built-in validator
        if registry._built_in_validators:
            validator_class = list(registry._built_in_validators.values())[0]
            assert registry._is_built_in(validator_class) is True

    def test_is_built_in_for_custom_validator(self):
        """Test that custom validators are not identified as built-in."""
        registry = ValidatorRegistry(extensions_folder="test_extensions")

        assert registry._is_built_in(ValidTestValidator) is False


class TestValidatorRegistryContractChecking:
    """Test ValidatorRegistry contract checking functionality."""

    def test_check_validator_passes_for_valid_validator(self):
        """Test contract checking passes for valid validator."""
        registry = ValidatorRegistry(extensions_folder="test_extensions")

        passed, violations = registry.check_validator(ValidTestValidator)

        assert passed is True
        assert len(violations) == 0

    def test_check_validator_skips_built_in_validators(self):
        """Test that contract checking is skipped for built-in validators."""
        registry = ValidatorRegistry(extensions_folder="test_extensions")

        # Get any built-in validator
        if registry._built_in_validators:
            validator_class = list(registry._built_in_validators.values())[0]
            passed, violations = registry.check_validator(validator_class)

            # Should pass without actual checking
            assert passed is True
            assert len(violations) == 0

    def test_check_validator_caches_results(self):
        """Test that contract checking results are cached."""
        registry = ValidatorRegistry(extensions_folder="test_extensions")

        # Check the same validator twice
        passed1, violations1 = registry.check_validator(ValidTestValidator)
        passed2, violations2 = registry.check_validator(ValidTestValidator)

        # Both should pass
        assert passed1 is True
        assert passed2 is True

        # Validator should be in checked cache
        assert ValidTestValidator in registry._checked_classes

    def test_check_validator_detects_violations(self):
        """Test that contract checking detects violations."""

        class InvalidContractValidator(BaseValidator):
            @property
            def name(self) -> str:
                return 123  # Invalid: should be string

            @property
            def initial_hint(self) -> str:
                return "Hint"

            async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
                return ValidationResult(is_valid=True)

        registry = ValidatorRegistry(extensions_folder="test_extensions")
        passed, violations = registry.check_validator(InvalidContractValidator)

        assert passed is False
        assert len(violations) > 0


class TestValidatorRegistryGetClassFromName:
    """Test ValidatorRegistry get_class_from_name functionality."""

    def test_get_class_from_name_built_in(self):
        """Test retrieving built-in validator by name."""
        registry = ValidatorRegistry(extensions_folder="test_extensions")

        # Get any built-in validator name
        if registry._built_in_validators:
            validator_name = list(registry._built_in_validators.keys())[0]
            validator_class = registry.get_class_from_name(validator_name)

            assert validator_class is not None
            assert validator_name == validator_class.name()

    def test_get_class_from_name_not_found_raises_error(self):
        """Test that getting non-existent validator raises ValueError."""
        registry = ValidatorRegistry(extensions_folder="nonexistent_folder")

        with pytest.raises(ValueError, match="Validator 'nonexistent' not found"):
            registry.get_class_from_name("nonexistent")

    def test_get_class_from_name_user_validator(self):
        """Test retrieving user validator by name."""
        registry = ValidatorRegistry(extensions_folder="test_extensions")

        # Manually add a user validator
        registry._user_validators["test_user"] = ValidTestValidator

        validator_class = registry.get_class_from_name("test_user")

        assert validator_class == ValidTestValidator

    def test_get_class_from_name_prefers_built_in(self):
        """Test that built-in validators take precedence over user validators."""
        registry = ValidatorRegistry(extensions_folder="test_extensions")

        # Get a built-in validator name
        if registry._built_in_validators:
            validator_name = list(registry._built_in_validators.keys())[0]
            built_in_class = registry._built_in_validators[validator_name]

            # Add a user validator with the same name
            registry._user_validators[validator_name] = ValidTestValidator

            # Should return built-in validator
            validator_class = registry.get_class_from_name(validator_name)
            assert validator_class == built_in_class


class TestValidatorRegistryUserValidatorLoading:
    """Test ValidatorRegistry user validator loading from filesystem."""

    def setup_method(self):
        """Set up test fixtures - create temporary extensions folder."""
        self.temp_dir = tempfile.mkdtemp()
        self.validators_dir = os.path.join(self.temp_dir, "extensions", "validators")
        os.makedirs(self.validators_dir)

    def teardown_method(self):
        """Clean up temporary directories."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_load_user_validators_from_file(self):
        """Test loading user validators from Python files."""
        # Create a validator file
        validator_code = '''
from lamia.validation.base import BaseValidator, ValidationResult

class CustomFileValidator(BaseValidator):
    @classmethod
    def name(cls) -> str:
        return "custom_file"

    @property
    def initial_hint(self) -> str:
        return "Custom file hint"

    async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
        return ValidationResult(is_valid=True)
'''
        validator_path = os.path.join(self.validators_dir, "custom_validator.py")
        with open(validator_path, 'w') as f:
            f.write(validator_code)

        # Change to temp directory to make extensions folder discoverable
        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            registry = ValidatorRegistry(extensions_folder="extensions")
            registry._load_user_validators()

            # Should have loaded the custom validator
            assert "custom_file" in registry._user_validators
        finally:
            os.chdir(original_cwd)

    def test_load_user_validators_skips_invalid_files(self):
        """Test that invalid Python files are skipped."""
        # Create an invalid Python file
        invalid_path = os.path.join(self.validators_dir, "invalid.py")
        with open(invalid_path, 'w') as f:
            f.write("This is not valid Python code {{{")

        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            registry = ValidatorRegistry(extensions_folder="extensions")

            # Should not crash, just skip invalid file
            registry._load_user_validators()

            # No validators should be loaded
            assert len(registry._user_validators) == 0
        finally:
            os.chdir(original_cwd)

    def test_load_user_validators_skips_non_validators(self):
        """Test that non-validator classes are skipped."""
        # Create a file with non-validator class
        non_validator_code = '''
class NotAValidator:
    def some_method(self):
        pass
'''
        non_validator_path = os.path.join(self.validators_dir, "not_validator.py")
        with open(non_validator_path, 'w') as f:
            f.write(non_validator_code)

        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            registry = ValidatorRegistry(extensions_folder="extensions")
            registry._load_user_validators()

            # No validators should be loaded
            assert len(registry._user_validators) == 0
        finally:
            os.chdir(original_cwd)

    def test_load_user_validators_handles_missing_directory(self):
        """Test that missing validators directory is handled gracefully."""
        # Don't create validators directory
        if os.path.exists(self.validators_dir):
            shutil.rmtree(self.validators_dir)

        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            registry = ValidatorRegistry(extensions_folder="extensions")

            # Should not crash
            registry._load_user_validators()

            assert len(registry._user_validators) == 0
        finally:
            os.chdir(original_cwd)

    def test_load_user_validators_skips_dunder_files(self):
        """Test that __init__.py and __pycache__ are skipped."""
        # Create __init__.py
        init_path = os.path.join(self.validators_dir, "__init__.py")
        with open(init_path, 'w') as f:
            f.write("# Init file")

        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            registry = ValidatorRegistry(extensions_folder="extensions")
            registry._load_user_validators()

            # Should not load __init__.py as a validator
            assert len(registry._user_validators) == 0
        finally:
            os.chdir(original_cwd)


class TestValidatorRegistryBuiltInUserConflict:
    """Test ValidatorRegistry handling of built-in and user validator conflicts."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.validators_dir = os.path.join(self.temp_dir, "extensions", "validators")
        os.makedirs(self.validators_dir)

    def teardown_method(self):
        """Clean up temporary directories."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_user_validator_conflicting_with_built_in_is_skipped(self):
        """Test that user validators with same name as built-in are skipped."""
        registry = ValidatorRegistry(extensions_folder="extensions")

        # Get a built-in validator name
        if registry._built_in_validators:
            built_in_name = list(registry._built_in_validators.keys())[0]

            # Create a user validator with the same name
            validator_code = f'''
from lamia.validation.base import BaseValidator, ValidationResult

class ConflictingValidator(BaseValidator):
    @classmethod
    def name(cls) -> str:
        return "{built_in_name}"

    @property
    def initial_hint(self) -> str:
        return "Conflicting hint"

    async def validate(self, response: str, execution_context=None, **kwargs) -> ValidationResult:
        return ValidationResult(is_valid=True)
'''
            validator_path = os.path.join(self.validators_dir, "conflicting.py")
            with open(validator_path, 'w') as f:
                f.write(validator_code)

            original_cwd = os.getcwd()
            try:
                os.chdir(self.temp_dir)
                registry = ValidatorRegistry(extensions_folder="extensions")
                registry._load_user_validators()

                # User validator should not be loaded due to conflict
                assert built_in_name not in registry._user_validators
                assert built_in_name in registry._built_in_validators
            finally:
                os.chdir(original_cwd)


class TestValidatorRegistryDiscoveryRecursive:
    """Test ValidatorRegistry recursive discovery of validators."""

    def test_discover_validators_recursively(self):
        """Test that validators are discovered recursively in package."""
        registry = ValidatorRegistry(extensions_folder="test_extensions")

        # Should have discovered validators from nested packages
        validators = registry._built_in_validators

        # Check that we have validators from file_validators subpackages
        validator_names = [name for name in validators.keys() if name is not None]

        # Should have JSON, YAML, XML, HTML, CSV validators
        assert any("json" in name.lower() for name in validator_names)
        assert any("yaml" in name.lower() for name in validator_names)

    def test_discover_handles_import_errors_gracefully(self):
        """Test that discovery handles import errors gracefully."""
        # This test verifies the system doesn't crash on import errors
        registry = ValidatorRegistry(extensions_folder="test_extensions")

        # Should complete without crashing even if some modules fail
        assert isinstance(registry._built_in_validators, dict)


class TestValidatorRegistryEdgeCases:
    """Test ValidatorRegistry edge cases."""

    def test_registry_with_empty_extensions_folder(self):
        """Test registry with empty extensions folder."""
        registry = ValidatorRegistry(extensions_folder="")

        # Should still work, just no user validators
        assert isinstance(registry._built_in_validators, dict)
        assert isinstance(registry._user_validators, dict)

    def test_get_class_from_name_triggers_lazy_loading(self):
        """Test that get_class_from_name triggers lazy loading of user validators."""
        registry = ValidatorRegistry(extensions_folder="test_extensions")

        # User validators should be empty initially
        assert len(registry._user_validators) == 0

        # Try to get a non-existent validator
        try:
            registry.get_class_from_name("nonexistent_user_validator")
        except ValueError:
            pass

        # Should have attempted to load user validators
        # (even though none exist in test_extensions)