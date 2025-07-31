"""AST analyzer for detecting used action namespaces in .hu files."""

import ast
from typing import Set, Dict, Any
from lamia.types import HTML, JSON, CSV, XML, YAML, Markdown


class ActionNamespaceAnalyzer(ast.NodeVisitor):
    """Analyzes AST to detect which action namespaces are used."""
    
    def __init__(self):
        self.used_namespaces: Set[str] = set()
        self.used_types: Set[str] = set()
        
    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Visit attribute access like web.click(), http.get()."""
        if isinstance(node.value, ast.Name):
            namespace = node.value.id
            # Check if it's one of our action namespaces
            if namespace in ['web', 'http', 'file', 'db', 'email']:
                self.used_namespaces.add(namespace)
        
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name) -> None:
        """Visit name references like HTML, JSON, etc."""
        # Check if it's one of our validation types
        if node.id in ['HTML', 'JSON', 'CSV', 'XML', 'YAML', 'Markdown']:
            self.used_types.add(node.id)
        
        self.generic_visit(node)
    
    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Visit subscript access like HTML[Model], JSON[Schema]."""
        if isinstance(node.value, ast.Name):
            type_name = node.value.id
            if type_name in ['HTML', 'JSON', 'CSV', 'XML', 'YAML', 'Markdown']:
                self.used_types.add(type_name)
        
        self.generic_visit(node)


def analyze_hybrid_file(code: str) -> Dict[str, Any]:
    """Analyze .hu file code and return needed imports.
    
    Args:
        code: The .hu file source code
        
    Returns:
        Dictionary with 'namespaces' and 'types' that need to be injected
    """
    try:
        tree = ast.parse(code)
        analyzer = ActionNamespaceAnalyzer()
        analyzer.visit(tree)
        
        return {
            'namespaces': analyzer.used_namespaces,
            'types': analyzer.used_types
        }
    except SyntaxError as e:
        # If AST parsing fails, inject everything as fallback
        return {
            'namespaces': {'web', 'http'},  # Default safe set
            'types': {'HTML', 'JSON', 'CSV', 'XML', 'YAML', 'Markdown'}
        }


def create_execution_globals(used_namespaces: Set[str], used_types: Set[str]) -> Dict[str, Any]:
    """Create execution globals dictionary with only needed imports.
    
    Args:
        used_namespaces: Set of namespace names to inject (web, http, etc.)
        used_types: Set of type names to inject (HTML, JSON, etc.)
        
    Returns:
        Dictionary ready for exec() global namespace
    """
    execution_globals = {}
    
    # Inject validation types
    type_mapping = {
        'HTML': HTML,
        'JSON': JSON,
        'CSV': CSV,
        'XML': XML,
        'YAML': YAML,
        'Markdown': Markdown
    }
    
    for type_name in used_types:
        if type_name in type_mapping:
            execution_globals[type_name] = type_mapping[type_name]
    
    # Inject action namespaces
    if 'web' in used_namespaces:
        from lamia.actions import web
        execution_globals['web'] = web
    
    if 'http' in used_namespaces:
        from lamia.actions import http
        execution_globals['http'] = http
    
    # Future namespaces can be added here
    # if 'file' in used_namespaces:
    #     from lamia.actions import file
    #     execution_globals['file'] = file
    
    return execution_globals