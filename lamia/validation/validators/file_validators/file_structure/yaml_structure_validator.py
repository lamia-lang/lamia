import yaml

from pydantic import BaseModel, create_model
import re
from .document_structure_validator import DocumentStructureValidator
from .utils import import_model_from_path


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

    @classmethod
    def file_type(cls) -> str:
        return "yaml"


            
    def extract_payload(self, response: str) -> str:
        markdown_match = re.search(r'```(?:yaml|yml)?\s*\n?(.*?)\n?```', response, re.DOTALL | re.IGNORECASE)
        if markdown_match:
            yaml_candidate = markdown_match.group(1).strip()
            try:
                yaml.safe_load(yaml_candidate)
                return yaml_candidate
            except yaml.YAMLError:
                return None
        else:
            # Try to parse the entire response as YAML first
            try:
                yaml.safe_load(response.strip())
                return response.strip()
            except yaml.YAMLError:
                pass
            
            # Fallback: extract YAML-like lines (including nested structure)
            # Only use this fallback if there are lines that look like surrounding text
            response_lines = response.split('\n')
            non_empty_lines = [line for line in response_lines if line.strip()]
            
            # Check if all non-empty lines look like YAML
            yaml_like_lines = []
            non_yaml_lines = []
            
            for line in response_lines:
                stripped_line = line.strip()
                if not stripped_line:  # Empty line
                    yaml_like_lines.append(line)
                elif (re.match(r'^[\w\s-]+:\s*.*$', stripped_line) or  # key: value or key:
                      re.match(r'^\s+[\w\s-]+:\s*.*$', line)):        # indented nested key: value
                    yaml_like_lines.append(line)
                else:
                    non_yaml_lines.append(line)
            
            # If there are non-YAML lines, only extract if they seem like surrounding text
            # (not if they look like malformed YAML)
            if non_yaml_lines:
                # Check if non-YAML lines look like malformed YAML keys
                for line in non_yaml_lines:
                    stripped = line.strip()
                    # If it looks like a key without value (common YAML error), reject extraction
                    if re.match(r'^[\w\s-]+$', stripped) and not re.match(r'^(true|false|null|\d+)$', stripped.lower()):
                        return None
                
                # If we reach here, non-YAML lines seem like surrounding text, so extract YAML
                yaml_candidate = '\n'.join(yaml_like_lines)
            else:
                # All lines are YAML-like, but original parsing failed - likely malformed YAML
                return None
            
            if yaml_like_lines:
                yaml_candidate = '\n'.join(yaml_like_lines)
                try:
                    yaml.safe_load(yaml_candidate)
                    return yaml_candidate
                except yaml.YAMLError:
                    return None
                
            return None

    def load_payload(self, payload: str) -> any:
        return yaml.safe_load(payload)

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
        return yaml.dump(elem, allow_unicode=True, sort_keys=False)

    def get_field_order(self, tree):
        """Get the order of keys as they appear in the YAML object."""
        if isinstance(tree, dict):
            return list(tree.keys())
        return []

    def _describe_structure(self, model, indent=0):
        lines = []
        prefix = '  ' * indent
        
        field_items = list(model.model_fields.items())
        
        for field, field_info in field_items:
            submodel = field_info.annotation
                
            if hasattr(submodel, "model_fields"):
                lines.append(f'{prefix}{field}:')
                lines.extend(self._describe_structure(submodel, indent + 1))
            else:
                lines.append(f'{prefix}{field}: ...')
            
        return lines 