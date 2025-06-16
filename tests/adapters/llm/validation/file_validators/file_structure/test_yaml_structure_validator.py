import pytest
from pydantic import BaseModel, Field, RootModel
from lamia.adapters.llm.validation.validators.file_validators import YAMLStructureValidator
from typing import List, Dict, Optional, Any, Union, Tuple

# The tests that are common to all file structure validators should go to multi_file_format folder
# Tests exclusive to YAML format should go here

yaml = """
# YAML Example: Full Semantic Demonstration

# Scalars (strings, numbers, booleans, null)
string_scalar: Hello, YAML!
int_scalar: 42
float_scalar: 3.14
boolean_true: true
boolean_false: false
null_value: null

# Sequences (lists)
shopping_list:
  - Milk
  - Bread
  - Eggs

# Nested sequences
matrix:
  - [1, 2, 3]
  - [4, 5, 6]

# Mappings (dictionaries)
person:
  name: Alice
  age: 30
  married: false

# Nested mappings
address:
  street: 123 Maple St
  city: Springfield
  zip: 12345

# Mixed mappings and sequences
company:
  name: Acme Corp
  employees:
    - name: John Doe
      role: Developer
    - name: Jane Smith
      role: Designer

# Multiline strings
multiline_literal: |
  This is a multiline
  string using literal block.
  Line breaks are preserved.

multiline_folded: >
  This is a multiline
  string using folded block.
  Line breaks become spaces.

# Anchors and aliases (reuse)
defaults: &defaults
  retries: 3
  timeout: 30

production:
  <<: *defaults
  url: https://prod.example.com

development:
  <<: *defaults
  url: https://dev.example.com

# Tags (explicit typing)
number_as_string: !!str 1234
string_as_bool: !!bool \"yes\"
int_tagged: !!int \"42\"

# Comments
# This is a comment line

# Empty structure examples
empty_list: []
empty_dict: {}

# Ordered mapping (YAML 1.2)
ordered_map:
  - one: 1
  - two: 2
  - three: 3

    """

class PersonModel(BaseModel):
    name: str
    age: int
    married: bool

class AddressModel(BaseModel):
    street: str
    city: str
    zip: int

class EmployeeModel(BaseModel):
    name: str
    role: str

class CompanyModel(BaseModel):
    name: str
    employees: List[EmployeeModel]

class DefaultsModel(BaseModel):
    retries: int
    timeout: int

class ProductionModel(DefaultsModel):
    url: str

class DevelopmentModel(DefaultsModel):
    url: str

class OrderedMapItemModel(BaseModel):
    one: Optional[int] = None
    two: Optional[int] = None
    three: Optional[int] = None

class YamlModel(BaseModel):
    string_scalar: str
    int_scalar: int
    float_scalar: float
    boolean_true: bool
    boolean_false: bool
    null_value: Optional[Any]
    shopping_list: List[str]
    matrix: List[List[int]]
    person: PersonModel
    address: AddressModel
    company: CompanyModel
    multiline_literal: str
    multiline_folded: str
    defaults: DefaultsModel
    production: ProductionModel
    development: DevelopmentModel
    number_as_string: str
    string_as_bool: bool
    int_tagged: int
    empty_list: List[Any]
    empty_dict: Dict[Any, Any]
    ordered_map: List[OrderedMapItemModel]

@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_yaml_structure_validator_deep_nesting(strict):
    validator = YAMLStructureValidator(model=YamlModel, strict=strict)
    result = await validator.validate(yaml)
    assert result.is_valid is True