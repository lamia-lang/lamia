from .regex_validator import RegexValidator
from .length_validator import LengthValidator
from .atomic_type_validator import AtomicTypeValidator
from .object_validator import ObjectValidator
from .file_validators import (
    HTMLValidator,
    JSONValidator,
    YAMLValidator,
    XMLValidator,
    MarkdownValidator,
    CSVValidator,
)

from .file_validators import (
    HTMLStructureValidator,
    JSONStructureValidator,
    YAMLStructureValidator,
    XMLStructureValidator,
    MarkdownStructureValidator,
    CSVStructureValidator,
)

__all__ = [
    "RegexValidator",
    "LengthValidator",
    "AtomicTypeValidator",
    "ObjectValidator",
    "HTMLStructureValidator",
    "JSONStructureValidator",
    "YAMLStructureValidator",
    "XMLStructureValidator",
    "MarkdownStructureValidator",
    "CSVStructureValidator",
    "HTMLValidator",
    "JSONValidator",
    "YAMLValidator",
    "XMLValidator",
    "MarkdownValidator",
    "CSVValidator",
] 

# Group all validators by file type for conflict detection
HTML_VALIDATORS = {HTMLValidator, HTMLStructureValidator}
JSON_VALIDATORS = {JSONValidator, JSONStructureValidator}
YAML_VALIDATORS = {YAMLValidator, YAMLStructureValidator}
XML_VALIDATORS = {XMLValidator, XMLStructureValidator}
MARKDOWN_VALIDATORS = {MarkdownValidator, MarkdownStructureValidator}
CSV_VALIDATORS = {CSVValidator, CSVStructureValidator}

# Each set represents a file type; only one file type group can be present in a config
CONFLICTING_VALIDATOR_GROUPS = [
    HTML_VALIDATORS,
    JSON_VALIDATORS,
    YAML_VALIDATORS,
    XML_VALIDATORS,
    MARKDOWN_VALIDATORS,
    CSV_VALIDATORS,
] 