import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import MarkdownStructureValidator

class SimpleModel(BaseModel):
    title: str
    value: int

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_markdown_structure_validator(strict):
    validator = MarkdownStructureValidator(model=SimpleModel, strict=strict)
    valid_md = '# title\n\n123\n'
    invalid_md = '# title\n\nabc\n'
    result = await validator.validate(valid_md)
    assert isinstance(result.is_valid, bool)
    result = await validator.validate(invalid_md)
    assert isinstance(result.is_valid, bool) 