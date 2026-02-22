import pytest
from pydantic import BaseModel
from collections import OrderedDict
from lamia.validation.validators import (
    CSVStructureValidator,
    JSONStructureValidator, 
    YAMLStructureValidator,
    XMLStructureValidator,
    HTMLStructureValidator,
    MarkdownStructureValidator
)
from typing import Any
from lamia.validation.validators.file_validators.file_structure.markdown_structure_validator import Heading2, Heading1

# Flat structure models for testing ordered fields
class ModelWithOrderedFields(BaseModel):
    name: str
    age: int
    
    # These fields must maintain order
    __ordered_fields__ = OrderedDict([
        ("field1", int),
        ("field2", str),
    ])

class MarkdownWithOrderedFields(BaseModel):
    bio: Heading2
    
    # These fields must maintain order
    __ordered_fields__ = OrderedDict([
        ("name", Heading1),
        ("contact", Heading2),
    ])

# Nested structure models for testing ordered fields in complex scenarios
class NestedSubModel(BaseModel):
    nested_field1: str
    nested_field2: int

class NestedModelWithOrderedFields(BaseModel):
    simple_field: str
    nested_data: NestedSubModel
    
    # These fields must maintain order
    __ordered_fields__ = OrderedDict([
        ("ordered_field1", int),
        ("ordered_field2", str),
    ])

# --- Test Payloads for Flat Structure Ordering ---
VALID_FLAT_PAYLOADS = {
    "csv": "name,age,field1,field2\nJohn,25,1,test",
    "json": '{"name": "John", "field1": 1, "age": 25, "field2": "test"}',
    "yaml": "name: John\nfield1: 1\nage: 25\nfield2: test",
    "xml": "<root><name>John</name><field1>1</field1><age>25</age><field2>test</field2></root>",
    "html": "<html><name>John</name><field1>1</field1><age>25</age><field2>test</field2></html>",
    "markdown": "## Biography\n\n# John\n\n## Contact \n\n",
}

INVALID_FLAT_PAYLOADS = {
    "csv": "name,age,field2,field1\nJohn,25,test,1",
    "json": '{"name": "John", "field2": "test", "age": 25, "field1": 1}',
    "yaml": "name: John\nfield2: test\nage: 25\nfield1: 1",
    "xml": "<root><name>John</name><field2>test</field2><age>25</age><field1>1</field1></root>",
    "html": "<html><name>John</name><field2>test</field2><age>25</age><field1>1</field1></html>",
    "markdown": "## Biography\n\n ## Contact\n\n# John\n\n ",
}

# --- Test Payloads for Nested Structure Ordering ---
VALID_NESTED_PAYLOADS = {
    "json": '{"simple_field": "test", "ordered_field1": 1, "nested_data": {"nested_field1": "nested", "nested_field2": 42}, "ordered_field2": "second"}',
    "yaml": "simple_field: test\nordered_field1: 1\nnested_data:\n  nested_field1: nested\n  nested_field2: 42\nordered_field2: second",
    "xml": "<root><simple_field>test</simple_field><ordered_field1>1</ordered_field1><nested_data><nested_field1>nested</nested_field1><nested_field2>42</nested_field2></nested_data><ordered_field2>second</ordered_field2></root>",
}

INVALID_NESTED_PAYLOADS = {
    "json": '{"simple_field": "test", "ordered_field2": "second", "nested_data": {"nested_field1": "nested", "nested_field2": 42}, "ordered_field1": 1}',
    "yaml": "simple_field: test\nordered_field2: second\nnested_data:\n  nested_field1: nested\n  nested_field2: 42\nordered_field1: 1",
    "xml": "<root><simple_field>test</simple_field><ordered_field2>second</ordered_field2><nested_data><nested_field1>nested</nested_field1><nested_field2>42</nested_field2></nested_data><ordered_field1>1</ordered_field1></root>",
}

# --- Validator Configurations ---
FLAT_VALIDATOR_CONFIGS = [
    (CSVStructureValidator, "csv", ModelWithOrderedFields),
    (JSONStructureValidator, "json", ModelWithOrderedFields),
    (YAMLStructureValidator, "yaml", ModelWithOrderedFields),
    (XMLStructureValidator, "xml", ModelWithOrderedFields),
    (HTMLStructureValidator, "html", ModelWithOrderedFields),
    (MarkdownStructureValidator, "markdown", MarkdownWithOrderedFields),
]

NESTED_VALIDATOR_CONFIGS = [
    (JSONStructureValidator, "json", NestedModelWithOrderedFields),
    (YAMLStructureValidator, "yaml", NestedModelWithOrderedFields),
    (XMLStructureValidator, "xml", NestedModelWithOrderedFields),
]

@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("validator_class, payload_key, model", FLAT_VALIDATOR_CONFIGS)
@pytest.mark.asyncio
async def test_flat_structure_order_validation_all_formats_valids(strict, validator_class, payload_key, model):
    """Test that all file format validators properly validate field order during extraction for flat structures"""
    validator = validator_class(model=model, strict=strict, generate_hints=False)
    
    valid_payload = VALID_FLAT_PAYLOADS[payload_key]
    result = await validator.validate(valid_payload)
    assert result.is_valid is True
    assert result.typed_result is not None

    if validator_class == MarkdownStructureValidator:
        assert result.typed_result.name == "John"
        assert result.typed_result.contact == "Contact"
        assert result.typed_result.bio == "Biography" 
    else:
        assert result.typed_result.name == "John"
        assert result.typed_result.age == 25
        assert result.typed_result.field1 == 1
        assert result.typed_result.field2 == "test"

@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("validator_class, payload_key, model", FLAT_VALIDATOR_CONFIGS)
@pytest.mark.asyncio
async def test_flat_structure_order_validation_all_formats_invalids(strict, validator_class, payload_key, model):
    """Test that all file format validators properly validate field order during extraction for flat structures"""
    validator = validator_class(model=model, strict=strict, generate_hints=False)
     
    invalid_payload = INVALID_FLAT_PAYLOADS[payload_key]
    result = await validator.validate(invalid_payload)
    assert result.is_valid is False 


# Special HTML payload for nested structure test
NESTED_HTML_PAYLOAD = """
<html>

    <article class="card">
        <div class="card-header">
            <div class="author">
                <img src="/avatar.jpg" alt="Author">
                <div class="name">John Doe</div>
            </div>
        </div>
        <div class="card-content">
            <h2>Title</h2>
            <p>Content with <span class="highlight">nested</span> elements</p>
        </div>
        <div class="comments">
            <div class="comment">
                <div class="author">User 1</div>
                <p>Comment content</p>
                <div class="replies">
                    <div class="reply">
                        <span class="author">User 2</span>
                        <p>Reply content</p>
                    </div>
                </div>
            </div>
        </div>
    </article>
    </body>
</html>
    """

# Special XML payload for nested structure test  
NESTED_XML_PAYLOAD = """
<root>
    <article class="card">
        <div class="card-header">
            <div class="author">
                <img src="/avatar.jpg" alt="Author"/>
                <div class="name">John Doe</div>
            </div>
        </div>
        <div class="card-content">
            <h2>Title</h2>
            <p>Content with <span class="highlight">nested</span> elements</p>
        </div>
        <div class="comments">
            <div class="comment">
                <div class="author">User 1</div>
                <p>Comment content</p>
                <div class="replies">
                    <div class="reply">
                        <span class="author">User 2</span>
                        <p>Reply content</p>
                    </div>
                </div>
            </div>
        </div>
    </article>
</root>
    """

# Special YAML payload for nested structure test
NESTED_YAML_PAYLOAD = """
article:
  class: "card"
  div:
    - div:
        img:
          src: "/avatar.jpg"
          alt: "Author"
        div:
          content: "John Doe"
    - h2: "Title"
      p:
        - "Content with "
        - span: "nested"
        - " elements"
    - div:
        p: "Comment content"
        div:
          div:
            span: "User 2"
"""

# Special JSON payload for nested structure test
NESTED_JSON_PAYLOAD = """{
  "article": {
    "div": [
      {
        "div": {
          "img": {
            "src": "/avatar.jpg",
            "alt": "Author"
          },
          "div": {
            "content": "John Doe"
          }
        }
      },
      {
        "h2": "Title",
        "p": [
          "Content with ",
          {"span": "nested"},
          " elements"
        ]
      },
      {
        "div": {
          "p": "Comment content",
          "div": {
            "div": {
              "span": "User 2",
              "p": "Reply content"
            }
          }
        }
      }
    ]
  }
}"""

payload_map = {
    "html": NESTED_HTML_PAYLOAD,
    "xml": NESTED_XML_PAYLOAD,
    "yaml": NESTED_YAML_PAYLOAD,
    "json": NESTED_JSON_PAYLOAD,
}

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "validator_class, payload_key",
    [
        (HTMLStructureValidator, "html"),
        (XMLStructureValidator, "xml"),
        (YAMLStructureValidator, "yaml"),
        (JSONStructureValidator, "json"),
    ],
)
async def test_complex_structure_order_validation_p_before_span(validator_class, payload_key):
    payload = payload_map[payload_key]

    class ParagraphBeforeSpanRequest(BaseModel):
        __ordered_fields__ = OrderedDict([
            ("p", str),
            ("span", str),
        ])

    validator = validator_class(model=ParagraphBeforeSpanRequest, strict=False, generate_hints=True)
    result = await validator.validate(payload)
    assert result.is_valid is True
    assert hasattr(result.typed_result, "p")
    assert hasattr(result.typed_result, "span")
    # Allow slight formatting differences by checking substrings
    assert "Comment content" in str(result.typed_result.p)
    assert "User 2" in str(result.typed_result.span)

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "validator_class, payload_key",
    [
        (HTMLStructureValidator, "html"),
        (XMLStructureValidator, "xml"),
        (YAMLStructureValidator, "yaml"),
        (JSONStructureValidator, "json"),
    ],
)
async def test_complex_structure_order_validation_span_before_p(validator_class, payload_key):
    payload = payload_map[payload_key]

    class SpanBeforeParagraphRequest(BaseModel):
        __ordered_fields__ = OrderedDict([
            ("span", str),
            ("p", str),
        ])

    validator = validator_class(model=SpanBeforeParagraphRequest, strict=False, generate_hints=True)
    result = await validator.validate(payload)
    assert result.is_valid is True
    assert hasattr(result.typed_result, "p")
    assert hasattr(result.typed_result, "span")
    assert "nested" in str(result.typed_result.span)
    assert "Comment content" in str(result.typed_result.p)

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "validator_class, payload_key",
    [
        (HTMLStructureValidator, "html"),
        (XMLStructureValidator, "xml"),
        (YAMLStructureValidator, "yaml"),
        (JSONStructureValidator, "json"),
    ],
)
async def test_complex_structure_order_validation_nested_span_in_non_primitive_paragraph(validator_class, payload_key):
    payload = payload_map[payload_key]

    class NestedSpanInComplexParagraphShouldNotBeIncluded(BaseModel):
        __ordered_fields__ = OrderedDict([
            ("p", Any),
            ("span", str),
        ])

    validator = validator_class(model=NestedSpanInComplexParagraphShouldNotBeIncluded, strict=False, generate_hints=True)
    result = await validator.validate(payload)
    assert result.is_valid is True
    assert hasattr(result.typed_result, "p")
    assert hasattr(result.typed_result, "span")

    assert "Content with" in str(result.typed_result.p)
    assert "User 2" in str(result.typed_result.span)

