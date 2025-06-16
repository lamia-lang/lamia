# NOTE: Type checking logic is now tested in unit tests for TypeMatcher. These tests remain as integration tests for file structure validators.
import pytest
from pydantic import BaseModel
from lamia.adapters.llm.validation.validators.file_validators import *

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("file_content, validator_class", [
    ("<html><body><p>paragraph1</p><p>paragraph2</p><body></html>", HTMLStructureValidator),
    ("<root><p>paragraph1</p><p>paragraph2</p></root>", XMLStructureValidator),
    ('{"div1":{"p": "paragraph1"}, "div2":{"p": "paragraph2"}}', JSONStructureValidator), # JSON does not allow repetion of of the same key on the same level
    ("div1:\n  p: paragraph1\ndiv2:\n  p: paragraph2\n", YAMLStructureValidator), # YAML does not allow repetion of of the same key on the same level
    ("p;p;\nparagraph1;paragraph2;", CSVStructureValidator),
    ("# Heading 1\n## Heading 2\nParagraph 1\nParagraph 2", MarkdownStructureValidator),
])
async def test_file_structure_validator_should_select_first_when_many_fields_with_same_name(strict, file_content, validator_class):
    class P1(BaseModel):
      p: str

    validator = validator_class(model=P1, strict=False)
    result = await validator.validate(file_content)
    print(result)
    assert result.is_valid is True
    assert result.result_type.p == "paragraph1"