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

@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("validator_class, has_model", [
    (HTMLValidator, False),
    (HTMLStructureValidator, True),
    (JSONValidator, False),
    (JSONStructureValidator, True),
    (XMLValidator, False),
    (XMLStructureValidator, True),
    (YAMLValidator, False),
    (YAMLStructureValidator, True),
    (CSVValidator, False),
    (CSVStructureValidator, True),
    (MarkdownValidator, False),
    (MarkdownStructureValidator, True),
])
async def test_initial_hint_generation(strict, validator_class, has_model):

    class SubModel(BaseModel):
        myint: int

    class CompoundModel(BaseModel):
        mystr: str
        mysubmodel: SubModel
    
    if has_model:
        validator = validator_class(strict=strict, generate_hints=True, model=CompoundModel)
    else:
        validator = validator_class(strict=strict, generate_hints=True)
    
    print(validator.initial_hint)
    assert "with no explanation or extra text" in validator.initial_hint
    assert "<html>" in validator.initial_hint
    assert "</html>" in validator.initial_hint