"""
Hybrid syntax executor for executing transformed hybrid syntax code.

Handles execution of transformed hybrid syntax code with smart type resolution,
parameter handling, and integration with Lamia instances.
"""

import inspect
import os
import logging
from typing import Optional, Dict, Any
from .hybrid_syntax_parser import HybridSyntaxParser
from .hybrid_file_cache import HybridFileCache
from .ast_analyzer import extract_code_dependencies, create_execution_globals
from .detectors.llm_command_detector import (
    LLMFunctionInfo,
    SimpleReturnType,
    ParametricReturnType,
    FileWriteReturnType,
)
from lamia.adapters.web.session_context import SessionSkipException

logger = logging.getLogger(__name__)


class HybridExecutor:
    """Executes hybrid syntax code with smart type resolution."""
    
    def __init__(self, lamia_instance, lamia_var_name: str = 'lamia', cache_enabled: bool = True):
        self.lamia = lamia_instance
        self.lamia_var_name = lamia_var_name
        self.parser = HybridSyntaxParser(lamia_var_name)
        self.cache = HybridFileCache(cache_enabled=cache_enabled)
    
    def parse(self, source_code: str) -> Dict[str, Any]:
        """Parse hybrid syntax and return information about LLM commands."""
        return self.parser.parse(source_code)
    
    def transform(self, source_code: str) -> str:
        """Transform hybrid syntax code into executable Python."""
        transformed_code = self.parser.transform(source_code)
        
        # Add necessary imports to the transformed code
        imports = self._generate_imports(source_code)
        if imports:
            transformed_code = imports + "\n\n" + transformed_code
        
        return transformed_code
    
    def _generate_imports(self, source_code: str) -> str:
        """Generate import statements for types used in the code."""
        parsed_info = self.parse(source_code)
        
        # Collect all unique types used
        types_to_import = self._collect_types_from_parsed(parsed_info)
        
        # Generate import statements
        imports = []
        lamia_types = []
        
        for type_name in types_to_import:
            try:
                from lamia import types as lamia_types_module
                lamia_type = getattr(lamia_types_module, type_name, None)
                if lamia_type is not None:
                    lamia_types.append(type_name)
            except (ImportError, AttributeError):
                # Type might be user-defined or from another module
                pass
        
        if lamia_types:
            imports.append(f"from lamia.types import {', '.join(sorted(lamia_types))}")
        
        # Always import SmartTypeResolver for parameter resolution
        imports.append("from lamia.interpreter.hybrid_executor import SmartTypeResolver")
        
        return "\n".join(imports)
    
    async def execute(self, source_code: str, globals_dict: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute hybrid syntax code with AST-based selective injection."""
        # Transform the code
        transformed_code = self.transform(source_code)
        
        # Analyze source code to determine what needs to be injected
        analysis = extract_code_dependencies(source_code)
        
        # Prepare execution environment
        if globals_dict is None:
            globals_dict = {}
        
        # Add lamia instance to globals
        globals_dict[self.lamia_var_name] = self.lamia
        
        # Inject only the namespaces and types that are actually used
        ast_globals = create_execution_globals(analysis['namespaces'], analysis['types'], self.lamia)
        globals_dict.update(ast_globals)
        
        # Extract and import types from return annotations (legacy support)
        self._extract_and_import_types(source_code, globals_dict)
        
        # Execute the transformed code
        compiled_code = compile(transformed_code, '<hybrid_syntax>', 'exec')
        
        # Create a new local scope for execution
        local_dict = {}
        
        # Execute in async context
        exec(compiled_code, globals_dict, local_dict)
        
        return local_dict
    
    async def execute_function(self, func_name: str, source_code: str, *args, **kwargs) -> Any:
        """Execute a specific function from hybrid syntax code."""
        local_dict = await self.execute(source_code)
        
        if func_name not in local_dict:
            raise ValueError(f"Function '{func_name}' not found in executed code")
        
        func = local_dict[func_name]
        if not callable(func):
            raise ValueError(f"'{func_name}' is not a callable function")
        
        # Call the function
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    
    def _extract_and_import_types(self, source_code: str, globals_dict: dict):
        """Extract types from return annotations and import them dynamically."""
        # Parse to get LLM function info
        parsed_info = self.parse(source_code)

        # Collect all unique types used
        types_to_import = self._collect_types_from_parsed(parsed_info)

        # Import only the types that are actually used
        for type_name in types_to_import:
            if type_name not in globals_dict:  # Don't override existing globals
                try:
                    # Try importing from lamia.types first
                    from lamia import types as lamia_types
                    lamia_type = getattr(lamia_types, type_name, None)
                    if lamia_type is not None:
                        globals_dict[type_name] = lamia_type
                        logger.info(f"Imported type: {type_name}")
                except (ImportError, AttributeError) as e:
                    # Type might be user-defined or from another module
                    logger.warning(f"Could not import type {type_name}: {e}")

    @staticmethod
    def _collect_types_from_parsed(parsed_info: dict) -> set:
        """Collect all type names referenced in parsed LLM function return types."""
        types_to_import: set = set()
        for func_info in parsed_info.get('llm_functions', {}).values():
            rt = func_info.return_type if isinstance(func_info, LLMFunctionInfo) else None
            if rt is None:
                continue
            if isinstance(rt, ParametricReturnType):
                types_to_import.add(rt.base_type)
                types_to_import.add(rt.inner_type)
            elif isinstance(rt, SimpleReturnType):
                types_to_import.add(rt.base_type)
            elif isinstance(rt, FileWriteReturnType) and rt.inner_return_type is not None:
                inner = rt.inner_return_type
                if isinstance(inner, ParametricReturnType):
                    types_to_import.add(inner.base_type)
                    types_to_import.add(inner.inner_type)
                elif isinstance(inner, SimpleReturnType):
                    types_to_import.add(inner.base_type)
        return types_to_import
    
    def execute_file(self, file_path: str, globals_dict: Optional[Dict] = None, enable_lazy_dependency_loading: bool = False):
        """Execute a hybrid syntax file directly with AST-based selective injection."""
        # Read source code
        with open(file_path, 'r') as f:
            source_code = f.read()
        
        # Analyze source code to determine what needs to be injected
        analysis = extract_code_dependencies(source_code)
        
        # Transform the code
        transformed_code = self.transform(source_code)
        
        # Prepare execution environment
        if globals_dict is None:
            globals_dict = {}
        
        # Add lamia instance to globals
        globals_dict[self.lamia_var_name] = self.lamia
        
        # Inject only the namespaces and types that are actually used
        ast_globals = create_execution_globals(analysis['namespaces'], analysis['types'], self.lamia)
        globals_dict.update(ast_globals)
        
        # Extract and import types from return annotations (legacy support)
        self._extract_and_import_types(source_code, globals_dict)
        
        # Use lazy loading if enabled
        if enable_lazy_dependency_loading:
            from .hybrid_files_lazy_loader import create_lazy_loading_globals
            globals_dict = create_lazy_loading_globals(self.lamia, globals_dict, file_path)
        
        # Execute the transformed code directly
        compiled_code = compile(transformed_code, file_path, 'exec')
        try:
            exec(compiled_code, globals_dict)
        except NameError as e:
            if enable_lazy_dependency_loading:
                # NameError during execution - the lazy loading should have handled it
                # Re-raise with more context
                logger.error(f"Function not found even after lazy loading: {e}")
            raise
    


class SmartTypeResolver:
    """Handles smart type resolution for LamiaResult objects.
    
    Automatically extracts the appropriate value (result_type or result_text)
    based on context for parametric return types.
    """
    
    @staticmethod
    def resolve_for_assignment(lamia_result, target_type: str) -> Any:
        """Resolve LamiaResult for typed variable assignment.
        
        Args:
            lamia_result: The LamiaResult object
            target_type: The target type string (e.g., "WeatherModel")
            
        Returns:
            Appropriate value based on context
        """
        # For parametric types, extract structured data (result_type)
        if hasattr(lamia_result, 'result_type') and lamia_result.result_type is not None:
            return lamia_result.result_type
        
        # Fallback to raw text
        return lamia_result.result_text if hasattr(lamia_result, 'result_text') else lamia_result
    
    @staticmethod
    def resolve_for_string_context(lamia_result) -> str:
        """Resolve LamiaResult for string operations or file operations.
        
        Args:
            lamia_result: The LamiaResult object
            
        Returns:
            Raw text content
        """
        # For string/file operations, extract raw text (result_text)
        if hasattr(lamia_result, 'result_text'):
            return lamia_result.result_text
        
        # Fallback to string representation
        return str(lamia_result)
    
    @staticmethod
    def resolve_for_parameter(lamia_result, param_type: Optional[str] = None) -> Any:
        """Resolve LamiaResult when passed as function parameter.
        
        Args:
            lamia_result: The LamiaResult object
            param_type: The parameter type annotation (if available)
            
        Returns:
            Appropriate value based on parameter type
        """
        logger.info(f"SmartTypeResolver: resolving {type(lamia_result)} for param_type {param_type}")
        
        # If parameter has a specific type annotation, try to match it
        if param_type and hasattr(lamia_result, 'result_type') and lamia_result.result_type is not None:
            logger.info(f"SmartTypeResolver: returning result_type {type(lamia_result.result_type)}")
            return lamia_result.result_type
        
        # Default to raw text for untyped parameters
        result = lamia_result.result_text if hasattr(lamia_result, 'result_text') else lamia_result
        logger.info(f"SmartTypeResolver: returning fallback {type(result)}")
        return result


# Example usage patterns:
"""
# Create executor
executor = HybridExecutor(lamia_instance)

# Parse hybrid syntax code  
code = '''
def get_weather() -> HTML[WeatherModel]:
    "https://api.weather.com/current"

def generate_report(weather_data: WeatherModel, location: str):
    "Generate report for {location} using {weather_data}"
'''

generate_report(get_weather(), "NYC")
"""