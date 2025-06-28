import pytest
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
    "markdown": "# A Heading",
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

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("with_code_fences", [True, False])
@pytest.mark.parametrize("validator_class, payload_key, model", VALIDATOR_CONFIGS)
async def test_reply_hint_generation_after_response_with_enclosing_texts(strict, with_code_fences, validator_class, payload_key, model):
    # Skip markdown validators without code fences since they require triple backticks
    if (validator_class in [MarkdownValidator, MarkdownStructureValidator] and not with_code_fences):
        pytest.skip("Markdown validators require triple backticks, skipping without code fences test")
    
    if model is None:
        validator = validator_class(strict=strict, generate_hints=True)
    else:
        validator = validator_class(strict=strict, generate_hints=True, model=model)
    
    payload = PAYLOADS[payload_key]
    
    chatty_response = create_chatty_response(payload, with_code_fences)
    
    result = await validator.validate(chatty_response)
    
    assert result.is_valid is not strict
    if strict:
        assert result.error_message in result.hint
        assert validator.initial_hint in result.hint
    else:
        assert result.hint is None
        assert result.validated_text == payload
        assert result.raw_text == chatty_response

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("is_markdown", [True, False])
@pytest.mark.parametrize("validator_class, payload_key, model", VALIDATOR_CONFIGS)
async def test_reply_hint_generation_for_invalid_payload(strict, is_markdown, validator_class, payload_key, model):
    if model is None:
        validator = validator_class(strict=strict, generate_hints=True)
    else:
        validator = validator_class(strict=strict, generate_hints=True, model=model)
    
    payload = INVALID_PAYLOADS[payload_key]
    
    chatty_response = create_chatty_response(payload, is_markdown)
    
    result = await validator.validate(chatty_response)
    
    assert result.is_valid is False
    assert result.hint is not None
    assert result.error_message is not None
    
    # Check that the hint contains both the error message and initial hint
    assert result.error_message in result.hint
    assert validator.initial_hint in result.hint

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("is_markdown", [True, False])
@pytest.mark.parametrize("validator_class, payload_key, model", VALIDATOR_CONFIGS)
async def test_no_hint_generation_when_hiniting_diabled_for_invalid_payload(strict, is_markdown, validator_class, payload_key, model):
    if model is None:
        validator = validator_class(strict=strict)
    else:
        validator = validator_class(strict=strict, model=model)
    
    payload = INVALID_PAYLOADS[payload_key]
    
    chatty_response = create_chatty_response(payload, is_markdown)
    
    result = await validator.validate(chatty_response)
    
    assert result.is_valid is False
    assert result.hint is None