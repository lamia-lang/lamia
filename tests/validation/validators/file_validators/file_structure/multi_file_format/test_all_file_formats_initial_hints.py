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

@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("validator,expected_structure", [
    (
        HTMLValidator(strict=True, generate_hints=True),
        '''
Please return only the HTML code, starting with <html> and ending with </html>, with no explanation or extra text.
'''
    ),
    (
        JSONValidator(strict=True, generate_hints=True),
        '''
Please return only valid JSON, with no explanation or extra text. The response must be a single JSON object or array.
'''
    ),
    (
        XMLValidator(strict=True, generate_hints=True),
        '''
Please return only valid XML, with no explanation or extra text. The response must be a single XML document with a single root element.
'''
    ),
    (
        YAMLValidator(strict=True, generate_hints=True),
        '''
Please return only valid YAML, with no explanation or extra text.
'''
    ),
    (
        CSVValidator(strict=True, generate_hints=True),
        '''
Please return only the CSV code, starting with the header row and ending with the last row, with no explanation or extra text.
'''
    ),
    (
        MarkdownValidator(strict=True, generate_hints=True),
        '''
Please ensure the Markdown is well-formed.
'''
    ),
    (
        HTMLStructureValidator(model=CompoundModel, generate_hints=True),
        '''
Please ensure the HTML matches the required structure.
Expected structure:
<mystr>...text...</mystr>
<mysubmodel>
  <myint>...text...</myint>
</mysubmodel>
'''
    ),
    (
        JSONStructureValidator(model=CompoundModel, generate_hints=True),
        '''
Please ensure the JSON matches the required structure.
Expected structure:
"mystr": ...
"mysubmodel": {
  "myint": ...
}
'''
    ),
    (
        XMLStructureValidator(model=CompoundModel, generate_hints=True),
        '''
Please ensure the XML matches the required structure.
Expected structure:
<mystr>...text...</mystr>
<mysubmodel>
  <myint>...text...</myint>
</mysubmodel>
'''
    ),
    (
        YAMLStructureValidator(model=CompoundModel, generate_hints=True),
        '''
Please ensure the YAML matches the required structure.
Expected structure:
mystr: ...
mysubmodel:
  myint: ...
'''
    ),
    (
        CSVStructureValidator(model=CompoundModel, generate_hints=True),
        '''
Please ensure the CSV matches the required structure.
Expected columns and types:
mystr: str
mysubmodel: SubModel
'''
    ),
    (
        MarkdownStructureValidator(model=CompoundModel, generate_hints=True),
        '''
Please ensure the Markdown matches the required structure.
Expected structure:
mystr: ...
mysubmodel:
  myint: ...
'''
    ),
])
def test_structure_validator_initial_hint_exact(strict, validator, expected_structure):
    assert validator.initial_hint.strip() == expected_structure.strip()
