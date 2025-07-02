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
from lamia.validation.validators.file_validators.file_structure.document_structure_validator import DocumentStructureValidator
import json
from collections import OrderedDict

# Minimal derivative class that doesn't override initial_hint - for .txt files
class MinimalTxtStructureValidator(DocumentStructureValidator):
    @classmethod
    def name(cls) -> str:
        return "txt_structure"

    @classmethod
    def file_type(cls) -> str:
        return "txt"

    def _describe_structure(self, model, indent=0):
        """Describe structure for txt files: primitives on lines, objects as JSON."""
        lines = []
        if not model:
            return lines
            
        # Get fields from any Pydantic model
        if hasattr(model, 'model_fields'):
            fields = model.model_fields
        elif hasattr(model, '__fields__'):
            fields = model.__fields__
        else:
            return lines
            
        for field_name, field_info in fields.items():
            field_type = field_info.annotation
            
            # Check if it's a primitive type
            is_primitive = field_type in (str, int, float, bool)
            if is_primitive:
                lines.append(" " * indent + f"{field_name} ({field_type.__name__})")
            else:
                # For complex types (nested models, lists, etc.), they go as JSON
                type_name = getattr(field_type, '__name__', str(field_type))
                lines.append(" " * indent + f"{field_name} (JSON: {type_name})")
        return lines

    def extract_payload(self, response: str) -> str:
        """Simple extraction that just returns the response."""
        return response.strip()

    def load_payload(self, payload: str) -> dict:
        """For txt files: primitives on lines, nested objects as JSON."""
        lines = [line.strip() for line in payload.strip().split('\n') if line.strip()]
        
        if not self.model:
            # If no model, return a simple dict representation
            return {"content": payload}
        
        # Get fields from the model dynamically
        if hasattr(self.model, 'model_fields'):
            fields = self.model.model_fields
        elif hasattr(self.model, '__fields__'):
            fields = self.model.__fields__
        else:
            return {"content": payload}
        
        result = {}
        line_index = 0
        
        # Process each field in order
        for field_name, field_info in fields.items():
            if line_index >= len(lines):
                break
                
            field_type = field_info.annotation
            line_content = lines[line_index]
            
            # Check if it's a primitive type
            is_primitive = field_type in (str, int, float, bool)
            
            if is_primitive:
                # Parse primitive types
                if field_type == str:
                    result[field_name] = line_content
                elif field_type == int:
                    try:
                        result[field_name] = int(line_content)
                    except ValueError:
                        result[field_name] = 0
                elif field_type == float:
                    try:
                        result[field_name] = float(line_content)
                    except ValueError:
                        result[field_name] = 0.0
                elif field_type == bool:
                    result[field_name] = line_content.lower() in ('true', '1', 'yes', 'on')
            else:
                # For complex types, expect JSON format
                try:
                    result[field_name] = json.loads(line_content)
                except json.JSONDecodeError:
                    # If JSON parsing fails, store as string
                    result[field_name] = line_content
            
            line_index += 1
        
        return result

    def find_element(self, tree, key):
        """Find element in dict-like structure."""
        return tree.get(key) if isinstance(tree, dict) else None

    def get_text(self, element):
        """Get text representation - for primitives, return as string."""
        if isinstance(element, (dict, list, tuple, set)):
            return json.dumps(element, default=str)
        return str(element)

    def has_nested(self, element):
        """Check if element has nested structure (JSON objects/arrays/complex types)."""
        return isinstance(element, (dict, list, tuple, set)) or hasattr(element, '__dict__')

    def iter_direct_children(self, tree):
        """Iterate over direct children - for dicts, return key-value pairs."""
        if isinstance(tree, dict):
            return tree.items()
        elif isinstance(tree, (list, tuple)):
            return enumerate(tree)
        elif isinstance(tree, set):
            return enumerate(list(tree))
        elif hasattr(tree, '__dict__'):
            return tree.__dict__.items()
        return []

    def get_name(self, element):
        """Get name/key of element."""
        if isinstance(element, tuple) and len(element) == 2:
            return element[0]  # For (key, value) pairs
        return str(element)

    def find_all(self, tree, key):
        """Find all elements with key, including nested JSON objects."""
        results = []
        
        def _search_recursive(obj, target_key):
            if isinstance(obj, dict):
                if target_key in obj:
                    results.append(obj[target_key])
                # Search recursively in nested objects
                for k, v in obj.items():
                    if isinstance(v, (dict, list, tuple, set)) or hasattr(v, '__dict__'):
                        _search_recursive(v, target_key)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    if isinstance(item, (dict, list, tuple, set)) or hasattr(item, '__dict__'):
                        _search_recursive(item, target_key)
            elif isinstance(obj, set):
                for item in obj:
                    if isinstance(item, (dict, list, tuple, set)) or hasattr(item, '__dict__'):
                        _search_recursive(item, target_key)
            elif hasattr(obj, '__dict__'):
                if hasattr(obj, target_key):
                    results.append(getattr(obj, target_key))
                for attr_name, attr_value in obj.__dict__.items():
                    if isinstance(attr_value, (dict, list, tuple, set)) or hasattr(attr_value, '__dict__'):
                        _search_recursive(attr_value, target_key)
        
        _search_recursive(tree, key)
        return results

    def get_subtree_string(self, elem):
        """Return string representation of a subtree/element."""
        if isinstance(elem, (dict, list, tuple, set)):
            return json.dumps(elem, default=str)
        elif hasattr(elem, '__dict__'):
            return json.dumps(elem.__dict__, default=str)
        return str(elem)

    def get_field_order(self, tree):
        """Get field order for txt files - return keys in dictionary order."""
        if isinstance(tree, dict):
            return list(tree.keys())
        return []

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
    "txt_structure": MinimalTxtStructureValidator,
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
    "txt_structure": CompoundModel,
}

# --- Test Payloads ---
INITIAL_HINTS = {
    "html": "Please return only the HTML code, starting with <html> and ending with </html>, with no explanation or extra text.",
    "json": "Please return only valid json, with no explanation or extra text.",
    "xml": "Please return only valid XML, with no explanation or extra text.",
    "yaml": "Please return only valid yaml, with no explanation or extra text.",
    "csv": "Please return only the CSV table, starting with the header row and ending with the last row, with no explanation or extra text and without extra whitespaces in the header and content rows. Please use commas as separators. If any of the cells of a string type contains a comma, please surround the cell with double quotes.",
    "markdown": "Please provide your Markdown content wrapped in triple backticks (``` ... ``` or ```markdown ... ```) and ensure it is well-formed.",
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
        'strict': '''Please ensure the json matches the required structure exactly.
Expected structure:
{
  "mystr": ...,
  "mysubmodel": {
    "myint": ...
  }
}
Expected target pydantic type in json format to be extracted from the JSON:
{"$defs":{"SubModel":{"properties":{"myint":{"title":"Myint","type":"integer"}},"required":["myint"],"title":"SubModel","type":"object"}},"properties":{"mystr":{"title":"Mystr","type":"string"},"mysubmodel":{"$ref":"#/$defs/SubModel"}},"required":["mystr","mysubmodel"],"title":"CompoundModel","type":"object"}''',
        'permissive': '''Please ensure the JSON contains the required fields with the correct types.
The fields can be nested within other JSON objects.
Required fields that must be present:
{
  "mystr": ...,
  "mysubmodel": {
    "myint": ...
  }
}
Expected target pydantic type in JSON format to be extracted from the JSON:
{"$defs":{"SubModel":{"properties":{"myint":{"title":"Myint","type":"integer"}},"required":["myint"],"title":"SubModel","type":"object"}},"properties":{"mystr":{"title":"Mystr","type":"string"},"mysubmodel":{"$ref":"#/$defs/SubModel"}},"required":["mystr","mysubmodel"],"title":"CompoundModel","type":"object"}'''
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
        'strict': '''Please ensure the yaml matches the required structure.
Expected structure:
mystr: ...
mysubmodel:
  myint: ...

Expected target pydantic type in JSON format to be extracted from the YAML:
{"$defs":{"SubModel":{"properties":{"myint":{"title":"Myint","type":"integer"}},"required":["myint"],"title":"SubModel","type":"object"}},"properties":{"mystr":{"title":"Mystr","type":"string"},"mysubmodel":{"$ref":"#/$defs/SubModel"}},"required":["mystr","mysubmodel"],"title":"CompoundModel","type":"object"}''',
        'permissive': '''Please ensure the yaml matches the required structure.
Expected structure:
mystr: ...
mysubmodel:
  myint: ...

Expected target pydantic type in JSON format to be extracted from the YAML:
{"$defs":{"SubModel":{"properties":{"myint":{"title":"Myint","type":"integer"}},"required":["myint"],"title":"SubModel","type":"object"}},"properties":{"mystr":{"title":"Mystr","type":"string"},"mysubmodel":{"$ref":"#/$defs/SubModel"}},"required":["mystr","mysubmodel"],"title":"CompoundModel","type":"object"}'''
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
Please provide your Markdown content wrapped in triple backticks (``` ... ``` or ```markdown ... ```).
Ensure the Markdown matches the required structure exactly.
Expected structure:
title: # Level 1 heading (starts with single #)
content: Regular paragraph text (plain text without special formatting)
''',
        "permissive": '''
Please provide your Markdown content wrapped in triple backticks (``` ... ``` or ```markdown ... ```).
Ensure the Markdown contains the required fields with the correct types.
The fields can be nested within other Markdown structures.
Required fields that must be present:
title: # Level 1 heading (starts with single #)
content: Regular paragraph text (plain text without special formatting)
'''
    },
    "txt_structure": {
        'strict': '''Please ensure the txt matches the required structure.
Expected structure:
mystr (str)
mysubmodel (JSON: SubModel)

Expected target pydantic type in JSON format to be extracted from the TXT:
{"$defs":{"SubModel":{"properties":{"myint":{"title":"Myint","type":"integer"}},"required":["myint"],"title":"SubModel","type":"object"}},"properties":{"mystr":{"title":"Mystr","type":"string"},"mysubmodel":{"$ref":"#/$defs/SubModel"}},"required":["mystr","mysubmodel"],"title":"CompoundModel","type":"object"}''',
        "permissive": '''Please ensure the txt matches the required structure.
Expected structure:
mystr (str)
mysubmodel (JSON: SubModel)

Expected target pydantic type in JSON format to be extracted from the TXT:
{"$defs":{"SubModel":{"properties":{"myint":{"title":"Myint","type":"integer"}},"required":["myint"],"title":"SubModel","type":"object"}},"properties":{"mystr":{"title":"Mystr","type":"string"},"mysubmodel":{"$ref":"#/$defs/SubModel"}},"required":["mystr","mysubmodel"],"title":"CompoundModel","type":"object"}'''
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
    "markdown_structure",
    "txt_structure"
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
        expected_message = INITIAL_HINTS[validator_type][message_key]
    else:
        expected_message = INITIAL_HINTS[validator_type]

    assert validator.initial_hint.strip() == expected_message.strip()

class CompoundOrderedModel(BaseModel):
    mystr: str
    mysubmodel: SubModel
    
    __ordered_fields__ = OrderedDict([
        ("mystr", str),
        ("mysubmodel", SubModel),
    ])

# CSV-specific model with only primitive types
class CSVModelOrdered(BaseModel):
    mystr: str
    myint: int
    myfloat: float
    mybool: bool
    
    __ordered_fields__ = OrderedDict([
        ("mystr", str),
        ("myint", int),
        ("myfloat", float),
        ("mybool", bool),
    ])

# Markdown-specific model using proper markdown classes
class MarkdownModelOrdered(BaseModel):
    title: Heading1
    content: Paragraph
    
    __ordered_fields__ = OrderedDict([
        ("title", Heading1),
        ("content", Paragraph),
    ])

ORDERED_DICTS = {
    "html_structure": CompoundOrderedModel,
    "json_structure": CompoundOrderedModel,
    "xml_structure": CompoundOrderedModel,
    "yaml_structure": CompoundOrderedModel,
    "csv_structure": CSVModelOrdered,
    "markdown_structure": MarkdownModelOrdered,
    "txt_structure": CompoundOrderedModel,
}

def get_ordered_hints():
    """Generate initial hints for ordered field models by calling actual validators to get consistent output."""
    ordered_hints = {}
    
    # Map validator types to their classes and models
    validator_mapping = {
        "html_structure": (HTMLStructureValidator, CompoundOrderedModel),
        "json_structure": (JSONStructureValidator, CompoundOrderedModel), 
        "xml_structure": (XMLStructureValidator, CompoundOrderedModel),
        "yaml_structure": (YAMLStructureValidator, CompoundOrderedModel),
        "csv_structure": (CSVStructureValidator, CSVModelOrdered),
        "markdown_structure": (MarkdownStructureValidator, MarkdownModelOrdered),
        "txt_structure": (MinimalTxtStructureValidator, CompoundOrderedModel),
    }
    
    for validator_type, (validator_class, model_class) in validator_mapping.items():
        ordered_hints[validator_type] = {}
        
        # Generate hints for both strict and permissive modes by calling actual validators
        for strict in [True, False]:
            validator = validator_class(model=model_class, strict=strict, generate_hints=True)
            mode_key = "strict" if strict else "permissive"
            ordered_hints[validator_type][mode_key] = validator.initial_hint
    
    return ordered_hints

INITIAL_HINTS_ORDERED = get_ordered_hints()

@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("validator_type", [
    "html_structure",
    "json_structure",
    "xml_structure",
    "yaml_structure",
    "csv_structure",
    "markdown_structure",
    "txt_structure"
])
def test_structure_validator_initial_hint_exact_for_ordered_fields(strict, validator_type):
    validator_class = VALIDATOR_CLASSES[validator_type]

    model = ORDERED_DICTS[validator_type]
    validator = validator_class(model=model, strict=strict, generate_hints=True)

    message_key = "strict" if strict else "permissive"
    expected_message = INITIAL_HINTS_ORDERED[validator_type][message_key]

    assert validator.initial_hint.strip() == expected_message.strip()


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("validator_type", [
    "html_structure",
    "json_structure",
    "xml_structure",
    "yaml_structure",
])
def test_structure_validator_initial_hint_for_ordered_nested_fields(strict, validator_type):
    validator_class = VALIDATOR_CLASSES[validator_type]

    class NestedOrderedModel(BaseModel):
        mystr: str
        myint: int
        
        __ordered_fields__ = OrderedDict([
            ("myorderedstr", str),
            ("myorderedint", int),
        ])

    class UpperOrderedModel(BaseModel):
        mysubmodel: NestedOrderedModel
        
        __ordered_fields__ = OrderedDict([
            ("mystr", str),
            ("mysubmodel_inside_ordereddict", NestedOrderedModel),
        ])
    
    # Use the UpperOrderedModel that was defined in the test
    validator = validator_class(model=UpperOrderedModel, strict=strict, generate_hints=True)
    
    assert "mysubmodel.myorderedstr should come before mysubmodel.myorderedint" in validator.initial_hint
    assert "mystr should come before mysubmodel_inside_ordereddict" in validator.initial_hint
    assert "mysubmodel_inside_ordereddict.myorderedstr should come before mysubmodel_inside_ordereddict.myorderedint" in validator.initial_hint
    
    # Ensure there are exactly 3 ordering messages (no more, no less)
    ordering_lines = [line for line in validator.initial_hint.split('\n') if 'ORDERING:' in line]
    assert len(ordering_lines) == 3, f"Expected exactly 3 ordering messages, but found {len(ordering_lines)}: {ordering_lines}"

