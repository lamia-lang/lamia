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
    name: Heading1
    
    # These fields must maintain order
    __ordered_fields__ = OrderedDict([
        ("bio", Heading2),
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
    "csv": "field1,field2\n1,test",
    "json": '{"name": "John", "field1": 1, "age": 25, "field2": "test"}',
    "yaml": "name: John\nfield1: 1\nage: 25\nfield2: test",
    "xml": "<root><name>John</name><field1>1</field1><age>25</age><field2>test</field2></root>",
    "html": "<html><name>John</name><field1>1</field1><age>25</age><field2>test</field2></html>",
    "markdown": "## Contact \n\n# John Smith\n\n John is a great person\n\n## Biography\n\n",
}

INVALID_FLAT_PAYLOADS = {
    "csv": "field2,field1\ntest,1",
    "json": '{"name": "John", "field2": "test", "age": 25, "field1": 1}',
    "yaml": "name: John\nfield2: test\nage: 25\nfield1: 1",
    "xml": "<root><name>John</name><field2>test</field2><age>25</age><field1>1</field1></root>",
    "html": "<html><name>John</name><field2>test</field2><age>25</age><field1>1</field1></html>",
    "markdown": "# John Smith\n\n John is a great person ## Biography\n\n ## Contact",
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
      div:
        img:
          src: "/avatar.jpg"
          alt: "Author"
        div:
          content: "John Doe"
      h2: "Title"
      p:
        - "Content with "
        - span:
            class: "highlight"
            content: "nested"
        - " elements"
      div:
        div:
          content: "User 1"
        p: "Comment content"
        div:
          div:
            span:
              content: "User 2"
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
async def test_flat_structure_order_validation_all_formats(strict, validator_class, payload_key, model):
    """Test that all file format validators properly validate field order during extraction for flat structures"""
    validator = validator_class(model=model, strict=strict, generate_hints=False)
    
    # Test valid case - ordered fields maintain relative order
    valid_payload = VALID_FLAT_PAYLOADS[payload_key]
    result = await validator.validate(valid_payload)
    assert result.is_valid is True, f"Valid case failed for {validator_class.__name__} in {'strict' if strict else 'non-strict'} mode: {valid_payload}"
    
    # Test invalid case - ordered fields in wrong relative order  
    invalid_payload = INVALID_FLAT_PAYLOADS[payload_key]
    result = await validator.validate(invalid_payload)
    assert result.is_valid is False, f"Invalid case passed for {validator_class.__name__} in {'strict' if strict else 'non-strict'} mode: {invalid_payload}"

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
async def test_complex_structure_order_validation(validator_class, payload_key):
    """Parametrised version of the complex nested-structure ordering test for multiple file formats."""
    payload_map = {
        "html": NESTED_HTML_PAYLOAD,
        "xml": NESTED_XML_PAYLOAD,
        "yaml": NESTED_YAML_PAYLOAD,
        "json": NESTED_JSON_PAYLOAD,
    }
    payload = payload_map[payload_key]

    # --- First scenario: p comes before span ---
    class ParagraphBeforeSpanRequest(BaseModel):
        __ordered_fields__ = OrderedDict([
            ("p", str),
            ("span", str),
        ])

    validator = validator_class(model=ParagraphBeforeSpanRequest, strict=False, generate_hints=True)
    result = await validator.validate(payload)
    assert result.is_valid is True
    assert hasattr(result.result_type, "p")
    assert hasattr(result.result_type, "span")
    # Allow slight formatting differences by checking substrings
    assert "Comment content" in str(result.result_type.p)
    assert "User 2" in str(result.result_type.span)

    # --- Second scenario: span comes before p ---
    class SpanBeforeParagraphRequest(BaseModel):
        __ordered_fields__ = OrderedDict([
            ("span", str),
            ("p", str),
        ])

    validator = validator_class(model=SpanBeforeParagraphRequest, strict=False, generate_hints=True)
    result = await validator.validate(payload)
    assert result.is_valid is True
    assert hasattr(result.result_type, "p")
    assert hasattr(result.result_type, "span")
    assert "nested" in str(result.result_type.span)
    assert "Comment content" in str(result.result_type.p)

    # --- Third scenario: p is Any (capture subtree) then span str ---
    class NestedSpanInComplexParagraphShouldNotBeIncluded(BaseModel):
        __ordered_fields__ = OrderedDict([
            ("p", Any),
            ("span", str),
        ])

    validator = validator_class(model=NestedSpanInComplexParagraphShouldNotBeIncluded, strict=False, generate_hints=True)
    result = await validator.validate(payload)
    assert result.is_valid is True
    assert hasattr(result.result_type, "p")
    assert hasattr(result.result_type, "span")
    # .p should contain the complex paragraph with the nested span/highlight
    assert "Content with" in str(result.result_type.p)
    assert "User 2" in str(result.result_type.span)

