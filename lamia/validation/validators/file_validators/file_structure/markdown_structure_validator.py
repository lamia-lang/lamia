import mistune
from pydantic import BaseModel, create_model
from .document_structure_validator import DocumentStructureValidator
from ....base import BaseValidator, ValidationResult
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from .utils import import_model_from_path
import re
from collections import OrderedDict

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

# Headers
class Heading1(MarkdownStr): pass
class Heading2(MarkdownStr): pass
class Heading3(MarkdownStr): pass
class Heading4(MarkdownStr): pass
class Heading5(MarkdownStr): pass
class Heading6(MarkdownStr): pass

# Block elements
class Paragraph(MarkdownStr): pass
class Blockquote(MarkdownStr): pass
class OrderedList(MarkdownStr): pass  # Numbered lists
class UnorderedList(MarkdownStr): pass  # Bullet lists
class ListItem(MarkdownStr): pass
class DefinitionList(MarkdownStr): pass  # Term: definition lists
class DefinitionTerm(MarkdownStr): pass
class DefinitionDescription(MarkdownStr): pass

# Code and preformatted
class CodeBlock(MarkdownStr): pass
class FencedCode(MarkdownStr): pass  # ```language code blocks
class IndentedCode(MarkdownStr): pass  # 4-space indented code

# Tables and dividers
class Table(MarkdownStr): pass
class TableRow(MarkdownStr): pass
class TableCell(MarkdownStr): pass
class HorizontalRule(MarkdownStr): pass

# Mapping of semantic types to mistune AST node types
MARKDOWN_TYPE_MAPPING = OrderedDict({
    # Headers
    Heading1: ("heading", 1),
    Heading2: ("heading", 2),
    Heading3: ("heading", 3),
    Heading4: ("heading", 4),
    Heading5: ("heading", 5),
    Heading6: ("heading", 6),
    
    # Block elements
    Paragraph: ("paragraph", None),
    Blockquote: ("block_quote", None),
    OrderedList: ("list", "ordered"),
    UnorderedList: ("list", "bullet"),
    ListItem: ("list_item", None),
    
    # Code blocks
    CodeBlock: ("block_code", None),
    FencedCode: ("block_code", "fenced"),
    IndentedCode: ("block_code", "indented"),
    
    # Special elements
    HorizontalRule: ("thematic_break", None),
})

# Currently, markdown is treated as a flat structure, in the future we might want to support nested structures
# like detecting bold text, italic text, etc. in the top level elements.
#
# NOTE: The following elements are not supported because they require special handling:
# - Definition lists (mistune parses them as paragraphs)
# - Tables (mistune parses them as paragraphs)
# - Table rows and cells (mistune doesn't separate them)
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
        # Start with statically annotated model fields
        fields = list(model.__annotations__.items())

        if hasattr(model, "__ordered_fields__") and isinstance(model.__ordered_fields__, OrderedDict):
            for fname, ftype in model.__ordered_fields__.items():
                if fname not in model.__annotations__:
                    fields.append((fname, ftype))

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
                if node['type'] in ('blank_line'):
                    scan_idx += 1
                    continue
                if node['type'] == ast_type:
                    if ast_type == 'heading' and ast_level is not None:
                        if node.get('attrs', {}).get('level') == ast_level:
                            values[name] = typ(self._extract_text(node))
                            scan_idx += 1
                            found = True
                            break
                    else:
                        values[name] = typ(self._extract_text(node))
                        scan_idx += 1
                        found = True
                        break

                if not found and strict:
                    scan_idx += 1
                    break
                scan_idx += 1

            if not found:
                # Both strict and permissive modes now collect all missing fields
                missing_fields.append(name)
                # In permissive mode, advance ast_idx to scan_idx for next field
            ast_idx = scan_idx
        
        # Check for missing fields (both modes)
        if missing_fields:
            # Check if missing fields might be due to field order issues
            if hasattr(model, "__ordered_fields__") and isinstance(model.__ordered_fields__, OrderedDict):
                # Look for any fields that exist but are in wrong order
                ordered_field_names = list(model.__ordered_fields__.keys())
                found_fields = set(values.keys())
                missing_field_set = set(missing_fields)
                
                # Check if any missing fields actually exist in the AST but in wrong position
                order_violation_detected = False
                for missing_field in missing_fields:
                    missing_field_type = model.__ordered_fields__.get(missing_field)
                    if missing_field_type:
                        ast_type, ast_level = self._ast_type_for_field(missing_field_type)
                        # Look for this type in the entire AST
                        for node in ast:
                            if node.get('type') == ast_type:
                                if ast_type == 'heading' and ast_level is not None:
                                    if node.get('attrs', {}).get('level') == ast_level:
                                        order_violation_detected = True
                                        break
                                else:
                                    order_violation_detected = True
                                    break
                
                if order_violation_detected:
                    return False, f"Field order validation failed. Expected order: {', '.join(ordered_field_names)}. Elements must appear in the specified order.", None
            
            return False, f"Missing element(s) for field(s): {', '.join(missing_fields)}", None
            
        # In strict mode, ensure no extra nodes after last field
        if strict:
            while ast_idx < len(ast):
                if ast[ast_idx]['type'] not in ('blank_line'):
                    return False, "Extra elements found after last expected field", None
                ast_idx += 1
        
        return True, None, values

    async def _validate_common(self, response: str, strict: bool, **kwargs) -> ValidationResult:
        """Shared validation logic for both strict and permissive modes."""
        payload = self.extract_payload(response)
        if payload is None:
            if self.generate_hints:
                # LLM mode - expected backticks but didn't find them
                error_msg = f"Invalid Response: the markdown is not wrapped in triple backticks"
            else:
                # File mode - this shouldn't happen since extract_payload returns the raw response
                error_msg = f"Invalid Response: empty or invalid markdown content"
            return ValidationResult(is_valid=False, error_message=error_msg, hint=self.get_retry_hint(retry_hint=error_msg))

        ast = self.load_payload(payload)  # Parse Markdown string into AST

        if self.model is None:
            return ValidationResult(is_valid=True, validated_text=self.get_subtree_string(ast))

        valid, err, values = self._match_fields(ast, model=self.model, strict=strict)
        if not valid:
            return ValidationResult(is_valid=False, error_message=err, hint=self.get_retry_hint(retry_hint=err))
        
        model_kwargs = {k: v for k, v in values.items() if k in self.model.model_fields}
        result_type = self.model(**model_kwargs)

        if hasattr(self.model, "__ordered_fields__") and isinstance(self.model.__ordered_fields__, OrderedDict):
            for field_name in self.model.__ordered_fields__.keys():
                if field_name in values and not hasattr(result_type, field_name):
                    # Use __dict__ to bypass Pydantic's field validation
                    result_type.__dict__[field_name] = values[field_name]
        
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
            if hasattr(result_type, field_name):
                field_value = getattr(result_type, field_name)
                if hasattr(field_value, 'text'):
                    # Markdown type with .text property
                    validated_text_dict[field_name] = field_value.text
                else:
                    # Regular string or other type
                    validated_text_dict[field_name] = str(field_value)
        
        return ValidationResult(
            is_valid=True, 
            validated_text=validated_text_dict,
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
            Blockquote: "> Blockquote (line starting with >)",
            OrderedList: "Ordered list (numbered list)",
            UnorderedList: "- List item (bullet point starting with dash)",
            ListItem: "- List item (bullet point starting with dash)",
            DefinitionList: "Definition list (term: definition pairs)",
            DefinitionTerm: "Definition term",
            DefinitionDescription: "Definition description",
            CodeBlock: "```code block``` (fenced code block with triple backticks)",
            FencedCode: "```language code block``` (fenced code block with triple backticks)",
            IndentedCode: "4-space indented code block",
            Table: "| Table | with | columns | (pipe-separated values)",
            TableRow: "Table row",
            TableCell: "Table cell",
            HorizontalRule: "--- (horizontal rule with three dashes)",
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
        """Get field order for markdown - extract structure elements in order they appear."""
        if not isinstance(tree, list):
            return []
        
        order = []
        for node in tree:
            if node.get('type') == 'heading':
                level = node.get('attrs', {}).get('level', 1)
                order.append(f"heading_{level}")
            elif node.get('type') == 'paragraph':
                order.append("paragraph")
            elif node.get('type') in ['block_code', 'code_block']:
                order.append("code_block")
            elif node.get('type') == 'list_item':
                order.append("list_item")
            elif node.get('type') == 'block_quote':
                order.append("blockquote")
            # Add more types as needed
        
        return order