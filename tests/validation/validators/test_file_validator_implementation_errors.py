import pytest
import asyncio
from lamia.validation.base import BaseValidator, ValidationResult
from lamia.validation.validators.file_validators.file_structure.document_structure_validator import DocumentStructureValidator
from pydantic import BaseModel


class SampleModel(BaseModel):
    title: str
    content: str


def test_file_validator_inheriting_from_document_structure_but_missing_abstract_methods():
    """Test: File validator inheriting from DocumentStructureValidator but not implementing abstract methods should fail"""
    
    class CustomFileValidator(DocumentStructureValidator):
        """A custom file validator that doesn't implement required abstract methods."""
        
        def __init__(self, model=None, strict=True):
            super().__init__(model=model, strict=strict)
        
        @property
        def name(self) -> str:
            return "custom_file"

        @property
        def initial_hint(self) -> str:
            return "Please provide a valid custom file format."
        
        # Missing all abstract methods from DocumentStructureValidator:
        # parse, find_element, get_text, has_nested, iter_direct_children, get_name, find_all
    
    with pytest.raises(TypeError, match="abstract method"):
        CustomFileValidator(model=SampleModel, strict=True)


def test_file_validator_inheriting_from_document_structure_missing_some_abstract_methods():
    """Test: File validator implementing some but not all abstract methods should fail"""
    
    class PartialFileValidator(DocumentStructureValidator):
        """A custom file validator that implements some abstract methods but not all."""
        
        def __init__(self, model=None, strict=True):
            super().__init__(model=model, strict=strict)
        
        @property
        def name(self) -> str:
            return "partial_file"

        @property
        def initial_hint(self) -> str:
            return "Please provide a valid partial file format."
        
        def parse(self, response: str):
            return {"parsed": response}
        
        def find_element(self, tree, key):
            return tree.get(key)
        
        def get_text(self, element):
            return str(element)
        
        # Missing: has_nested, iter_direct_children, get_name, find_all
    
    with pytest.raises(TypeError, match="abstract method"):
        PartialFileValidator(model=SampleModel, strict=True)


def test_file_validator_inheriting_from_document_structure_with_all_abstract_methods_succeeds():
    """Test: File validator implementing all abstract methods should succeed"""
    
    class CompleteFileValidator(DocumentStructureValidator):
        """A custom file validator that implements all required abstract methods."""
        
        def __init__(self, model=None, strict=True):
            super().__init__(model=model, strict=strict)
        
        @property
        def name(self) -> str:
            return "complete_file"

        @property
        def initial_hint(self) -> str:
            return "Please provide a valid complete file format."
        
        def parse(self, response: str):
            # Simple parsing for test
            lines = response.strip().split('\n')
            return {
                'title': lines[0] if lines else '',
                'content': '\n'.join(lines[1:]) if len(lines) > 1 else ''
            }
        
        def find_element(self, tree, key):
            return tree.get(key)
        
        def get_text(self, element):
            return str(element) if element is not None else ''
        
        def has_nested(self, element):
            return isinstance(element, dict) and len(element) > 0
        
        def iter_direct_children(self, tree):
            if isinstance(tree, dict):
                for key, value in tree.items():
                    yield value
        
        def get_name(self, element):
            return getattr(element, '__name__', str(type(element).__name__))
        
        def find_all(self, tree, key):
            results = []
            if isinstance(tree, dict):
                if key in tree:
                    results.append(tree[key])
                for value in tree.values():
                    if isinstance(value, dict):
                        results.extend(self.find_all(value, key))
            return results
        
        def _describe_structure(self, model, indent=0):
            return []

        def extract_payload(self, response: str):
            return response

        @classmethod
        def file_type(cls):
            return "test"

        def get_field_order(self, tree):
            return []

        def get_subtree_string(self, elem):
            return str(elem)

        def load_payload(self, payload: str):
            return payload
    
    # Should instantiate successfully
    validator = CompleteFileValidator(model=SampleModel, strict=True)
    assert validator.name == "complete_file"


def test_file_validator_bypassing_document_structure_inheriting_directly_from_base_succeeds():
    """Test: File validator inheriting directly from BaseValidator (bypassing DocumentStructureValidator) should work"""
    
    class DirectFileValidator(BaseValidator):
        """A file validator that inherits directly from BaseValidator, bypassing DocumentStructureValidator."""
        
        def __init__(self, file_type: str = "txt", strict: bool = True):
            super().__init__(strict=strict)
            self.file_type = file_type
        
        @property
        def name(self) -> str:
            return f"direct_{self.file_type}"

        @property
        def initial_hint(self) -> str:
            return f"Please provide a valid {self.file_type} file."
        
        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            # Simple validation logic
            if not response.strip():
                return ValidationResult(
                    is_valid=False,
                    error_message="File cannot be empty",
                    hint=self.initial_hint
                )
            return ValidationResult(is_valid=True)
            
        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            # More lenient validation
            return ValidationResult(is_valid=True)
    
    # Should instantiate successfully
    validator = DirectFileValidator(file_type="csv", strict=True)
    assert validator.name == "direct_csv"


@pytest.mark.asyncio
async def test_direct_file_validator_validation_works():
    """Test: Direct file validator should work correctly in validation"""
    
    class SimpleFileValidator(BaseValidator):
        """A simple file validator for testing."""
        
        def __init__(self, min_lines: int = 1, strict: bool = True):
            super().__init__(strict=strict)
            self.min_lines = min_lines
        
        @property
        def name(self) -> str:
            return "simple_file"

        @property
        def initial_hint(self) -> str:
            return f"Please provide a file with at least {self.min_lines} lines."
        
        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            lines = response.strip().split('\n')
            if len(lines) < self.min_lines:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"File must have at least {self.min_lines} lines, got {len(lines)}",
                    hint=self.initial_hint
                )
            return ValidationResult(is_valid=True)
            
        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            # Always pass in permissive mode
            return ValidationResult(is_valid=True)
    
    validator = SimpleFileValidator(min_lines=2, strict=True)
    
    # Test strict validation
    result = await validator.validate_strict("line1")
    assert not result.is_valid
    assert "must have at least 2 lines" in result.error_message
    
    result = await validator.validate_strict("line1\nline2")
    assert result.is_valid
    
    # Test permissive validation
    result = await validator.validate_permissive("line1")
    assert result.is_valid


def test_file_validator_with_validate_method_instead_of_strict_permissive():
    """Test: File validator using single validate() method instead of strict/permissive should work"""
    
    class SingleValidateFileValidator(BaseValidator):
        """A file validator that uses single validate() method."""
        
        def __init__(self, extension: str = "txt", strict: bool = True):
            super().__init__(strict=strict)
            self.extension = extension
        
        @property
        def name(self) -> str:
            return f"single_{self.extension}"

        @property
        def initial_hint(self) -> str:
            return f"Please provide content for a {self.extension} file."
        
        async def validate(self, response: str, **kwargs) -> ValidationResult:
            if not response.strip():
                return ValidationResult(
                    is_valid=False,
                    error_message="File content cannot be empty",
                    hint=self.initial_hint
                )
            return ValidationResult(is_valid=True)
    
    # Should instantiate successfully
    validator = SingleValidateFileValidator(extension="json", strict=True)
    assert validator.name == "single_json"


def test_file_validator_cannot_have_both_validate_and_strict_permissive():
    """Test: File validator cannot implement both validate() and validate_strict/validate_permissive"""
    
    class ConflictingFileValidator(BaseValidator):
        """A file validator that incorrectly implements both validation approaches."""
        
        def __init__(self, strict: bool = True):
            super().__init__(strict=strict)
        
        @property
        def name(self) -> str:
            return "conflicting_file"

        @property
        def initial_hint(self) -> str:
            return "Please provide valid file content."
        
        async def validate(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
        
        async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
            
        async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
            return ValidationResult(is_valid=True)
    
    with pytest.raises(TypeError, match="Implement either validate\\(\\) OR validate_strict/validate_permissive, not both\\."):
        ConflictingFileValidator(strict=True) 