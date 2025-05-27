import importlib
from pydantic import BaseModel, create_model
from .document_structure_validator import DocumentStructureValidator
import mistune

def import_model_from_path(path: str, default_module: str = "models"):
    if "." in path:
        parts = path.split('.')
        module_path = '.'.join(parts[:-1])
        class_name = parts[-1]
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)
    else:
        mod = importlib.import_module(default_module)
        return getattr(mod, path)

def describe_model_structure(model, indent=0):
    lines = []
    prefix = '  ' * indent
    for field, field_info in model.model_fields.items():
        submodel = field_info.annotation
        if hasattr(submodel, "model_fields"):
            lines.append(f'{prefix}{field}:')
            lines.extend(describe_model_structure(submodel, indent + 1))
        else:
            lines.append(f'{prefix}{field}: ...')
    return lines

class MarkdownStructureValidator(DocumentStructureValidator):
    """Validates if the Markdown matches a given Pydantic model structure.
    Limitations: Only block-level structure (headings, paragraphs, lists, etc.) is validated, not inline formatting.
    """
    def __init__(self, model: BaseModel = None, model_name: str = None, schema: dict = None, strict: bool = True, model_module: str = "models"):
        if model is not None:
            resolved_model = model
        elif model_name is not None:
            resolved_model = import_model_from_path(model_name, default_module=model_module)
        elif schema is not None:
            resolved_model = create_model("MarkdownStructureModel", **schema)
        else:
            raise ValueError("MarkdownStructureValidator requires a Pydantic model, model_name, or a schema dict.")
        super().__init__(model=resolved_model, strict=strict)

    @classmethod
    def name(cls) -> str:
        return "markdown_structure"

    @property
    def initial_hint(self) -> str:
        structure_lines = describe_model_structure(self.model)
        return (
            "Please ensure the Markdown matches the required structure.\n"
            "Expected structure:\n"
            + '\n'.join(structure_lines)
        )

    def parse(self, response: str):
        # Parse markdown into an AST using mistune
        return mistune.create_markdown(renderer=mistune.AstRenderer())(response)

    def find_element(self, tree, key):
        # Only direct children (block-level)
        for node in tree:
            if node.get('type') == key:
                return node
        return None

    def get_text(self, element):
        # For block-level, get text content if available
        return element.get('text') if element and 'text' in element else None

    def has_nested(self, element):
        return bool(element.get('children')) if element else False

    def iter_direct_children(self, tree):
        return iter(tree)

    def get_name(self, element):
        return element.get('type') if element else None

    def find_all(self, tree, key):
        found = []
        def _find_all(nodes):
            for node in nodes:
                if node.get('type') == key:
                    found.append(node)
                if 'children' in node and node['children']:
                    _find_all(node['children'])
        _find_all(tree)
        return found 