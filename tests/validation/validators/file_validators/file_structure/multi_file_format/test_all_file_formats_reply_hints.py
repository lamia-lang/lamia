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
    heading: str

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
    "csv": "col1col2\nhello,123",
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

def create_chatty_response(payload: str, for_markdown: bool = False) -> str:
    if for_markdown:
        return f"Of course, here is the file you requested:\n\n```{payload}```\n\nLet me know if you need anything else!"
    else:  # without_markdown
        return f"Here's the content you requested:\n\n{payload}\n\nHope this helps!"

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("is_markdown", [True, False])
@pytest.mark.parametrize("validator_class, payload_key, model", VALIDATOR_CONFIGS)
async def test_reply_hint_generation_after_response_with_enclosing_texts(strict, is_markdown, validator_class, payload_key, model):
    if model is None:
        validator = validator_class(strict=strict, generate_hints=True)
    else:
        validator = validator_class(strict=strict, generate_hints=True, model=model)
    
    payload = PAYLOADS[payload_key]
    
    chatty_response = create_chatty_response(payload, is_markdown)
    
    result = await validator.validate(chatty_response)
    
    assert result.is_valid is not strict
    if strict:
        assert result.hint is not None, "A hint should be provided when generate_hints is True."
        assert "Please ensure" in result.hint or "Please return only" in result.hint
    else:
        assert result.hint is None
        #assert result.validated_text == payload
        #assert result.raw_text == chatty_response

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
    assert "Please ensure" in result.hint or "Please return only" in result.hint

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