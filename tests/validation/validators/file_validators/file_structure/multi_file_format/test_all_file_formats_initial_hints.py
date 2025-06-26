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
    "markdown_structure": CompoundModel,
}

# --- Test Payloads ---
ERROR_MESSAGES = {
    "html": "Please return only the HTML code, starting with <html> and ending with </html>, with no explanation or extra text.",
    "json": "Please return only valid JSON, with no explanation or extra text. The response must be a single JSON object or array.",
    "xml": "Please return only valid XML, with no explanation or extra text.",
    "yaml": "Please return only valid YAML, with no explanation or extra text.",
    "csv": "Please return only the CSV table, starting with the header row and ending with the last row, with no explanation or extra text and without extra whitespaces in the header and content rows. Please use commas as separators. If any of the cells of a string type contains a comma, please surround the cell with double quotes.",
    "markdown": "Please provide your Markdown content wrapped in triple backticks (```markdown ... ```) and ensure it is well-formed.",
    "html_structure": '''
Please ensure the HTML matches the required structure.
Expected structure:
<mystr>...text...</mystr>
<mysubmodel>
  <myint>...text...</myint>
</mysubmodel>
''',
    "json_structure": '''
Please ensure the JSON matches the required structure.
Expected structure:
"mystr": ...
"mysubmodel": {
  "myint": ...
}
''',
    "xml_structure": '''
Please ensure the XML matches the required structure.
Expected structure:
<mystr>...text...</mystr>
<mysubmodel>
  <myint>...text...</myint>
</mysubmodel>
''',
    "yaml_structure": '''
Please ensure the YAML matches the required structure.
Expected structure:
mystr: ...
mysubmodel:
  myint: ...
''',
    "csv_structure": '''
Please ensure the CSV matches the required structure.
Expected header row: mystr, myint, myfloat, mybool
Expected columns and types:
mystr: str
myint: int
myfloat: float
mybool: bool

Please return only the CSV table, starting with the header row and ending with the last row, with no explanation or extra text and without extra whitespaces in the header and content rows. Please use commas as separators. If any of the cells of a string type contains a comma, please surround the cell with double quotes.
''', 
    "markdown_structure": '''
Please provide your Markdown content wrapped in triple backticks (```markdown ... ```).
Ensure the Markdown matches the required structure.
Expected structure:
mystr: ...
mysubmodel:
  myint: ...
'''
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

    assert validator.initial_hint.strip() == ERROR_MESSAGES[validator_type].strip()
