import pytest
import re
from pydantic import BaseModel
from lamia.validation.validators import (
    HTMLValidator, HTMLStructureValidator,
    JSONValidator, JSONStructureValidator,
    XMLValidator, XMLStructureValidator,
    YAMLValidator, YAMLStructureValidator,
    CSVValidator, CSVStructureValidator,
    MarkdownValidator, MarkdownStructureValidator,
)
from lamia.validation.validators.file_validators.file_structure.markdown_structure_validator import Heading1
from lamia.validation.validators.file_validators.file_structure.document_structure_validator import DocumentStructureValidator

# --- Test Models for Structure Validators ---
class SimpleHTML(BaseModel):
    body: str

class SimpleJSON(BaseModel):
    message: str

class SimpleXML(BaseModel):
    message: str

class SimpleYAML(BaseModel):
    message: str

class SimpleCSV(BaseModel):
    col1: str
    col2: int

class SimpleMD(BaseModel):
    heading: Heading1

# --- Test Payloads ---
PAYLOADS = {
    "html": "<html><body>Hello</body></html>",
    "json": '{"message": "hello"}',
    "xml": "<root><message>hello</message></root>",
    "yaml": "message: hello",
    "csv": "col1,col2\nhello,123",
    "markdown": "# A Heading",
}

INVALID_PAYLOADS = {
    "html": "html><body>Hello</body></html>",
    "json": '"message": "hello}',
    "xml": "root><message>hello</message></root>",
    "yaml": "invalid_map: { hello",
    "csv": "col1,col2\nhello123",
    "markdown": "## Heading2",
}

# --- Validator Configurations ---
VALIDATOR_CONFIGS = [
    # Simple Validators (well-formedness check)
    (HTMLValidator, "html", None),
    (JSONValidator, "json", None),
    (XMLValidator, "xml", None),
    (YAMLValidator, "yaml", None),
    (CSVValidator, "csv", None),
    (MarkdownValidator, "markdown", None),
    # Structure Validators
    (HTMLStructureValidator, "html", SimpleHTML),
    (JSONStructureValidator, "json", SimpleJSON),
    (XMLStructureValidator, "xml", SimpleXML),
    (YAMLStructureValidator, "yaml", SimpleYAML),
    (CSVStructureValidator, "csv", SimpleCSV),
    (MarkdownStructureValidator, "markdown", SimpleMD),
]

def create_chatty_response(payload: str, with_code_fences: bool = False) -> str:
    if with_code_fences:
        return f"Of course, here is the file you requested:\n\n```{payload}```\n\nLet me know if you need anything else!"
    else:
        return f"Here's the content you requested:\n\n{payload}\n\nHope this helps!"

def _contains_error_class_path(message: str) -> bool:
    """Check if message contains a full error class path."""
    # Pattern to match module paths ending with "Error"
    # e.g., "lamia.validation.validators.file_validators.file_structure.document_structure_validator.TextAroundPayloadError"
    pattern = r'[a-zA-Z_][a-zA-Z0-9_.]*\.[A-Z][a-zA-Z0-9]*Error'
    return bool(re.search(pattern, message))

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("with_code_fences", [True, False])
@pytest.mark.parametrize("validator_class, payload_key, model", VALIDATOR_CONFIGS)
async def test_reply_hint_generation_after_response_with_enclosing_texts(strict, with_code_fences, validator_class, payload_key, model):

    
    if model is None:
        validator = validator_class(strict=strict, generate_hints=True)
    else:
        validator = validator_class(strict=strict, generate_hints=True, model=model)
    
    payload = PAYLOADS[payload_key]
    
    chatty_response = create_chatty_response(payload, with_code_fences)
    
    result = await validator.validate(chatty_response)

    # Markdown validators always need code fences and unlike other file types they will work
    # the same for strict and permissive modes. They will work with fences and will fail withut
    if (validator_class in [MarkdownValidator, MarkdownStructureValidator]):
        if not with_code_fences:
            assert result.is_valid is False, "Markdown validators require triple backticks, skipping without code fences test"
            assert "Please provide your Markdown content wrapped in triple backticks" in result.hint
            return 
        else:
            assert result.is_valid is True, "Markdown validators with code fences should be valid for strict and permissive modes"
            return 
    
    assert result.is_valid is not strict
    if strict:
        assert "unexpected text around payload" in result.hint
        assert validator.initial_hint in result.hint
        assert result.raw_text == chatty_response
        # Ensure no error class paths leak through hints
        assert not _contains_error_class_path(result.hint), f"Hint contains error class path: {result.hint}"
    else:
        assert result.hint is None
        assert result.validated_text.replace(" ", "").replace("\n", "") == payload.replace(" ", "").replace("\n", "")
        assert result.raw_text == chatty_response

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("with_code_fences", [True, False])
@pytest.mark.parametrize("validator_class, payload_key, model", VALIDATOR_CONFIGS)
async def test_reply_hint_generation_for_invalid_payload(strict, with_code_fences, validator_class, payload_key, model):
    if model is None:
        validator = validator_class(strict=strict, generate_hints=True)
    else:
        validator = validator_class(strict=strict, generate_hints=True, model=model)
    
    payload = INVALID_PAYLOADS[payload_key]
    
    chatty_response = create_chatty_response(payload, with_code_fences)
    
    result = await validator.validate(chatty_response)
    
    if validator_class == MarkdownValidator:
        if not with_code_fences:
            assert result.is_valid is False, "Markdown validators require triple backticks, skipping without code fences test"
            assert "Invalid Response: the markdown is not wrapped in triple backticks" in result.hint
            return
        # it is actaully impossible to have invalid markdown if we have code fences
        else:
            assert result.is_valid is True, "Markdown validators with code fences should be valid for strict and permissive modes"
            return
 
    assert result.is_valid is False
    assert result.hint is not None
    assert result.error_message is not None
    # Ensure no error class paths leak through hints or error messages
    assert not _contains_error_class_path(result.hint), f"Hint contains error class path: {result.hint}"
    assert not _contains_error_class_path(result.error_message), f"Error message contains error class path: {result.error_message}"
    if validator_class == MarkdownStructureValidator:
        if with_code_fences:
            assert result.is_valid is False, "Markdown validators with code fences should be valid for strict and permissive modes"
            assert "Missing element(s) for field(s): heading" in result.hint
            return 
        else:
            assert result.is_valid is False, "Markdown validators require triple backticks, skipping without code fences test"
            assert "Invalid Response: the markdown is not wrapped in triple backticks" in result.hint
            return

    
    if strict:
        assert f"no valid {payload_key} payload is found in the text" in result.hint
        assert validator.initial_hint in result.hint
        assert result.raw_text == chatty_response
    else:
        assert f"no valid {payload_key} payload is found in the text" in result.hint
        assert validator.initial_hint in result.hint
        assert result.raw_text == chatty_response

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("is_markdown", [True, False])
@pytest.mark.parametrize("validator_class, payload_key, model", VALIDATOR_CONFIGS)
async def test_no_hint_generation_when_hinting_disabled_for_invalid_payload(strict, is_markdown, validator_class, payload_key, model):
    if model is None:
        validator = validator_class(strict=strict)
    else:
        validator = validator_class(strict=strict, model=model)
    
    payload = INVALID_PAYLOADS[payload_key]
    
    chatty_response = create_chatty_response(payload, is_markdown)
    
    result = await validator.validate(chatty_response)
    
    if validator_class == MarkdownValidator:
        assert result.is_valid is True, "Markdown validators are always valid"
        return 

    assert result.is_valid is False
    assert result.error_message is not None
    # Check that no error class paths leak through error messages
    assert not _contains_error_class_path(result.error_message), f"Error message contains error class path: {result.error_message}"
    # Check hints only if they exist (some validators may generate hints even when hinting is disabled)
    if result.hint is not None:
        assert not _contains_error_class_path(result.hint), f"Hint contains error class path: {result.hint}"
    assert result.validated_text is None
    assert result.raw_text == chatty_response

# --- Test for Nested Exceptions ---
class DummyThrowingNestedExceptionValidator(DocumentStructureValidator):
    """Dummy validator that throws nested exceptions for testing."""
    
    @classmethod
    def name(cls) -> str:
        return "dummy_nested"
    
    @classmethod
    def file_type(cls) -> str:
        return "dummy"
    
    def _describe_structure(self, model, indent=0):
        return ["dummy structure"]
    
    def extract_payload(self, response: str) -> str:
        # This will throw a nested exception
        try:
            # Inner exception
            raise ValueError("Inner parsing error occurred")
        except ValueError as inner_error:
            # Outer exception that wraps the inner one
            raise RuntimeError("Outer wrapper error") from inner_error
    
    def load_payload(self, payload: str):
        pass
    
    def find_element(self, tree, key):
        pass
    
    def get_text(self, element):
        pass
    
    def has_nested(self, element):
        return False
    
    def iter_direct_children(self, tree):
        return []
    
    def get_name(self, element):
        pass
    
    def find_all(self, tree, key):
        return []
    
    def get_subtree_string(self, elem):
        return ""
    
    def get_field_order(self, tree):    
        return []

@pytest.mark.asyncio
async def test_nested_exception_messages_in_hints():
    """Test that both outer and inner exception messages appear in hints when exceptions are chained."""
    
    # Create a validator that will trigger nested exceptions
    validator = DummyThrowingNestedExceptionValidator(model=None, strict=True, generate_hints=True)
    
    # This should cause a nested exception via extract_payload
    test_input = "some test input"
    
    result = await validator.validate(test_input)
    
    assert result.is_valid is False
    assert result.hint is not None
    assert result.error_message is not None
    assert "Outer wrapper error" in result.hint
    assert "Inner parsing error occurred" in result.hint