import yaml
from pydantic import BaseModel, create_model
import re
from .document_structure_validator import DocumentStructureValidator, TextAroundPayloadError
from .utils import import_model_from_path, describe_model_structure

class YAMLStructureValidator(DocumentStructureValidator):
    """Validates if the YAML matches a given Pydantic model structure."""
    def __init__(self, model: BaseModel = None, model_name: str = None, schema: dict = None, strict: bool = True, model_module: str = "models", generate_hints: bool = False):
        if model is not None:
            resolved_model = model
        elif model_name is not None:
            resolved_model = import_model_from_path(model_name, default_module=model_module)
        elif schema is not None:
            resolved_model = create_model("YAMLStructureModel", **schema)
        else:
            resolved_model = None
        super().__init__(model=resolved_model, strict=strict, generate_hints=generate_hints)

    @classmethod
    def name(cls) -> str:
        return "yaml_structure"

    @property
    def initial_hint(self) -> str:
        structure_lines = describe_model_structure(self.model, format_type="yaml")
        return (
            "Please ensure the YAML matches the required structure.\n"
            "Expected structure:\n"
            + '\n'.join(structure_lines)
        )

    def parse(self, response: str):
        stripped = response.strip()
        
        if not self.strict:
            # Strategy 1: Try markdown code blocks first
            markdown_match = re.search(r'```(?:yaml|yml)?\s*\n?(.*?)\n?```', stripped, re.DOTALL | re.IGNORECASE)
            if markdown_match:
                yaml_candidate = markdown_match.group(1).strip()
                try:
                    return yaml.safe_load(yaml_candidate)
                except yaml.YAMLError:
                    pass  # Continue to next strategy
            
            # Strategy 2: Look for YAML-like patterns (key: value lines)
            yaml_lines = []
            for line in stripped.split('\n'):
                line = line.strip()
                # Simple YAML pattern: word characters followed by colon and value
                if re.match(r'^[\w\s-]+:\s*.+$', line):
                    yaml_lines.append(line)
            
            if yaml_lines:
                yaml_candidate = '\n'.join(yaml_lines)
                try:
                    return yaml.safe_load(yaml_candidate)
                except yaml.YAMLError:
                    pass  # Continue to next strategy
            
            # Strategy 3: Try the whole thing (fallback)
            try:
                return yaml.safe_load(stripped)
            except yaml.YAMLError:
                pass
            
            # If nothing worked, raise error
            raise TextAroundPayloadError(
                validator_class_name="YAML",
                original_text=response,
                parsed_text=stripped
            )
        else:
            # Strict mode: parse as-is
            try:
                return yaml.safe_load(stripped)
            except yaml.YAMLError as e:
                raise TextAroundPayloadError(
                    validator_class_name="YAML",
                    original_text=response,
                    parsed_text=stripped
                ) from e

    def find_element(self, tree, key):
        if isinstance(tree, dict):
            return tree.get(key)
        return None

    def get_text(self, element):
        if isinstance(element, (str, int, float, bool, list, dict)) or element is None:
            return element
        return None

    def has_nested(self, element):
        return isinstance(element, (dict, list))

    def iter_direct_children(self, tree):
        if isinstance(tree, dict):
            for k, v in tree.items():
                yield v
        elif isinstance(tree, list):
            for item in tree:
                yield item

    def get_name(self, element):
        return None

    def find_all(self, tree, key):
        found = []
        def _find_all(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == key:
                        found.append(v)
                    _find_all(v)
            elif isinstance(obj, list):
                for item in obj:
                    _find_all(item)
        _find_all(tree)
        return found

    def get_subtree_string(self, elem):
        return yaml.dump(elem, allow_unicode=True) 