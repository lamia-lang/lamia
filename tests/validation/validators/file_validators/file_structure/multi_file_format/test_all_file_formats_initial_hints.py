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
from lamia.validation.validators.file_validators.file_structure.markdown_structure_validator import Heading1, Paragraph

# Define models once for all tests
class SubModel(BaseModel):
    myint: int

class CompoundModel(BaseModel):
    mystr: str
    mysubmodel: SubModel

# CSV-specific model with only primitive types
class CSVModel(BaseModel):
    mystr: str
    myint: int
    myfloat: float
    mybool: bool

# Markdown-specific model using proper markdown classes
class MarkdownModel(BaseModel):
    title: Heading1
    content: Paragraph

VALIDATOR_CLASSES = {
    "html": HTMLValidator,
    "json": JSONValidator,
    "xml": XMLValidator,
    "yaml": YAMLValidator,
    "csv": CSVValidator,
    "markdown": MarkdownValidator,
    "html_structure": HTMLStructureValidator,
    "json_structure": JSONStructureValidator,
    "xml_structure": XMLStructureValidator,
    "yaml_structure": YAMLStructureValidator,
    "csv_structure": CSVStructureValidator,
    "markdown_structure": MarkdownStructureValidator,
}

MODEL_CLASSES = {
    "html": None,
    "json": None,
    "xml": None,
    "yaml": None,
    "csv": None,
    "markdown": None,
    "html_structure": CompoundModel,
    "json_structure": CompoundModel,
    "xml_structure": CompoundModel,
    "yaml_structure": CompoundModel,
    "csv_structure": CSVModel,
    "markdown_structure": MarkdownModel,
}

# --- Test Payloads ---
ERROR_MESSAGES = {
    "html": "Please return only the HTML code, starting with <html> and ending with </html>, with no explanation or extra text.",
    "json": "Please return only valid JSON, with no explanation or extra text. The response must be a single JSON object or array.",
    "xml": "Please return only valid XML, with no explanation or extra text.",
    "yaml": "Please return only valid YAML, with no explanation or extra text.",
    "csv": "Please return only the CSV table, starting with the header row and ending with the last row, with no explanation or extra text and without extra whitespaces in the header and content rows. Please use commas as separators. If any of the cells of a string type contains a comma, please surround the cell with double quotes.",
    "markdown": "Please provide your Markdown content wrapped in triple backticks (```markdown ... ```) and ensure it is well-formed.",
    "html_structure": { 
        'strict': '''
Please ensure the HTML matches the required structure exactly.
Expected structure (as direct children under <html>):
<mystr>string value</mystr>
<mysubmodel>
  <myint>integer value</myint>
</mysubmodel>
Expected target pydantic type in JSON format to be extracted from the HTML:
{"$defs":{"SubModel":{"properties":{"myint":{"title":"Myint","type":"integer"}},"required":["myint"],"title":"SubModel","type":"object"}},"properties":{"mystr":{"title":"Mystr","type":"string"},"mysubmodel":{"$ref":"#/$defs/SubModel"}},"required":["mystr","mysubmodel"],"title":"CompoundModel","type":"object"}
''',
        "permissive": '''
Please ensure the HTML contains the required fields somewhere in the structure.
The fields can be nested within other HTML elements like <body>, <div>, etc.
Required fields that must be present somewhere under <html> root tags:
<mystr>string value</mystr>
<mysubmodel>
  <myint>integer value</myint>
</mysubmodel>
Expected target pydantic type in JSON format to be extracted from the HTML:
{"$defs":{"SubModel":{"properties":{"myint":{"title":"Myint","type":"integer"}},"required":["myint"],"title":"SubModel","type":"object"}},"properties":{"mystr":{"title":"Mystr","type":"string"},"mysubmodel":{"$ref":"#/$defs/SubModel"}},"required":["mystr","mysubmodel"],"title":"CompoundModel","type":"object"}
''' 
    },
    "json_structure": {
        'strict': '''
Please ensure the JSON matches the required structure exactly.
Expected structure:
{
  "mystr": ...,
  "mysubmodel": {
    "myint": ...
  }
}
Expected target pydantic type in JSON format to be extracted from the JSON:
{"$defs":{"SubModel":{"properties":{"myint":{"title":"Myint","type":"integer"}},"required":["myint"],"title":"SubModel","type":"object"}},"properties":{"mystr":{"title":"Mystr","type":"string"},"mysubmodel":{"$ref":"#/$defs/SubModel"}},"required":["mystr","mysubmodel"],"title":"CompoundModel","type":"object"}
''',
        "permissive": '''
Please ensure the JSON contains the required fields with the correct types.
The fields can be nested within other JSON objects.
Required fields that must be present:
{
  "mystr": ...,
  "mysubmodel": {
    "myint": ...
  }
}
Expected target pydantic type in JSON format to be extracted from the JSON:
{"$defs":{"SubModel":{"properties":{"myint":{"title":"Myint","type":"integer"}},"required":["myint"],"title":"SubModel","type":"object"}},"properties":{"mystr":{"title":"Mystr","type":"string"},"mysubmodel":{"$ref":"#/$defs/SubModel"}},"required":["mystr","mysubmodel"],"title":"CompoundModel","type":"object"}
'''
    },
    "xml_structure": {
        'strict': '''
Please ensure the XML matches the required structure exactly.
Expected structure (as direct children under root):
<mystr>string value</mystr>
<mysubmodel>
  <myint>integer value</myint>
</mysubmodel>
Expected target pydantic type in JSON format to be extracted from the XML:
{"$defs":{"SubModel":{"properties":{"myint":{"title":"Myint","type":"integer"}},"required":["myint"],"title":"SubModel","type":"object"}},"properties":{"mystr":{"title":"Mystr","type":"string"},"mysubmodel":{"$ref":"#/$defs/SubModel"}},"required":["mystr","mysubmodel"],"title":"CompoundModel","type":"object"}
''',
        "permissive": '''
Please ensure the XML contains the required elements somewhere in the structure.
The elements can be nested within other XML elements.
Required elements that must be present somewhere:
<mystr>string value</mystr>
<mysubmodel>
  <myint>integer value</myint>
</mysubmodel>
Expected target pydantic type in JSON format to be extracted from the XML:
{"$defs":{"SubModel":{"properties":{"myint":{"title":"Myint","type":"integer"}},"required":["myint"],"title":"SubModel","type":"object"}},"properties":{"mystr":{"title":"Mystr","type":"string"},"mysubmodel":{"$ref":"#/$defs/SubModel"}},"required":["mystr","mysubmodel"],"title":"CompoundModel","type":"object"}
'''
    },
    "yaml_structure": {
        'strict': '''
Please ensure the YAML matches the required structure exactly.
Expected structure:
mystr: "..."
mysubmodel:
  myint: ...
''',
        "permissive": '''
Please ensure the YAML contains the required fields with the correct types.
The fields can be nested within other YAML objects.
Required fields that must be present:
mystr: "..." (string)
mysubmodel:
  myint: ... (integer)
'''
    },
    "csv_structure": {
        'strict': '''
Please ensure the CSV matches the required structure exactly.
Expected header row: mystr,myint,myfloat,mybool
Expected columns and types:
mystr: str
myint: int
myfloat: float
mybool: bool

Please return only the CSV table, starting with the header row and ending with the last row, with no explanation or extra text and without extra whitespaces in the header and content rows. Please use commas as separators. If any of the cells of a string type contains a comma, please surround the cell with double quotes.
''',
        "permissive": '''
Please ensure the CSV matches the required structure exactly.
Expected header row: mystr,myint,myfloat,mybool
Expected columns and types:
mystr: str
myint: int
myfloat: float
mybool: bool

Please return only the CSV table, starting with the header row and ending with the last row, with no explanation or extra text and without extra whitespaces in the header and content rows. Please use commas as separators. If any of the cells of a string type contains a comma, please surround the cell with double quotes.
'''
    }, 
    "markdown_structure": {
        'strict': '''
Please provide your Markdown content wrapped in triple backticks (```markdown ... ```).
Ensure the Markdown matches the required structure exactly.
Expected structure:
title: "..."
content: "..."
''',
        "permissive": '''
Please provide your Markdown content wrapped in triple backticks (```markdown ... ```).
Ensure the Markdown contains the required fields with the correct types.
The fields can be nested within other Markdown structures.
Required fields that must be present:
title: "..." (Heading1)
content: "..." (Paragraph)
'''
    }
}


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("validator_type", [
    "html",
    "json",
    "xml",
    "yaml",
    "csv",
    "markdown",
    "html_structure",
    "json_structure",
    "xml_structure",
    "yaml_structure",
    "csv_structure",
    "markdown_structure"
])
def test_structure_validator_initial_hint_exact(strict, validator_type):
    validator_class = VALIDATOR_CLASSES[validator_type]

    model = MODEL_CLASSES[validator_type]
    if model is not None:
        validator = validator_class(model=model, strict=strict, generate_hints=True)
    else:
        validator = validator_class(strict=strict, generate_hints=True)

    # Get the appropriate message based on strict/permissive mode
    if validator_type.endswith('_structure'):
        message_key = "strict" if strict else "permissive"
        expected_message = ERROR_MESSAGES[validator_type][message_key]
    else:
        expected_message = ERROR_MESSAGES[validator_type]

    assert validator.initial_hint.strip() == expected_message.strip()
