"""AST analyzer for detecting used action namespaces in .hu files."""

import ast
import asyncio
import logging
from typing import Set, Dict, Any, List, Optional

from pydantic import BaseModel, Field

from lamia.types import BaseType
import lamia.types as lamia_types
from lamia.async_bridge import EventLoopManager
from lamia.adapters.web.session_context import (
    create_session_factory, SessionSkipException,
    SessionLoginFailedError, validate_login_completion,
    pre_validate_session,
)
from lamia.interpreter.command_types import CommandType

logger = logging.getLogger(__name__)


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
        """Visit name references like potential validation types or command symbols.

        We don't hard-code type names here. We collect all identifiers that might
        be types and filter them later against dynamically discovered BaseType subclasses.
        """
        # Tentatively record as a type; we'll filter later against dynamic mapping
        self.used_types.add(node.id)
        # Check if it's one of our command types (needed for transformed code)
        if node.id in ['WebCommand', 'WebActionType', 'LLMCommand', 'FileCommand']:
            self.used_types.add(node.id)
        # Check if it's one of our session functions
        if node.id in ['session']:
            self.used_namespaces.add('session')
        # Add 'files' context manager to used namespaces
        if node.id in ['files']:
            self.used_namespaces.add('files')
        
        self.generic_visit(node)
    
    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Visit subscript access like HTML[Model], JSON[Schema].

        Record the base identifier; filtering happens later.
        """
        if isinstance(node.value, ast.Name):
            type_name = node.value.id
            self.used_types.add(type_name)
        
        self.generic_visit(node)


def extract_code_dependencies(code: str) -> Dict[str, Any]:
    """Extract namespaces and types used in .hu file code.

    Args:
        code: The .hu file source code

    Returns:
        Dictionary with 'namespaces' and 'types' that need to be injected
    """
    # Preprocess session return type syntax before AST parsing
    from lamia.interpreter.hybrid_syntax_parser import WithReturnTypePreprocessor
    preprocessor = WithReturnTypePreprocessor()
    processed_code, return_types = preprocessor.preprocess(code)

    tree = ast.parse(processed_code)
    analyzer = ActionNamespaceAnalyzer()
    analyzer.visit(tree)

    # Also analyze return types extracted by preprocessor (collect base type names)
    for return_type in return_types.values():
        if '[' in return_type and return_type.endswith(']'):
            base_type = return_type.split('[', 1)[0].strip()
            analyzer.used_types.add(base_type)
        else:
            analyzer.used_types.add(return_type.strip())

    # Build dynamic mapping of available validation types from lamia.types
    dynamic_type_mapping: Dict[str, type] = {}
    for name, attr in vars(lamia_types).items():
        if isinstance(attr, type) and attr is not BaseType and issubclass(attr, BaseType):
            dynamic_type_mapping[name] = attr

    # Filter used_types to only those that are valid dynamic types
    command_types = {'WebCommand', 'WebActionType', 'LLMCommand', 'FileCommand', 'FileActionType'}
    filtered_used_types = {t for t in analyzer.used_types if t in dynamic_type_mapping or t in command_types}

    # File(...) in return annotations means the generated code needs FileCommand + FileActionType
    if 'File' in analyzer.used_types:
        filtered_used_types.add('FileCommand')
        filtered_used_types.add('FileActionType')

    return {
        'namespaces': analyzer.used_namespaces,
        'types': filtered_used_types
    }


def create_execution_globals(used_namespaces: Set[str], used_types: Set[str], lamia_instance=None) -> Dict[str, Any]:
    """Create execution globals dictionary with only needed imports.
    
    Args:
        used_namespaces: Set of namespace names to inject (web, http, etc.)
        used_types: Set of type names to inject (HTML, JSON, etc.)
        lamia_instance: The Lamia instance to use for session validation (optional)
        
    Returns:
        Dictionary ready for exec() global namespace
    """
    execution_globals = {}
    
    # Inject validation types dynamically discovered from lamia.types
    dynamic_type_mapping: Dict[str, type] = {}
    for name, attr in vars(lamia_types).items():
        if isinstance(attr, type) and attr is not BaseType and issubclass(attr, BaseType):
            dynamic_type_mapping[name] = attr
    
    # Add command types for transformed code
    command_mapping: Dict[str, Any] = {
        'WebCommand': None,
        'WebActionType': None,
        'LLMCommand': None,
        'FileCommand': None,
        'FileActionType': None,
    }
    
    # Import command types only if needed
    for cmd_type in used_types:
        if cmd_type in command_mapping:
            if cmd_type == 'WebCommand':
                from lamia.interpreter.commands import WebCommand
                command_mapping['WebCommand'] = WebCommand
            elif cmd_type == 'WebActionType':
                from lamia.interpreter.commands import WebActionType
                command_mapping['WebActionType'] = WebActionType
            elif cmd_type == 'LLMCommand':
                from lamia.interpreter.commands import LLMCommand
                command_mapping['LLMCommand'] = LLMCommand
            elif cmd_type == 'FileCommand':
                from lamia.interpreter.commands import FileCommand
                command_mapping['FileCommand'] = FileCommand
            elif cmd_type == 'FileActionType':
                from lamia.interpreter.commands import FileActionType
                command_mapping['FileActionType'] = FileActionType
    
    for type_name in used_types:
        if type_name in dynamic_type_mapping:
            execution_globals[type_name] = dynamic_type_mapping[type_name]
        elif type_name in command_mapping and command_mapping[type_name] is not None:
            execution_globals[type_name] = command_mapping[type_name]
    
    # Inject action namespaces
    if 'web' in used_namespaces:
        from lamia.actions import web
        from lamia.interpreter.commands import WebCommand, WebActionType
        execution_globals['web'] = web
        execution_globals['WebCommand'] = WebCommand
        execution_globals['WebActionType'] = WebActionType
    
    if 'http' in used_namespaces:
        from lamia.actions import http
        execution_globals['http'] = http
        
    if 'file' in used_namespaces:
        from lamia.actions import file
        execution_globals['file'] = file
    
    if 'files' in used_namespaces:
        from lamia.engine.managers.llm.files_context_manager import files
        execution_globals['files'] = files
    
    # Always inject InputType for form automation
    from lamia.types import InputType
    execution_globals['InputType'] = InputType
    # Always inject pydantic and typing essentials for .hu model definitions
    execution_globals['BaseModel'] = BaseModel
    execution_globals['Field'] = Field
    execution_globals['List'] = List
    execution_globals['Optional'] = Optional
    execution_globals['Dict'] = Dict
    execution_globals['Any'] = Any
    
    if 'session' in used_namespaces:
        # Get web_manager from lamia instance for session validation
        web_manager = None
        if lamia_instance:
            try:
                engine = lamia_instance._engine
                web_manager = engine.manager_factory.get_manager(CommandType.WEB)
            except Exception as e:
                logger.warning(f"Could not get web manager: {e}")
        
        # Create session factory with web_manager injection
        session_factory = create_session_factory(web_manager)
        execution_globals['session'] = session_factory
        execution_globals['SessionSkipException'] = SessionSkipException
        execution_globals['SessionLoginFailedError'] = SessionLoginFailedError
        execution_globals['validate_login_completion'] = validate_login_completion
        execution_globals['pre_validate_session'] = pre_validate_session
        execution_globals['logger'] = logging.getLogger(__name__)
        execution_globals['asyncio'] = asyncio  # Needed for asyncio.run() in session validation
        
        # Add session validation support - uses existing validation logic
        """if lamia_instance:
            execution_globals['validate_session_result'] = create_session_validator_function(lamia_instance)
        else:
            def no_lamia_validator(return_type):
                raise Exception("Session validation requires a Lamia instance but none was provided")
            execution_globals['validate_session_result'] = no_lamia_validator"""
    
    # Future namespaces can be added here
    # if 'db' in used_namespaces:
    #     from lamia.actions import db
    #     execution_globals['db'] = db
    
    return execution_globals