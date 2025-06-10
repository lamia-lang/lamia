from ...base import BaseValidator, ValidationResult
from .file_structure.markdown_structure_validator import MarkdownStructureValidator
from .file_structure.markdown_types import *
from pydantic import BaseModel
import mistune

class MarkdownValidator(BaseValidator):
    """Validates Markdown against a flat Pydantic model of Markdown element types."""
    def __init__(self, model: BaseModel = None, strict: bool = True):
        super().__init__(strict=strict)
        self.model = model
        self.ast_parser = mistune.create_markdown(renderer='ast')

    @classmethod
    def name(cls) -> str:
        return "markdown"

    @property
    def initial_hint(self) -> str:
        if self.model is None:
            return "Please ensure the Markdown is well-formed."
        else:
            fields = list(self.model.__annotations__.items())
            return "Expected Markdown structure (in order):\n" + "\n".join(f"- {name}: {typ.__name__}" for name, typ in fields)

    def _ast_type_for_field(self, typ):
        # Map our types to mistune AST node types
        mapping = {
            Heading1: ("heading", 1),
            Heading2: ("heading", 2),
            Heading3: ("heading", 3),
            Heading4: ("heading", 4),
            Heading5: ("heading", 5),
            Heading6: ("heading", 6),
            Paragraph: ("paragraph", None),
            CodeBlock: ("block_code", None),
            InlineCode: ("codespan", None),
            ListItem: ("list_item", None),
            Blockquote: ("block_quote", None),
            # Add more as needed
        }
        return mapping.get(typ, (None, None))

    def _extract_text(self, node):
        if node is None:
            return None
        if node.get('type') == 'text':
            return node.get('raw', '')
        if 'children' in node:
            return ''.join(self._extract_text(child) for child in node['children'])
        return node.get('raw', '')

    def _match_fields_strict(self, ast, model):
        fields = list(model.__annotations__.items())
        ast_idx = 0
        values = {}
        for name, typ in fields:
            ast_type, ast_level = self._ast_type_for_field(typ)
            # Find the next matching node
            if ast_idx >= len(ast):
                return False, f"Missing element for field '{name}'", None
            node = ast[ast_idx]
            if ast_type is None:
                return False, f"Unsupported type for field '{name}'", None
            if node['type'] != ast_type:
                return False, f"Expected {ast_type} for field '{name}', got {node['type']}", None
            if ast_type == 'heading' and ast_level is not None:
                if node.get('attrs', {}).get('level') != ast_level:
                    return False, f"Expected heading level {ast_level} for field '{name}', got {node.get('attrs', {}).get('level')}", None
            values[name] = self._extract_text(node)
            ast_idx += 1
        # Check for extra nodes in strict mode
        if ast_idx < len(ast):
            return False, "Extra elements found after last expected field", None
        return True, None, values

    def _match_fields_permissive(self, ast, model):
        fields = list(model.__annotations__.items())
        ast_idx = 0
        values = {}
        for name, typ in fields:
            ast_type, ast_level = self._ast_type_for_field(typ)
            # Find the next matching node, skipping extras
            found = False
            while ast_idx < len(ast):
                node = ast[ast_idx]
                if node['type'] == ast_type:
                    if ast_type == 'heading' and ast_level is not None:
                        if node.get('attrs', {}).get('level') != ast_level:
                            ast_idx += 1
                            continue
                    values[name] = self._extract_text(node)
                    ast_idx += 1
                    found = True
                    break
                ast_idx += 1
            if not found:
                return False, f"Missing element for field '{name}'", None
        return True, None, values

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        if self.model is None:
            # Just check well-formedness
            try:
                self.ast_parser(response)
                return ValidationResult(is_valid=True)
            except Exception as e:
                return ValidationResult(is_valid=False, error_message=f"Invalid Markdown: {e}")
        try:
            ast = self.ast_parser(response)
        except Exception as e:
            return ValidationResult(is_valid=False, error_message=f"Invalid Markdown: {e}")
        valid, err, values = self._match_fields_strict(ast, self.model)
        if not valid:
            return ValidationResult(is_valid=False, error_message=err)
        return ValidationResult(is_valid=True, validated_text=values)

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        if self.model is None:
            # Just check well-formedness
            try:
                self.ast_parser(response)
                return ValidationResult(is_valid=True)
            except Exception as e:
                return ValidationResult(is_valid=False, error_message=f"Invalid Markdown: {e}")
        try:
            ast = self.ast_parser(response)
        except Exception as e:
            return ValidationResult(is_valid=False, error_message=f"Invalid Markdown: {e}")
        valid, err, values = self._match_fields_permissive(ast, self.model)
        if not valid:
            return ValidationResult(is_valid=False, error_message=err)
        return ValidationResult(is_valid=True, validated_text=values) 