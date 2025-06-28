"""
Tests for the validator contract checker.

These tests demonstrate how the contract checker catches various violations
of the documented validator contracts.
"""

import pytest
import asyncio
from typing import Any
from lamia.validation.base import BaseValidator, ValidationResult
from lamia.validation.contract_checker import (
    ValidatorContractChecker, 
    check_validator_contracts,
    ContractViolation
)
from lamia.validation.validators.file_validators.file_structure.document_structure_validator import DocumentStructureValidator


class ValidCodeValidator(BaseValidator):
    """A properly implemented validator that should pass all contract checks."""
    
    @property
    def name(self) -> str:
        return "valid_code"
    
    @property 
    def initial_hint(self) -> str:
        return "Please return valid code."
    
    async def validate(self, response: str, **kwargs) -> ValidationResult:
        return ValidationResult(is_valid=True)


class InvalidNameValidator(BaseValidator):
    """Validator with invalid name property (returns int instead of str)."""
    
    @property
    def name(self) -> str:
        return 123  # Contract violation: should return str
    
    @property
    def initial_hint(self) -> str:
        return "Hint"
    
    async def validate(self, response: str, **kwargs) -> ValidationResult:
        return ValidationResult(is_valid=True)


class EmptyNameValidator(BaseValidator):
    """Validator with empty name property."""
    
    @property
    def name(self) -> str:
        return ""  # Contract violation: should be non-empty
    
    @property
    def initial_hint(self) -> str:
        return "Hint"
    
    async def validate(self, response: str, **kwargs) -> ValidationResult:
        return ValidationResult(is_valid=True)


class InvalidHintValidator(BaseValidator):
    """Validator with invalid initial_hint property."""
    
    @property
    def name(self) -> str:
        return "invalid_hint"
    
    @property
    def initial_hint(self) -> str:
        return None  # Contract violation: should return str
    
    async def validate(self, response: str, **kwargs) -> ValidationResult:
        return ValidationResult(is_valid=True)


class InvalidReturnTypeValidator(BaseValidator):
    """Validator that returns wrong type from validate method."""
    
    @property
    def name(self) -> str:
        return "invalid_return"
    
    @property
    def initial_hint(self) -> str:
        return "Hint"
    
    async def validate(self, response: str, **kwargs) -> ValidationResult:
        return "not a ValidationResult"  # Contract violation


class ValidDocumentStructureValidator(DocumentStructureValidator):
    """A properly implemented document structure validator."""
    
    def __init__(self, model=None, strict=True, generate_hints=False):
        super().__init__(model=model, strict=strict, generate_hints=generate_hints)
    
    @classmethod
    def name(cls) -> str:
        return "valid_document"
    
    @classmethod
    def file_type(cls) -> str:
        return "valid"
    
    def extract_payload(self, response: str) -> str:
        if "valid" in response:
            return response.strip()
        return None  # Correctly returns None when no valid payload
    
    def load_payload(self, payload: str) -> Any:
        return {"data": payload}
    
    def find_element(self, tree, key):
        return tree.get(key) if isinstance(tree, dict) else None
    
    def get_text(self, element):
        return element
    
    def has_nested(self, element):
        return isinstance(element, dict)
    
    def iter_direct_children(self, tree):
        if isinstance(tree, dict):
            for v in tree.values():
                yield v
    
    def get_name(self, element):
        return "element"
    
    def find_all(self, tree, key):
        return []
    
    def get_subtree_string(self, elem):
        return str(elem)
    
    def _describe_structure(self, model, indent=0):
        return ["structure description"]


class InvalidExtractPayloadValidator(DocumentStructureValidator):
    """Document validator that violates extract_payload contract."""
    
    def __init__(self, model=None, strict=True, generate_hints=False):
        super().__init__(model=model, strict=strict, generate_hints=generate_hints)
    
    @classmethod
    def name(cls) -> str:
        return "invalid_extract"
    
    @classmethod
    def file_type(cls) -> str:
        return "invalid"
    
    def extract_payload(self, response: str) -> str:
        return 123  # Contract violation: should return str or None
    
    def load_payload(self, payload: str) -> Any:
        return payload
    
    def find_element(self, tree, key):
        return None
    
    def get_text(self, element):
        return element
    
    def has_nested(self, element):
        return False
    
    def iter_direct_children(self, tree):
        return iter([])
    
    def get_name(self, element):
        return "element"
    
    def find_all(self, tree, key):
        return []
    
    def get_subtree_string(self, elem):
        return str(elem)
    
    def _describe_structure(self, model, indent=0):
        return []


@pytest.mark.asyncio
async def test_valid_validator_passes_all_checks():
    """Test that a properly implemented validator passes all contract checks."""
    passed, violations = await check_validator_contracts(ValidCodeValidator)
    
    assert passed is True
    assert len(violations) == 0


@pytest.mark.asyncio
async def test_invalid_name_type_detected():
    """Test that invalid name property type is detected."""
    passed, violations = await check_validator_contracts(InvalidNameValidator)
    
    assert passed is False
    assert len(violations) >= 1
    
    # Find the name violation
    name_violations = [v for v in violations if v.method_name == "name"]
    assert len(name_violations) >= 1
    
    violation = name_violations[0]
    assert violation.expected == "str"
    assert violation.actual == "int"


@pytest.mark.asyncio
async def test_empty_name_detected():
    """Test that empty name property is detected."""
    passed, violations = await check_validator_contracts(EmptyNameValidator)
    
    assert passed is False
    assert len(violations) >= 1
    
    # Find the name violation
    name_violations = [v for v in violations if v.method_name == "name"]
    assert len(name_violations) >= 1
    
    violation = name_violations[0]
    assert "non-empty string" in violation.expected


@pytest.mark.asyncio
async def test_invalid_hint_type_detected():
    """Test that invalid initial_hint property type is detected."""
    passed, violations = await check_validator_contracts(InvalidHintValidator)
    
    assert passed is False
    assert len(violations) >= 1
    
    # Find the hint violation
    hint_violations = [v for v in violations if v.method_name == "initial_hint"]
    assert len(hint_violations) >= 1
    
    violation = hint_violations[0]
    assert violation.expected == "str"
    assert violation.actual == "NoneType"


@pytest.mark.asyncio 
async def test_invalid_validation_return_type_detected():
    """Test that wrong return type from validate method is detected."""
    passed, violations = await check_validator_contracts(InvalidReturnTypeValidator)
    
    assert passed is False
    assert len(violations) >= 1
    
    # Find validation method violations
    validation_violations = [v for v in violations if "validate" in v.method_name]
    assert len(validation_violations) >= 1


@pytest.mark.asyncio
async def test_valid_document_structure_validator_passes():
    """Test that a properly implemented document structure validator passes."""
    passed, violations = await check_validator_contracts(ValidDocumentStructureValidator)
    
    assert passed is True
    assert len(violations) == 0


@pytest.mark.asyncio
async def test_invalid_extract_payload_detected():
    """Test that wrong return type from extract_payload is detected."""
    passed, violations = await check_validator_contracts(InvalidExtractPayloadValidator)
    
    assert passed is False
    assert len(violations) >= 1
    
    # Find extract_payload violations
    extract_violations = [v for v in violations if v.method_name == "extract_payload"]
    assert len(extract_violations) >= 1
    
    violation = extract_violations[0]
    assert violation.expected == "str | None"
    assert violation.actual == "int"


@pytest.mark.asyncio
async def test_contract_checker_direct_usage():
    """Test using the ValidatorContractChecker directly."""
    checker = ValidatorContractChecker(ValidCodeValidator)
    passed, violations = await checker.check_contracts()
    
    assert passed is True
    assert len(violations) == 0


class BrokenConstructorValidator(BaseValidator):
    """Validator that can't be instantiated due to broken constructor."""
    
    def __init__(self, required_param, another_required_param):
        # Missing super() call and requires TWO parameters - can't be instantiated with None
        if required_param is None or another_required_param is None:
            raise TypeError("Both parameters are required and cannot be None")
        self.required_param = required_param
        self.another_required_param = another_required_param
    
    @property
    def name(self) -> str:
        return "broken_constructor"
    
    @property
    def initial_hint(self) -> str:
        return "Hint"
    
    async def validate(self, response: str, **kwargs) -> ValidationResult:
        return ValidationResult(is_valid=True)


@pytest.mark.asyncio
async def test_broken_constructor_handled_gracefully():
    """Test that validators with broken constructors are handled gracefully."""
    # This should raise an exception about not being able to create test instance
    with pytest.raises(ValueError, match="Could not create test instance"):
        checker = ValidatorContractChecker(BrokenConstructorValidator)
        await checker.check_contracts()


@pytest.mark.asyncio
async def test_multiple_violations_detected():
    """Test that multiple violations in the same validator are all detected."""
    
    class MultipleViolationsValidator(BaseValidator):
        @property
        def name(self) -> str:
            return 42  # Violation 1: wrong type
        
        @property
        def initial_hint(self) -> str:
            return ["not", "a", "string"]  # Violation 2: wrong type
        
        async def validate(self, response: str, **kwargs) -> ValidationResult:
            return None  # Violation 3: wrong return type
    
    passed, violations = await check_validator_contracts(MultipleViolationsValidator)
    
    assert passed is False
    assert len(violations) >= 3  # Should find at least 3 violations
    
    # Check we have violations for different methods
    methods_with_violations = {v.method_name for v in violations}
    assert "name" in methods_with_violations
    assert "initial_hint" in methods_with_violations
    # validate method violations might be captured under different names depending on implementation


if __name__ == "__main__":
    # Run a quick demo
    async def demo():
        print("=== Contract Checker Demo ===")
        
        # Test valid validator
        print("\n1. Testing valid validator...")
        passed, violations = await check_validator_contracts(ValidCodeValidator)
        print(f"Valid validator passed: {passed}")
        
        # Test invalid validator
        print("\n2. Testing validator with contract violations...")
        passed, violations = await check_validator_contracts(InvalidNameValidator)
        print(f"Invalid validator passed: {passed}")
        print(f"Violations found: {len(violations)}")
        for v in violations:
            print(f"  - {v.method_name}: {v.error_message}")
        
        print("\n=== Demo Complete ===")
    
    asyncio.run(demo()) 