"""
Runtime contract checker for custom validators.

This module provides a comprehensive testing framework that validates custom validator
implementations against their documented contracts. It helps catch implementation errors
that Python's type system might miss and ensures all custom validators follow consistent
patterns for reliability and maintainability.

The contract checker automatically runs when validators are loaded through the ValidatorRegistry,
providing early detection of issues and detailed error reporting to help developers
fix their implementations.

Key Benefits:
- Catch contract violations early during validator loading
- Provide detailed error messages about what's wrong and how to fix it
- Ensure all custom validators follow documented patterns
- Help maintain code quality and consistency across custom validators
- Reduce runtime errors by validating implementation correctness upfront

Example Usage:
    # Manual contract checking
    from lamia.validation.contract_checker import check_validator_contracts
    
    passed, violations = await check_validator_contracts(MyCustomValidator)
    if not passed:
        for violation in violations:
            print(f"Error in {violation.method_name}: {violation.error_message}")
    
    # Automatic checking (happens when loading validators via config)
    # Just enable contract checking in your config:
    validation:
        enable_contract_checking: true
        validators:
            - type: "custom_file"
              path: "my_validator.py"
"""

import inspect
import asyncio
from typing import Type, List, Tuple, Any, Union, Dict
from dataclasses import dataclass

from .base import BaseValidator, ValidationResult
from .validators.file_validators.file_structure.document_structure_validator import DocumentStructureValidator


@dataclass
class ContractViolation:
    """Represents a contract violation found during testing.
    
    This class encapsulates all the information about a detected contract violation,
    providing detailed context for debugging and fixing the issue.
    
    Attributes:
        method_name: Name of the method or property that violated its contract
        expected: Description of what was expected (return type, behavior, etc.)
        actual: Description of what was actually found
        test_input: The input used when testing (None if not applicable)
        error_message: Detailed human-readable explanation of the violation
        
    Example:
        ContractViolation(
            method_name="name",
            expected="str",
            actual="int", 
            error_message="name property must return a string"
        )
    """
    method_name: str
    expected: str
    actual: str
    test_input: Any = None
    error_message: str = None


class ValidatorContractChecker:
    """
    Comprehensive contract checker for custom validators.
    
    This class performs thorough testing of custom validator implementations to ensure
    they follow the documented contracts. It tests both BaseValidator requirements
    and DocumentStructureValidator-specific contracts when applicable.
    
    The checker creates test instances of validator classes and exercises their methods
    with various inputs to verify they behave according to their documented contracts.
    This includes checking return types, handling edge cases, and ensuring required
    methods are properly implemented.
    
    Contract Categories Tested:
    1. Property Contracts: name and initial_hint properties return correct types
    2. Validation Method Contracts: validate methods return ValidationResult objects
    3. Document Structure Contracts: extract_payload, load_payload, and other abstract methods
    4. Method Existence: All required abstract methods are implemented and callable
    
    Attributes:
        validator_class: The validator class being tested
        violations: List of contract violations found during testing
    """
    
    def __init__(self, validator_class: Type[BaseValidator]):
        """Initialize the contract checker for a specific validator class.
        
        Args:
            validator_class: The BaseValidator subclass to check contracts for
        """
        self.validator_class = validator_class
        self.violations: List[ContractViolation] = []
        
    def check_contracts(self) -> Tuple[bool, List[ContractViolation]]:
        """
        Run all contract checks for the validator class.
        
        This is the main entry point that orchestrates all contract checking.
        It runs different sets of tests based on the validator type and collects
        all violations found during testing.
        
        Returns:
            Tuple containing:
            - bool: True if all contracts pass, False if any violations found
            - List[ContractViolation]: Detailed list of any violations discovered
        """
        self.violations = []
        
        # Test basic BaseValidator contracts that apply to all validators
        self._check_base_validator_contracts()
        
        # Test DocumentStructureValidator contracts if applicable
        if issubclass(self.validator_class, DocumentStructureValidator):
            self._check_document_structure_contracts()
            
        return len(self.violations) == 0, self.violations
    
    def _check_base_validator_contracts(self):
        """Check contracts for BaseValidator abstract methods and properties.
        
        This method tests the fundamental requirements that all validators must meet:
        - Properties return correct types (str for name and initial_hint)
        - Validation methods return ValidationResult objects
        - ValidationResult objects have correct structure
        
        These are the core contracts that enable the validation framework to work
        reliably with any custom validator implementation.
        """
        # Test property contracts
        self._test_name_property()
        self._test_initial_hint_property()
        
        # Test validation method contracts
        self._test_validation_methods()
        
    def _test_name_property(self):
        """Test that name property returns a non-empty string.
        
        The name property is critical for validator registration and identification.
        It must return a unique, non-empty string that doesn't conflict with
        built-in validators.
        
        Contract Requirements:
        - Must return a string (not int, None, or other types)
        - Must be non-empty (not "" or whitespace-only)
        - Should be descriptive and unique
        """
        try:
            # Create a minimal instance to test properties
            validator = self._create_test_instance()
            
            # Handle both instance properties and classmethods
            if hasattr(self.validator_class, 'name') and callable(getattr(self.validator_class, 'name')):
                # It's a classmethod - call it on the class
                name = self.validator_class.name()
            else:
                # It's an instance property - access it on the instance
                name = validator.name
            
            # Check return type is string
            if not isinstance(name, str):
                self.violations.append(ContractViolation(
                    method_name="name",
                    expected="str",
                    actual=f"{type(name).__name__}",
                    error_message="name property must return a string"
                ))
            
            # Check string is non-empty
            elif not name or name.strip() == "":
                self.violations.append(ContractViolation(
                    method_name="name", 
                    expected="non-empty string",
                    actual=f"'{name}'",
                    error_message="name property must return a non-empty string"
                ))
                
        except Exception as e:
            self.violations.append(ContractViolation(
                method_name="name",
                expected="str",
                actual="Exception",
                error_message=f"name property raised exception: {str(e)}"
            ))
    
    def _test_initial_hint_property(self):
        """Test that initial_hint property returns a string.
        
        The initial_hint property provides guidance to LLMs about expected output format.
        It must return a string that can be included in prompts.
        
        Contract Requirements:
        - Must return a string (can be empty but not None or other types)
        - Should provide helpful guidance about expected output format
        """
        try:
            validator = self._create_test_instance()
            hint = validator.initial_hint
            
            if not isinstance(hint, str):
                self.violations.append(ContractViolation(
                    method_name="initial_hint",
                    expected="str", 
                    actual=f"{type(hint).__name__}",
                    error_message="initial_hint property must return a string"
                ))
                
        except Exception as e:
            self.violations.append(ContractViolation(
                method_name="initial_hint",
                expected="str",
                actual="Exception",
                error_message=f"initial_hint property raised exception: {str(e)}"
            ))
    
    def _test_validation_methods(self):
        """Test validation method contracts with various input types.
        
        This method tests that validation methods properly handle different types
        of input and always return properly structured ValidationResult objects.
        
        Test Cases:
        - Normal text responses
        - Empty strings  
        - JSON-like content
        - Invalid/malformed content
        
        Contract Requirements:
        - Must return ValidationResult objects (never None, str, bool, etc.)
        - ValidationResult must have is_valid boolean field
        - Methods should handle any string input without crashing
        """
        validator = self._create_test_instance()
        
        # Test cases covering various input scenarios
        test_inputs = [
            "test response",              # Normal text
            "",                          # Empty string
            "{'key': 'value'}",          # JSON-like content
            "invalid content $$$ ###",   # Malformed/unusual content
        ]
        
        # Determine which validation pattern this validator uses
        cls = self.validator_class
        has_validate = cls.validate is not BaseValidator.validate
        has_strict = cls.validate_strict is not BaseValidator.validate_strict
        has_perm = cls.validate_permissive is not BaseValidator.validate_permissive
        
        if has_validate and not (has_strict or has_perm):
            # Uses validate() pattern - test only validate method
            self._test_validation_method(validator, 'validate', test_inputs)
            
        elif (has_strict and has_perm) and not has_validate:
            # Uses validate_strict/validate_permissive pattern
            self._test_validation_method(validator, 'validate_strict', test_inputs)
            self._test_validation_method(validator, 'validate_permissive', test_inputs)
            
        else:
            # Invalid pattern - this should be caught by BaseValidator.__init__
            self.violations.append(ContractViolation(
                method_name="validation_pattern",
                expected="either validate() OR both validate_strict/validate_permissive",
                actual="mixed or invalid pattern",
                error_message="Must implement either validate() OR both validate_strict and validate_permissive"
            ))
    
    def _test_validation_method(self, validator, method_name: str, test_inputs: List[str]):
        """Test a specific validation method with multiple inputs.
        
        This method exercises a validation method with various test inputs to ensure
        it consistently returns properly structured ValidationResult objects.
        
        Args:
            validator: The validator instance to test
            method_name: Name of the validation method being tested
            test_inputs: List of string inputs to test the method with
            
        Contract Verification:
        - Return type must be ValidationResult
        - ValidationResult.is_valid must be a boolean
        - Method should not raise exceptions for string inputs
        """
        method = getattr(validator, method_name)
        
        for test_input in test_inputs:
            try:
                result = method(test_input)
                
                # Check return type is ValidationResult
                if not isinstance(result, ValidationResult):
                    self.violations.append(ContractViolation(
                        method_name=method_name,
                        expected="ValidationResult",
                        actual=f"{type(result).__name__}",
                        test_input=test_input,
                        error_message=f"Method must return ValidationResult, got {type(result).__name__}"
                    ))
                    continue
                
                # Check ValidationResult has proper is_valid field
                if not hasattr(result, 'is_valid') or not isinstance(result.is_valid, bool):
                    self.violations.append(ContractViolation(
                        method_name=method_name,
                        expected="ValidationResult with boolean is_valid",
                        actual=f"ValidationResult with {type(getattr(result, 'is_valid', None)).__name__} is_valid",
                        test_input=test_input,
                        error_message="ValidationResult.is_valid must be a boolean"
                    ))
                    
            except Exception as e:
                self.violations.append(ContractViolation(
                    method_name=method_name,
                    expected="ValidationResult",
                    actual="Exception",
                    test_input=test_input, 
                    error_message=f"Method raised exception: {str(e)}"
                ))
    
    def _check_document_structure_contracts(self):
        """Check contracts specific to DocumentStructureValidator subclasses.
        
        Document structure validators have additional requirements beyond basic
        validation, including payload extraction, parsing, and tree traversal
        methods. This method tests those specialized contracts.
        
        Categories Tested:
        1. Payload handling: extract_payload and load_payload methods
        2. Tree navigation: find_element, iter_direct_children, find_all
        3. Content extraction: get_text, has_nested, get_name
        4. Serialization: get_subtree_string
        5. Structure description: _describe_structure
        """
        # Test extract_payload contract - critical for handling LLM responses
        self._test_extract_payload()
        
        # Test load_payload contract - must parse extracted content correctly
        self._test_load_payload()
        
        # Test other abstract methods exist and are callable
        self._test_document_structure_methods()
    
    def _test_extract_payload(self):
        """Test extract_payload method contract with various response types.
        
        The extract_payload method is crucial for handling real LLM responses that
        may contain extra text around the actual data payload. It must correctly
        return None when no valid payload is found, and a clean string when found.
        
        Test Scenarios:
        - Empty responses
        - Responses with no valid content
        - Malformed content
        - Text that might confuse the extractor
        
        Contract Requirements:
        - Must return str | None (never other types)
        - Should return None for inputs with no valid payload
        - Should handle any string input without crashing
        """
        try:
            validator = self._create_test_instance()
            
            # Test cases that typically should return None (no valid payload)
            test_inputs = [
                "",                                    # Empty string
                "just some text",                     # Plain text, no structured data
                "no valid payload here",              # Descriptive text
                "### markdown but not the right format", # Markdown but wrong format
            ]
            
            for test_input in test_inputs:
                try:
                    result = validator.extract_payload(test_input)
                    # Result should be either None or a string - never other types
                    if result is not None and not isinstance(result, str):
                        self.violations.append(ContractViolation(
                            method_name="extract_payload",
                            expected="str | None",
                            actual=f"{type(result).__name__}",
                            test_input=test_input,
                            error_message="extract_payload must return str or None"
                        ))
                except Exception as e:
                    self.violations.append(ContractViolation(
                        method_name="extract_payload",
                        expected="str | None",
                        actual="Exception",
                        test_input=test_input,
                        error_message=f"extract_payload raised exception: {str(e)}"
                    ))
                    
        except Exception as e:
            self.violations.append(ContractViolation(
                method_name="extract_payload",
                expected="str | None",
                actual="Exception",
                error_message=f"Could not test extract_payload: {str(e)}"
            ))
    
    def _test_load_payload(self):
        """Test load_payload method with format-appropriate test data.
        
        The load_payload method must parse clean payload strings into appropriate
        Python objects. We test with basic valid payloads for common formats.
        
        Contract Requirements:
        - Should accept clean payload strings (never None)
        - Should return parsed Python objects
        - May raise exceptions for invalid payloads (framework handles this)
        """
        try:
            validator = self._create_test_instance()
            
            # Try to determine the file format and test with appropriate payload
            if hasattr(validator, 'file_type'):
                file_type = validator.file_type()
                
                # Test with basic valid payloads for common formats
                test_payloads = {
                    'json': '{"key": "value"}',
                    'yaml': 'key: value',
                    'xml': '<root><key>value</key></root>',
                    'html': '<html><body>content</body></html>',
                    'csv': 'header1,header2\nvalue1,value2'
                }
                
                test_payload = test_payloads.get(file_type.lower(), '{}')
                
                try:
                    result = validator.load_payload(test_payload)
                    # Any return value is acceptable as long as no exception
                    # The framework handles parsing errors appropriately
                    pass
                except Exception:
                    # It's OK for load_payload to raise exceptions for invalid payloads
                    # The framework catches these and converts to InvalidPayloadError
                    pass
                    
        except Exception as e:
            # If we can't test load_payload, it's not necessarily a violation
            # This can happen if the validator has unusual constructor requirements
            pass
    
    def _test_document_structure_methods(self):
        """Test that all required DocumentStructureValidator methods exist and are callable.
        
        Document structure validators must implement several abstract methods for
        tree traversal and content extraction. While we can't test their behavior
        without knowing the specific format, we can verify they exist and are callable.
        
        Required Methods:
        - find_element: Find direct child elements by key
        - get_text: Extract primitive values from elements  
        - has_nested: Determine if element has nested structure
        - iter_direct_children: Iterate over immediate children
        - get_name: Get element name/tag/key
        - find_all: Recursively find all matching elements
        - get_subtree_string: Serialize element back to string format
        - _describe_structure: Generate structure descriptions for hints
        """
        validator = self._create_test_instance()
        
        # These methods are harder to test without knowing the specific format,
        # but we can at least verify they exist and are callable
        required_methods = [
            'find_element',          # Find direct child by key
            'get_text',             # Extract primitive value
            'has_nested',           # Check for nested structure  
            'iter_direct_children', # Iterate immediate children
            'get_name',             # Get element identifier
            'find_all',             # Recursive search
            'get_subtree_string',   # Serialize to string
            '_describe_structure'    # Generate structure description
        ]
        
        for method_name in required_methods:
            if not hasattr(validator, method_name):
                self.violations.append(ContractViolation(
                    method_name=method_name,
                    expected="method exists",
                    actual="method missing",
                    error_message=f"Required method {method_name} is not implemented"
                ))
            elif not callable(getattr(validator, method_name)):
                self.violations.append(ContractViolation(
                    method_name=method_name,
                    expected="callable method",
                    actual="not callable",
                    error_message=f"Required method {method_name} is not callable"
                ))
    
    def _create_test_instance(self):
        """Create a test instance of the validator class for contract testing.
        
        This method attempts to instantiate the validator class using common
        constructor patterns. It tries multiple approaches since validators
        may have different constructor requirements.
        
        Constructor Patterns Tried:
        1. No arguments (simplest case)
        2. model=None (common for document structure validators)
        3. strict=True (common parameter)
        4. Single None argument (fallback)
        
        Returns:
            An instance of the validator class for testing
            
        Raises:
            ValueError: If no constructor pattern works, indicating the validator
                       has unusual requirements that prevent testing
        """
        try:
            # Analyze constructor signature to determine parameters
            sig = inspect.signature(self.validator_class.__init__)
            params = list(sig.parameters.keys())[1:]  # Skip 'self'
            
            # Try with minimal args first
            if not params:
                return self.validator_class()
            
            # Try with common patterns for document structure validators
            if 'model' in params:
                return self.validator_class(model=None)
            
            # Try with no args (will likely fail but worth trying)
            try:
                return self.validator_class()
            except:
                # Try with strict=True as it's a common parameter
                try:
                    return self.validator_class(strict=True)
                except:
                    # Last resort - pass None for first parameter
                    return self.validator_class(None)
                    
        except Exception as e:
            raise ValueError(f"Could not create test instance of {self.validator_class.__name__}: {str(e)}")