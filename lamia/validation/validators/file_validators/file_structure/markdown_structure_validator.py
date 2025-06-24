import mistune
from pydantic import BaseModel, create_model
from .document_structure_validator import DocumentStructureValidator
from ....base import BaseValidator, ValidationResult
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from .utils import import_model_from_path

# Marker classes for semantic mapping
class MarkdownStr(str):
    def __new__(cls, text: str = ""):
        instance = super().__new__(cls, text)
        instance._text = text
        return instance
    
    @property
    def text(self) -> str:
        return self._text
        
    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler: GetCoreSchemaHandler):
        return core_schema.with_info_after_validator_function(
            function=lambda value, _: cls(text=str(value)),
            schema=core_schema.str_schema(),
            serialization=core_schema.str_schema(),
        )

    def __str__(self):
        return self._text

class Heading1(MarkdownStr): pass
class Heading2(MarkdownStr): pass
class Heading3(MarkdownStr): pass
class Heading4(MarkdownStr): pass
class Heading5(MarkdownStr): pass
class Heading6(MarkdownStr): pass
class Paragraph(MarkdownStr): pass
class BoldText(MarkdownStr): pass
class ItalicText(MarkdownStr): pass
class Strikethrough(MarkdownStr): pass
class Url(MarkdownStr): pass
class CodeBlock(MarkdownStr): pass
class InlineCode(MarkdownStr): pass
class ListItem(MarkdownStr): pass
class Blockquote(MarkdownStr): pass
class Table(MarkdownStr): pass
class Image(MarkdownStr): pass
class TaskListItem(MarkdownStr): pass
class Footnote(MarkdownStr): pass
class HorizontalRule(MarkdownStr): pass

MARKDOWN_TYPE_MAPPING = {
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
    Table: ("table", None),
    Image: ("image", None),
    TaskListItem: ("task_list_item", None),
    Footnote: ("footnote", None),
    HorizontalRule: ("thematic_break", None),
    BoldText: ("strong", None),
    ItalicText: ("emphasis", None),
    Strikethrough: ("strikethrough", None),
    Url: ("link", None),
}
# Add more markdown types as needed

class MarkdownStructureValidator(DocumentStructureValidator):
    """Validates if the Markdown matches a given Pydantic model structure, or just checks for well-formed Markdown if no model/schema is provided."""
    def __init__(self, model: BaseModel = None, model_name: str = None, schema: dict = None, strict: bool = True, model_module: str = "models", generate_hints: bool = False):
        resolved_model = None
        if model is not None:
            resolved_model = model
        elif model_name is not None:
            resolved_model = import_model_from_path(model_name, default_module=model_module)
        elif schema is not None:
            resolved_model = create_model("MarkdownStructureModel", **schema)
        else:
            resolved_model = None
        # If resolved_model is None, schema-less mode (well-formed only)
        super().__init__(model=resolved_model, strict=strict, generate_hints=generate_hints)

    @classmethod
    def name(cls) -> str:
        return "markdown_structure"

    @classmethod
    def file_type(cls) -> str:
        return "markdown"

    @property
    def initial_hint(self) -> str:
        if self.model is not None:
            structure_lines = describe_model_structure(self.model, format_type="markdown")
            return (
                "Please ensure the Markdown matches the required structure.\n"
                "Expected structure:\n"
                + '\n'.join(structure_lines)
            )
        else:
            return "Please ensure the Markdown is well-formed."

    def parse(self, response: str):
        # Parse markdown into an AST using mistune 3.x
        return mistune.create_markdown(renderer='ast')(response)

    def _extract_text_from_children(self, children):
        if not children:
            return ''
        texts = []
        for child in children:
            if child.get('type') == 'text':
                texts.append(child.get('raw', ''))
            elif 'children' in child:
                texts.append(self._extract_text_from_children(child['children']))
        return ''.join(texts)

    def find_element(self, tree, key, depth=1):
        if self.model is None:
            return None
        field_order = list(self.model.model_fields.keys())
        idx = field_order.index(key)
        if idx == 0:
            for node in tree:
                if node['type'] == 'heading':
                    if self.strict:
                        if node.get('attrs', {}).get('level') == depth:
                            return node
                    else:
                        return node
        else:
            found_heading = False
            for node in tree:
                if node['type'] == 'heading':
                    if self.strict:
                        if node.get('attrs', {}).get('level') == depth:
                            found_heading = True
                    else:
                        found_heading = True
                elif found_heading and node['type'] == 'paragraph':
                    return node
        return None

    def get_text(self, element):
        if self.model is None:
            return None
        if not element:
            return None
        return self._extract_text_from_children(element.get('children', []))

    def has_nested(self, element):
        if self.model is None:
            return False
        if not element or 'children' not in element:
            return False
        for child in element['children']:
            if child.get('type') != 'text':
                return True
        return False

    def iter_direct_children(self, tree, depth=1):
        if self.model is None:
            return
        field_order = list(self.model.model_fields.keys())
        yielded = set()
        for idx, field in enumerate(field_order):
            node = self.find_element(tree, field, depth=depth)
            if node is not None:
                yielded.add(id(node))
                yield node

    def get_name(self, element, depth=1):
        if self.model is None:
            return None
        field_order = list(self.model.model_fields.keys())
        for idx, field in enumerate(field_order):
            node = self.find_element(element if isinstance(element, list) else [element], field, depth=depth)
            if node is element:
                return field
        return None

    def find_all(self, tree, key, depth=1):
        if self.model is None:
            return []
        field_order = list(self.model.model_fields.keys())
        idx = field_order.index(key)
        results = []
        if idx == 0:
            for node in tree:
                if node['type'] == 'heading':
                    if self.strict:
                        if node.get('attrs', {}).get('level') == depth:
                            results.append(node)
                    else:
                        results.append(node)
        else:
            found_heading = False
            for node in tree:
                if node['type'] == 'heading':
                    if self.strict:
                        if node.get('attrs', {}).get('level') == depth:
                            found_heading = True
                    else:
                        found_heading = True
                elif found_heading and node['type'] == 'paragraph':
                    results.append(node)
        return results

    def _ast_type_for_field(self, typ):
        return MARKDOWN_TYPE_MAPPING.get(typ, (None, None))

    def _extract_text(self, node):
        if node is None:
            return None
        if node.get('type') == 'text':
            return node.get('raw', '')
        if 'children' in node:
            return ''.join(self._extract_text(child) for child in node['children'])
        return node.get('raw', '')

    def _match_fields(self, ast, model, strict: bool):
        fields = list(model.__annotations__.items())
        ast_idx = 0
        values = {}
        missing_fields = []
        for name, typ in fields:
            ast_type, ast_level = self._ast_type_for_field(typ)
            found = False
            scan_idx = ast_idx
            while scan_idx < len(ast):
                found = False
                node = ast[scan_idx]
                if node['type'] in ('blank_line', 'thematic_break'):
                    scan_idx += 1
                    continue
                if node['type'] == ast_type:
                    if ast_type == 'heading' and ast_level is not None:
                        if node.get('attrs', {}).get('level') == ast_level:
                            values[name] = self._extract_text(node)
                            scan_idx += 1
                            found = True
                            break
                    else:
                        values[name] = self._extract_text(node)
                        scan_idx += 1
                        found = True
                        break

                if not found and strict:
                    scan_idx += 1
                    break
                scan_idx += 1

            if not found:
                if strict:
                    return False, f"Missing element for field '{name}'", None
                else:
                    missing_fields.append(name)
                    # In permissive mode, advance ast_idx to scan_idx for next field
            ast_idx = scan_idx
        # In strict mode, ensure no extra nodes after last field
        if strict:
            while ast_idx < len(ast):
                if ast[ast_idx]['type'] not in ('blank_line', 'thematic_break'):
                    return False, "Extra elements found after last expected field", None
                ast_idx += 1
        if not strict and missing_fields:
            return False, f"Missing element(s) for field(s): {', '.join(missing_fields)}", None
        return True, None, values

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        if self.model is None:
            # Just check well-formedness
            try:
                self.parse(response)
                return ValidationResult(is_valid=True)
            except Exception as e:
                return ValidationResult(is_valid=False, error_message=f"Invalid Markdown: {e}")
        try:
            ast = self.parse(response)
        except Exception as e:
            return ValidationResult(is_valid=False, error_message=f"Invalid Markdown: {e}")
        valid, err, values = self._match_fields(ast, self.model, strict=True)
        if not valid:
            return ValidationResult(is_valid=False, error_message=err, hint=self.initial_hint)
        # Create an instance of the model with our values
        result_type = self.model(**values)
        return ValidationResult(is_valid=True, validated_text=values, result_type=result_type)

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        if self.model is None:
            # Just check well-formedness
            try:
                self.parse(response)
                return ValidationResult(is_valid=True)
            except Exception as e:
                return ValidationResult(is_valid=False, error_message=f"Invalid Markdown: {e}")
        try:
            ast = self.parse(response)
        except Exception as e:
            return ValidationResult(is_valid=False, error_message=f"Invalid Markdown: {e}")
        valid, err, values = self._match_fields(ast, self.model, strict=False)
        if not valid:
            return ValidationResult(is_valid=False, error_message=err, hint=self.initial_hint)
        # Create an instance of the model with our values
        result_type = self.model(**values)
        return ValidationResult(is_valid=True, validated_text=values, result_type=result_type)

    def _describe_structure(self, model, indent=0):
        lines = []
        prefix = '  ' * indent
        for field, field_info in model.model_fields.items():
            submodel = field_info.annotation
            if hasattr(submodel, "model_fields"):
                lines.append(f'{prefix}{field}:')
                lines.extend(self._describe_structure(submodel, indent + 1))
            else:
                lines.append(f'{prefix}{field}: ...')
        return lines 