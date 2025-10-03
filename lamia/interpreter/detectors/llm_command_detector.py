"""
LLM command detector for identifying string literal patterns in function bodies.

Detects functions that contain string commands that should be processed as LLM commands.
"""

import ast
from typing import Dict, Any, List, Optional


class LLMCommandDetector(ast.NodeVisitor):
    """Detects string literal patterns in function bodies that should be LLM commands."""
    
    def __init__(self):
        self.llm_functions = {}
    
    def detect_commands(self, source_code: str) -> Dict[str, Any]:
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
        
        self.llm_functions[node.name] = {
            'type': 'function_with_string_command',
            'command': command,
            'return_type': return_type,
            'parameters': parameters,
            'is_async': is_async,
            'node': node
        }
    
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
    
    def _extract_return_type(self, func_node):
        """Extract return type annotation from function node."""
        if func_node.returns:
            return_type_info = self._ast_to_type_string(func_node.returns)
            # Check if it's a parametric type like HTML[MyModel]
            if '[' in return_type_info and ']' in return_type_info:
                base_type = return_type_info.split('[')[0]
                inner_type = return_type_info.split('[')[1].rstrip(']')
                return {
                    'type': 'parametric',
                    'base_type': base_type,
                    'inner_type': inner_type,
                    'full_type': return_type_info
                }
            else:
                return {
                    'type': 'simple',
                    'base_type': return_type_info,
                    'full_type': return_type_info
                }
        return None
    
    def _extract_parameters(self, func_node):
        """Extract function parameters with their type annotations and default values."""
        parameters = []
        defaults = func_node.args.defaults
        
        # Calculate offset for defaults (defaults align with the last N parameters)
        defaults_offset = len(func_node.args.args) - len(defaults)
        
        for i, arg in enumerate(func_node.args.args):
            param_info = {
                'name': arg.arg,
                'type': None,
                'default': None
            }
            
            if arg.annotation:
                param_info['type'] = self._ast_to_type_string(arg.annotation)
            
            # Check if this parameter has a default value
            if i >= defaults_offset:
                default_index = i - defaults_offset
                param_info['default'] = self._ast_node_to_value(defaults[default_index])
            
            parameters.append(param_info)
        return parameters
    
    def _ast_to_type_string(self, ast_node):
        """Convert AST type annotation to string representation."""
        if isinstance(ast_node, ast.Name):
            return ast_node.id
        elif isinstance(ast_node, ast.Subscript):
            # Handle Generic[Args] syntax like HTML[MyModel]
            base = self._ast_to_type_string(ast_node.value)
            if hasattr(ast_node.slice, 'value'):
                arg = self._ast_to_type_string(ast_node.slice.value)
            else:
                arg = self._ast_to_type_string(ast_node.slice)
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
