import yaml
from pydantic import BaseModel, create_model
from .document_structure_validator import DocumentStructureValidator
from .utils import import_model_from_path, describe_model_structure

class YAMLStructureValidator(DocumentStructureValidator):
    """Validates if the YAML matches a given Pydantic model structure."""
    def __init__(self, model: BaseModel = None, model_name: str = None, schema: dict = None, strict: bool = True, model_module: str = "models"):
        if model is not None:
            resolved_model = model
        elif model_name is not None:
            resolved_model = import_model_from_path(model_name, default_module=model_module)
        elif schema is not None:
            resolved_model = create_model("YAMLStructureModel", **schema)
        else:
            raise ValueError("YAMLStructureValidator requires a Pydantic model, model_name, or a schema dict.")
        super().__init__(model=resolved_model, strict=strict)

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
        return yaml.safe_load(response)

    def find_element(self, tree, key):
        if isinstance(tree, dict):
            return tree.get(key)
        return None

    def get_text(self, element):
        if isinstance(element, (str, int, float, bool)) or element is None:
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