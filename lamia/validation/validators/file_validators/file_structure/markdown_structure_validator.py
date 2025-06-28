import mistune
from pydantic import BaseModel, create_model
from .document_structure_validator import DocumentStructureValidator
from ....base import BaseValidator, ValidationResult
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from .utils import import_model_from_path
import re

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
    
    # Constructor
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
        if resolved_model is not None:
            self._validate_model_uses_markdown_types(resolved_model)
        super().__init__(model=resolved_model, strict=strict, generate_hints=generate_hints)

    def _validate_model_uses_markdown_types(self, model):
        """Ensure model only uses predefined markdown types, not regular types like str, int, etc."""
        invalid_fields = []
        
        for field, field_info in model.model_fields.items():
            field_type = field_info.annotation
            # Check if it's a known markdown type
            if field_type not in MARKDOWN_TYPE_MAPPING:
                invalid_fields.append(f"'{field}': {field_type.__name__}")
        
        if invalid_fields:
            available_types = ", ".join([cls.__name__ for cls in MARKDOWN_TYPE_MAPPING.keys()])
            raise ValueError(
                f"Markdown validation only supports predefined markdown types. "
                f"Invalid fields found: {', '.join(invalid_fields)}. "
                f"Available markdown types: {available_types}. "
                f"Use Heading1-6 for headings, Paragraph for text, etc."
            )

    # Class methods
    @classmethod
    def name(cls) -> str:
        return "markdown_structure"

    @classmethod
    def file_type(cls) -> str:
        return "markdown"

    # Properties
    @property
    def initial_hint(self) -> str:
        if self.model is not None:
            structure_lines = self._describe_structure(self.model)
            if self.strict:
                return (
                    "Please provide your Markdown content wrapped in triple backticks (``` ... ``` or ```markdown ... ```).\n"
                    "Ensure the Markdown matches the required structure exactly.\n"
                    "Expected structure:\n"
                    + '\n'.join(structure_lines)
                )
            else:
                return (
                    "Please provide your Markdown content wrapped in triple backticks (``` ... ``` or ```markdown ... ```).\n"
                    "Ensure the Markdown contains the required fields with the correct types.\n"
                    "The fields can be nested within other Markdown structures.\n"
                    "Required fields that must be present:\n"
                    + '\n'.join(structure_lines)
                )
        else:
            return "Please provide your Markdown content wrapped in triple backticks (``` ... ``` or ```markdown ... ```) and ensure it is well-formed."

    # Public methods
    def extract_payload(self, response: str) -> str:
        markdown_match = re.search(r'```(?:markdown)?\s*\n?(.*?)\n?```', response, re.DOTALL | re.IGNORECASE)
        if markdown_match:
            return markdown_match.group(1).strip()
        return None

    def load_payload(self, payload: str) -> any:
        # Parse markdown into an AST using mistune 3.x
        return mistune.create_markdown(renderer='ast')(payload)

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

    # Overrides the base class method because unlike other file structure validators, 
    # Markdown works with it's own predefined classes like Heading1, Paragraph, etc.
    # Also, even in strict mode, we want to wait for a marddown wrapped in ```-s.
    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        return await self._validate_common(response, strict=True, **kwargs)

    # Overrides the base class method because unlike other file structure validators, 
    # Markdown works with it's own predefined classes like Heading1, Paragraph, etc.
    # Also, even in strict mode, we want to wait for a marddown wrapped in ```-s.
    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        return await self._validate_common(response, strict=False, **kwargs)

    # Private methods
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

    async def _validate_common(self, response: str, strict: bool, **kwargs) -> ValidationResult:
        """Shared validation logic for both strict and permissive modes."""
        payload = self.extract_payload(response)
        if payload is None:
            error_msg = f"Invalid Markdown: {response}"
            return ValidationResult(is_valid=False, error_message=error_msg, hint=self.get_retry_hint(retry_hint=error_msg))

        ast = self.load_payload(payload)  # Parse Markdown string into AST

        if self.model is None:
            return ValidationResult(is_valid=True, validated_text=self.get_subtree_string(ast))

        valid, err, values = self._match_fields(ast, model=self.model, strict=strict)
        if not valid:
            return ValidationResult(is_valid=False, error_message=err, hint=self.get_retry_hint(retry_hint=err))
        
        # Create an instance of the model with converted values
        try:
            result_type = self.model(**values)
        except Exception as e:
            error_msg = f"Model creation error: {e}"
            return ValidationResult(
                is_valid=False, 
                error_message=error_msg,
                hint=self.get_retry_hint(error=e)
            )
        
        return ValidationResult(
            is_valid=True, 
            validated_text=self.get_subtree_string(ast),
            result_type=result_type,
        )
    
    def get_subtree_string(self, elem):
        """Convert markdown AST back to string or return string as-is."""
        # If elem is already a string (the markdown text), return it directly
        if isinstance(elem, str):
            return elem
            
        # If elem is a list of AST tokens, extract text content
        if isinstance(elem, list):
            result = ""
            for token in elem:
                if isinstance(token, dict):
                    if 'raw' in token:
                        result += token['raw']
                    elif token.get('type') == 'text' and 'raw' in token:
                        result += token['raw']
                    elif token.get('type') == 'heading' and 'children' in token:
                        # Extract text from heading children and reconstruct heading
                        level = token.get('attrs', {}).get('level', 1)
                        heading_text = ""
                        for child in token['children']:
                            if child.get('type') == 'text' and 'raw' in child:
                                heading_text += child['raw']
                        if heading_text:
                            result += f"{'#' * level} {heading_text}\n"
            return result.strip()
        
        # If elem is a single AST token, extract its content
        if isinstance(elem, dict):
            if 'raw' in elem:
                return elem['raw']
            elif elem.get('type') == 'text' and 'raw' in elem:
                return elem['raw']
            elif elem.get('type') == 'heading' and 'children' in elem:
                # Reconstruct heading from AST
                level = elem.get('attrs', {}).get('level', 1)
                heading_text = ""
                for child in elem['children']:
                    if child.get('type') == 'text' and 'raw' in child:
                        heading_text += child['raw']
                if heading_text:
                    return f"{'#' * level} {heading_text}"
        
        # Fallback - return string representation
        return str(elem)

    def _describe_structure(self, model, indent=0):
        """Describe structure using LLM-friendly markdown syntax descriptions instead of class names."""
        lines = []
        prefix = '  ' * indent
        for field, field_info in model.model_fields.items():
            field_type = field_info.annotation
            if hasattr(field_type, "model_fields"):
                lines.append(f'{prefix}{field}:')
                lines.extend(self._describe_structure(field_type, indent + 1))
            else:
                # Convert markdown type to human-readable description
                markdown_description = self._get_markdown_type_description(field_type)
                lines.append(f'{prefix}{field}: {markdown_description}')
        return lines 

    def _get_markdown_type_description(self, field_type):
        """Convert a markdown field type to a human-readable description for LLMs."""
        type_descriptions = {
            Heading1: "# Level 1 heading (starts with single #)",
            Heading2: "## Level 2 heading (starts with ##)",
            Heading3: "### Level 3 heading (starts with ###)",
            Heading4: "#### Level 4 heading (starts with ####)",
            Heading5: "##### Level 5 heading (starts with #####)",
            Heading6: "###### Level 6 heading (starts with ######)",
            Paragraph: "Regular paragraph text (plain text without special formatting)",
            BoldText: "**Bold text** (surrounded by double asterisks)",
            ItalicText: "*Italic text* (surrounded by single asterisks)",
            Strikethrough: "~~Strikethrough text~~ (surrounded by double tildes)",
            CodeBlock: "```code block``` (fenced code block with triple backticks)",
            InlineCode: "`inline code` (surrounded by single backticks)",
            ListItem: "- List item (bullet point starting with dash)",
            Blockquote: "> Blockquote (line starting with >)",
            Table: "| Table | with | columns | (pipe-separated values)",
            Image: "![Alt text](image-url) (image syntax)",
            TaskListItem: "- [ ] Task list item (checkbox list item)",
            Footnote: "[^footnote] (footnote reference)",
            HorizontalRule: "--- (horizontal rule with three dashes)",
            Url: "[Link text](url) (link syntax)",
        }
        
        # Handle generic types like str, int, etc.
        if field_type == str:
            return "string value"
        elif field_type == int:
            return "integer value"
        elif field_type == float:
            return "float value"
        elif field_type == bool:
            return "boolean value"
        
        # Get description for markdown types
        description = type_descriptions.get(field_type)
        if description:
            return description
        
        # Fallback for unknown types
        type_name = getattr(field_type, '__name__', str(field_type))
        return f"{type_name} (custom type)"