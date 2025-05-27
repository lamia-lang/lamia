from .html_validator import HTMLValidator
from .json_validator import JSONValidator
from .regex_validator import RegexValidator
from .length_validator import LengthValidator
from .atomic_type_validator import AtomicTypeValidator
from .object_validator import ObjectValidator
from .file_structure_validators import (
    DocumentStructureValidator,
    HTMLStructureValidator,
    JSONStructureValidator,
    YAMLStructureValidator,
    XMLStructureValidator,
    MarkdownStructureValidator,
    CSVStructureValidator,
)

__all__ = [
    "HTMLValidator",
    "JSONValidator",
    "RegexValidator",
    "LengthValidator",
    "AtomicTypeValidator",
    "ObjectValidator",
    "DocumentStructureValidator",
    "HTMLStructureValidator",
    "JSONStructureValidator",
    "YAMLStructureValidator",
    "XMLStructureValidator",
    "MarkdownStructureValidator",
    "CSVStructureValidator",
] 

# Group all validators by file type for conflict detection
HTML_VALIDATORS = {HTMLValidator, HTMLStructureValidator}
JSON_VALIDATORS = {JSONValidator, JSONStructureValidator}
YAML_VALIDATORS = {YAMLStructureValidator}
XML_VALIDATORS = {XMLStructureValidator}
MARKDOWN_VALIDATORS = {MarkdownStructureValidator}
CSV_VALIDATORS = {CSVStructureValidator}

# Each set represents a file type; only one file type group can be present in a config
CONFLICTING_VALIDATOR_GROUPS = [
    HTML_VALIDATORS,
    JSON_VALIDATORS,
    YAML_VALIDATORS,
    XML_VALIDATORS,
    MARKDOWN_VALIDATORS,
    CSV_VALIDATORS,
] 