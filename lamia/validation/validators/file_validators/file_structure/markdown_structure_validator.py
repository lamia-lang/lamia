import mistune
from pydantic import BaseModel, create_model
from .document_structure_validator import DocumentStructureValidator
from ....base import BaseValidator, ValidationResult
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from .utils import import_model_from_path
import re
from collections import OrderedDict
from ....utils.type_matcher import TypeMatcher, TypeMatchResult

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

class MarkdownTypeMatcher(TypeMatcher):
    """Extended TypeMatcher that can handle markdown types."""
    
    def validate_and_convert(self, value, expected_type) -> TypeMatchResult:
        # Check if it's a markdown type
        if expected_type in MARKDOWN_TYPE_MAPPING:
            if isinstance(value, str):
                # Create the markdown type instance
                return TypeMatchResult(True, expected_type(value))
            else:
                return TypeMatchResult(False, None, f"Expected string for {expected_type.__name__}, got {type(value).__name__}")
        
        # Fall back to parent class for other types
        return super().validate_and_convert(value, expected_type)

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
        
        # Override the type_matcher to handle markdown types
        self.type_matcher = MarkdownTypeMatcher(strict=strict, get_text_func=self.get_text)
        
        # Track used elements for proper ordering
        self._used_elements = set()

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        """Override to provide markdown-specific validated_text format."""
        # Reset used elements for each validation
        self._used_elements = set()
        result = await super().validate_strict(response, **kwargs)
        return self._format_markdown_result(result)

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        """Override to provide markdown-specific validated_text format."""
        # Reset used elements for each validation
        self._used_elements = set()
        result = await super().validate_permissive(response, **kwargs)
        return self._format_markdown_result(result)

    def _format_markdown_result(self, result: ValidationResult) -> ValidationResult:
        """Convert the parent class result to the expected markdown format."""
        if not result.is_valid or not result.result_type or self.model is None:
            return result
        
        # Create validated_text as a dictionary with field names and their text values
        validated_text_dict = {}
        
        # Get all fields from the model
        all_fields = {}
        for field, field_info in self.model.model_fields.items():
            all_fields[field] = field_info.annotation
        
        if hasattr(self.model, "__ordered_fields__") and isinstance(self.model.__ordered_fields__, OrderedDict):
            for field_name, field_type in self.model.__ordered_fields__.items():
                if field_name not in all_fields:
                    all_fields[field_name] = field_type
        
        # Extract text values from the result_type
        for field_name in all_fields.keys():
            if hasattr(result.result_type, field_name):
                field_value = getattr(result.result_type, field_name)
                if hasattr(field_value, 'text'):
                    # Markdown type with .text property
                    validated_text_dict[field_name] = field_value.text
                else:
                    # Regular string or other type
                    validated_text_dict[field_name] = str(field_value)
        
        # Return new result with the dictionary format
        return ValidationResult(
            is_valid=result.is_valid,
            error_message=result.error_message,
            hint=result.hint,
            raw_text=result.raw_text,
            validated_text=validated_text_dict,
            result_type=result.result_type,
            info_loss=result.info_loss
        )

    def _validate_model_uses_markdown_types(self, model):
        """Ensure model only uses predefined markdown types or basic str types."""
        invalid_fields = []
        
        for field, field_info in model.model_fields.items():
            field_type = field_info.annotation
            # Check if it's a known markdown type or basic str type
            if field_type not in MARKDOWN_TYPE_MAPPING and field_type != str:
                invalid_fields.append(f"'{field}': {field_type.__name__}")
        
        if invalid_fields:
            available_types = ", ".join([cls.__name__ for cls in MARKDOWN_TYPE_MAPPING.keys()])
            raise ValueError(
                f"Markdown validation only supports predefined markdown types or str. "
                f"Invalid fields found: {', '.join(invalid_fields)}. "
                f"Available markdown types: {available_types}, str. "
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
                base_hint = (
                    "Please provide your Markdown content wrapped in triple backticks (``` ... ``` or ```markdown ... ```).\n"
                    "Ensure the Markdown matches the required structure exactly.\n"
                    "Expected structure:\n"
                    + '\n'.join(structure_lines)
                )
            else:
                base_hint = (
                    "Please provide your Markdown content wrapped in triple backticks (``` ... ``` or ```markdown ... ```).\n"
                    "Ensure the Markdown contains the required fields with the correct types.\n"
                    "The fields can be nested within other Markdown structures.\n"
                    "Required fields that must be present:\n"
                    + '\n'.join(structure_lines)
                )
            
            # Add clean ordering information
            ordering_hint = self._generate_field_ordering_hint(self.model)
            if ordering_hint:
                return base_hint + "\n\n" + ordering_hint
            else:
                return base_hint
        else:
            return "Please provide your Markdown content wrapped in triple backticks (``` ... ``` or ```markdown ... ```) and ensure it is well-formed."

    # Public methods
    def extract_payload(self, response: str) -> str:
        if self.generate_hints:
            # LLM mode - expect backticks
            markdown_match = re.search(r'```(?:markdown)?\s*\n?(.*?)\n?```', response, re.DOTALL | re.IGNORECASE)
            if markdown_match:
                return markdown_match.group(1).strip()
            return None
        else:
            # File mode - accept raw markdown
            return response

    def load_payload(self, payload: str) -> any:
        # Parse markdown into an AST using mistune 3.x
        return mistune.create_markdown(renderer='ast')(payload)

    def find_element(self, tree, key, depth=1):
        """Find the first unused element in the tree that matches the field type."""
        if self.model is None:
            return None
        
        # Get the field type
        field_type = None
        if hasattr(self.model, 'model_fields') and key in self.model.model_fields:
            field_type = self.model.model_fields[key].annotation
        elif hasattr(self.model, "__ordered_fields__") and isinstance(self.model.__ordered_fields__, OrderedDict):
            if key in self.model.__ordered_fields__:
                field_type = self.model.__ordered_fields__[key]
        
        if field_type is None:
            return None
        
        # Get the expected AST type and level
        ast_type, ast_level = self._ast_type_for_field(field_type)
        if ast_type is None:
            return None
        
        # Find the first matching element that hasn't been used
        for node in tree:
            if id(node) in self._used_elements:
                continue  # Skip already used elements
                
            if node.get('type') == ast_type:
                if ast_type == 'heading' and ast_level is not None:
                    if node.get('attrs', {}).get('level') == ast_level:
                        self._used_elements.add(id(node))
                        return node
                else:
                    self._used_elements.add(id(node))
                    return node
        
        return None

    def get_text(self, element):
        if self.model is None:
            return None
        if not element:
            return None
        return self._extract_text(element)

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
        """Find all elements in the tree that match the field type."""
        if self.model is None:
            return []
        
        # Get the field type
        field_type = None
        if hasattr(self.model, 'model_fields') and key in self.model.model_fields:
            field_type = self.model.model_fields[key].annotation
        elif hasattr(self.model, "__ordered_fields__") and isinstance(self.model.__ordered_fields__, OrderedDict):
            if key in self.model.__ordered_fields__:
                field_type = self.model.__ordered_fields__[key]
        
        if field_type is None:
            return []
        
        # Get the expected AST type and level
        ast_type, ast_level = self._ast_type_for_field(field_type)
        if ast_type is None:
            return []
        
        # Find all matching elements
        results = []
        for node in tree:
            if node.get('type') == ast_type:
                if ast_type == 'heading' and ast_level is not None:
                    if node.get('attrs', {}).get('level') == ast_level:
                        results.append(node)
                else:
                    results.append(node)
        
        return results



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
        # Handle str type as generic text (could be any markdown element)
        if typ == str:
            return ("paragraph", None)  # Default to paragraph for str fields
        return MARKDOWN_TYPE_MAPPING.get(typ, (None, None))

    def _extract_text(self, node):
        if node is None:
            return None
        if node.get('type') == 'text':
            return node.get('raw', '')
        if 'children' in node:
            return ''.join(self._extract_text(child) for child in node['children'])
        return node.get('raw', '')




    
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

    def get_field_order(self, tree):
        """Get field order for markdown - map markdown elements to their field names."""
        if not isinstance(tree, list) or self.model is None:
            return []
        
        # Get all model fields (including ordered fields)
        all_fields = {}
        for field, field_info in self.model.model_fields.items():
            all_fields[field] = field_info.annotation
        
        if hasattr(self.model, "__ordered_fields__") and isinstance(self.model.__ordered_fields__, OrderedDict):
            for field_name, field_type in self.model.__ordered_fields__.items():
                if field_name not in all_fields:
                    all_fields[field_name] = field_type
        
        # Map markdown elements to field names in order, avoiding duplicates
        order = []
        used_fields = set()
        
        for node in tree:
            node_type = node.get('type')
            if node_type in ('blank_line', 'thematic_break'):
                continue
                
            # Find which field this node could match (prefer unused fields)
            matched_field = None
            for field_name, field_type in all_fields.items():
                if field_name in used_fields:
                    continue  # Skip already used fields
                    
                ast_type, ast_level = self._ast_type_for_field(field_type)
                
                if node_type == ast_type:
                    if ast_type == 'heading' and ast_level is not None:
                        if node.get('attrs', {}).get('level') == ast_level:
                            matched_field = field_name
                            break
                    else:
                        matched_field = field_name
                        break
            
            if matched_field:
                order.append(matched_field)
                used_fields.add(matched_field)
        
        return order