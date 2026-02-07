"""
LLM command detector for identifying string literal patterns in function bodies.

Detects functions that contain string commands that should be processed as LLM commands.
"""

import ast
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Union


# ── Typed return-type descriptors ───────────────────────────────────────

@dataclass
class SimpleReturnType:
    """Simple return type like HTML, JSON, str."""
    base_type: str
    full_type: str


@dataclass
class ParametricReturnType:
    """Parametric return type like HTML[MyModel], JSON[Schema]."""
    base_type: str
    inner_type: str
    full_type: str


@dataclass
class FileWriteReturnType:
    """File write target from -> File(...) syntax."""
    path: str
    inner_return_type: Optional[Union[SimpleReturnType, ParametricReturnType]] = None
    append: bool = False
    encoding: str = "utf-8"


ReturnType = Union[SimpleReturnType, ParametricReturnType, FileWriteReturnType]


@dataclass
class FunctionParameter:
    """A function parameter with optional type annotation and default value."""
    name: str
    type_annotation: Optional[str] = None
    default: Optional[Any] = None


@dataclass
class LLMFunctionInfo:
    """Metadata for a detected LLM function."""
    command: str
    return_type: Optional[ReturnType]
    parameters: List[FunctionParameter]
    is_async: bool
    node: ast.AST


class LLMCommandDetector(ast.NodeVisitor):
    """Detects string literal patterns in function bodies that should be LLM commands."""
    
    def __init__(self):
        self.llm_functions: Dict[str, LLMFunctionInfo] = {}
    
    def detect_commands(self, source_code: str) -> Dict[str, LLMFunctionInfo]:
        """
        Detect LLM commands in source code.
        
        This is the main public interface method.
        
        Args:
            source_code: Python source code to analyze
            
        Returns:
            Dictionary of detected LLM functions with their metadata
        """
        tree = ast.parse(source_code)
        self.visit(tree)
        return self.llm_functions
    
    def visit_FunctionDef(self, node):
        """Handle function definitions that might contain string LLM commands."""
        self._process_function(node, is_async=False)
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node):
        """Handle async function definitions that might contain string LLM commands."""
        self._process_function(node, is_async=True)
        self.generic_visit(node)
    
    def _process_function(self, node, is_async: bool):
        """Process both sync and async function definitions."""
        command = self._extract_command_from_function(node)
        
        if command is None:
            # Not a pattern we recognize, skip
            return
            
        return_type = self._extract_return_type(node)
        parameters = self._extract_parameters(node)
        
        self.llm_functions[node.name] = LLMFunctionInfo(
            command=command,
            return_type=return_type,
            parameters=parameters,
            is_async=is_async,
            node=node,
        )
    
    def _extract_command_from_function(self, node) -> Optional[str]:
        """Extract string command from function body."""
        # Check if function body contains a single string literal (expression statement)
        if (len(node.body) == 1 and 
            isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, (ast.Constant, ast.Str))):
            
            # Single string literal case
            return self._extract_string_value(node.body[0].value)
                
        # Check if function has docstring + string literal (2 statements)
        elif (len(node.body) == 2 and
              isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, (ast.Constant, ast.Str)) and
              isinstance(node.body[1], ast.Expr) and isinstance(node.body[1].value, (ast.Constant, ast.Str))):
            
            # Docstring + command case - use the second string as the command
            return self._extract_string_value(node.body[1].value)
        
        return None
    
    def _extract_string_value(self, string_node) -> Optional[str]:
        """Extract string value from AST node."""
        if isinstance(string_node, ast.Constant) and isinstance(string_node.value, str):
            return string_node.value
        elif isinstance(string_node, ast.Str):  # For older Python versions
            return string_node.s
        return None
    
    def _extract_return_type(self, func_node) -> Optional[ReturnType]:
        """Extract return type annotation from function node."""
        if func_node.returns:
            # Check for File(...) call in return type position
            if self._is_file_call(func_node.returns):
                return self._extract_file_write_return_type(func_node.returns)

            return self._parse_type_node(func_node.returns)
        return None

    def _is_file_call(self, node) -> bool:
        """Check if AST node is a File(...) call."""
        return (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == 'File')

    def _extract_file_write_return_type(self, call_node) -> FileWriteReturnType:
        """Extract file write metadata from File(...) return type annotation.

        Handles:
            File("path")                         -> untyped write
            File(Type, "path")                    -> typed write
            File(Type[Inner], "path")             -> parametric typed write
            File(Type, "path", append=True)       -> typed append
            File("path", encoding="latin-1")      -> untyped write with encoding
        """
        args = call_node.args
        kwargs = {kw.arg: kw.value for kw in call_node.keywords}

        inner_return_type: Optional[Union[SimpleReturnType, ParametricReturnType]] = None
        path = ""

        if len(args) == 1:
            # File("path") - untyped write
            raw_path = self._ast_node_to_value(args[0])
            path = str(raw_path) if raw_path is not None else ""
        elif len(args) >= 2:
            # File(Type, "path") - typed write
            inner_return_type = self._parse_type_node(args[0])
            raw_path = self._ast_node_to_value(args[1])
            path = str(raw_path) if raw_path is not None else ""

        append = False
        if 'append' in kwargs:
            append = bool(self._ast_node_to_value(kwargs['append']))
        encoding = "utf-8"
        if 'encoding' in kwargs:
            raw_enc = self._ast_node_to_value(kwargs['encoding'])
            encoding = str(raw_enc) if raw_enc is not None else "utf-8"

        return FileWriteReturnType(
            path=path,
            inner_return_type=inner_return_type,
            append=append,
            encoding=encoding,
        )

    def _parse_type_node(self, type_node) -> Union[SimpleReturnType, ParametricReturnType]:
        """Parse an AST type node into a typed return type descriptor."""
        type_string = self._ast_to_type_string(type_node)
        if '[' in type_string and ']' in type_string:
            base_type = type_string.split('[')[0]
            inner_type = type_string.split('[')[1].rstrip(']')
            return ParametricReturnType(
                base_type=base_type,
                inner_type=inner_type,
                full_type=type_string,
            )
        return SimpleReturnType(
            base_type=type_string,
            full_type=type_string,
        )
    
    def _extract_parameters(self, func_node) -> List[FunctionParameter]:
        """Extract function parameters with their type annotations and default values."""
        parameters: List[FunctionParameter] = []
        defaults = func_node.args.defaults
        
        # Calculate offset for defaults (defaults align with the last N parameters)
        defaults_offset = len(func_node.args.args) - len(defaults)
        
        for i, arg in enumerate(func_node.args.args):
            type_annotation: Optional[str] = None
            default: Optional[Any] = None

            if arg.annotation:
                type_annotation = self._ast_to_type_string(arg.annotation)
            
            # Check if this parameter has a default value
            if i >= defaults_offset:
                default_index = i - defaults_offset
                default = self._ast_node_to_value(defaults[default_index])
            
            parameters.append(FunctionParameter(
                name=arg.arg,
                type_annotation=type_annotation,
                default=default,
            ))
        return parameters
    
    def _ast_to_type_string(self, ast_node):
        """Convert AST type annotation to string representation."""
        if isinstance(ast_node, ast.Name):
            return ast_node.id
        elif isinstance(ast_node, ast.Subscript):
            # Handle Generic[Args] syntax like HTML[MyModel]
            base = self._ast_to_type_string(ast_node.value)
            # Python 3.8 wraps slice in ast.Index; 3.9+ uses the node directly
            slice_node = ast_node.slice
            index_type = getattr(ast, 'Index', None)
            if index_type is not None and isinstance(slice_node, index_type):
                arg = self._ast_to_type_string(slice_node.value)  # type: ignore[attr-defined]
            else:
                arg = self._ast_to_type_string(slice_node)
            return f"{base}[{arg}]"
        elif isinstance(ast_node, ast.Attribute):
            # Handle module.Type syntax
            return f"{self._ast_to_type_string(ast_node.value)}.{ast_node.attr}"
        return str(ast_node)
    
    def _ast_node_to_value(self, node):
        """Convert AST node to value for models parameter (string or list)."""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Str):  # For older Python versions
            return node.s
        elif isinstance(node, ast.List):
            return [self._ast_node_to_value(item) for item in node.elts]
        else:
            # For unsupported types, return None
            return None
