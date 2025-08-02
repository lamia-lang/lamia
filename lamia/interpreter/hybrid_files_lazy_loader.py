"""
Lazy loader for Python and .hu files.

This module provides efficient lazy loading of Python and .hu files
when functions are not found during .hu file execution.
"""

import sys
import ast
import importlib.util
import logging
from pathlib import Path
from typing import Dict, Set, Any, Optional
from .hybrid_syntax_parser import HybridSyntaxParser

logger = logging.getLogger(__name__)


class LazyLoader:
    """Handles lazy loading of Python and .hu files when functions are not found."""
    
    def __init__(self, lamia_instance=None):
        self.lamia = lamia_instance
        self.loaded_modules: Set[str] = set()
        self.loaded_hu_files: Set[str] = set()
        self.function_registry: Dict[str, str] = {}  # function_name -> file_path
        self._parser = HybridSyntaxParser() if lamia_instance else None
        
    def scan_directory_for_functions(self, directory: str, recursive: bool = True) -> None:
        """Scan directory for Python and .hu files and catalog their functions.
        
        Args:
            directory: Directory path to scan
            recursive: Whether to scan subdirectories recursively
        """
        base_path = Path(directory).expanduser().resolve()
        if not base_path.is_dir():
            logger.warning(f"Directory not found: {directory}")
            return
            
        # Choose glob strategy based on recursion flag
        py_files = base_path.rglob('*.py') if recursive else base_path.glob('*.py')
        hu_files = base_path.rglob('*.hu') if recursive else base_path.glob('*.hu')
        
        # Scan Python files
        for py_file in py_files:
            if py_file.name == '__init__.py':
                continue
            self._catalog_python_file(py_file, base_path)
            
        # Scan .hu files  
        for hu_file in hu_files:
            self._catalog_hu_file(hu_file)
    
    def _catalog_python_file(self, py_file: Path, base_path: Path) -> None:
        """Catalog functions in a Python file."""
        try:
            with open(py_file, 'r') as file:
                node = ast.parse(file.read(), filename=str(py_file))
                
            for n in node.body:
                if isinstance(n, ast.FunctionDef):
                    func_name = n.name
                    if func_name in self.function_registry:
                        logger.warning(f"Function name conflict: '{func_name}' found in both '{self.function_registry[func_name]}' and '{py_file}'. Using first occurrence.")
                    else:
                        self.function_registry[func_name] = str(py_file)
                        
        except Exception as e:
            logger.warning(f"Could not parse Python file {py_file}: {e}")
    
    def _catalog_hu_file(self, hu_file: Path) -> None:
        """Catalog functions in a .hu file."""
        try:
            with open(hu_file, 'r') as file:
                content = file.read()
                
            # Parse .hu file to extract function definitions
            if self._parser:
                parsed_info = self._parser.parse(content)
                for func_name in parsed_info.get('llm_functions', {}):
                    if func_name in self.function_registry:
                        logger.warning(f"Function name conflict: '{func_name}' found in both '{self.function_registry[func_name]}' and '{hu_file}'. Using first occurrence.")
                    else:
                        self.function_registry[func_name] = str(hu_file)
                        
        except Exception as e:
            logger.warning(f"Could not parse .hu file {hu_file}: {e}")
    
    def load_function_file(self, function_name: str, execution_globals: Dict[str, Any]) -> bool:
        """Load the file containing the specified function.
        
        Args:
            function_name: Name of the function to load
            execution_globals: Global namespace to load the function into
            
        Returns:
            True if function was found and loaded, False otherwise
        """
        if function_name not in self.function_registry:
            return False
            
        file_path = self.function_registry[function_name]
        file_path_obj = Path(file_path)
        
        try:
            if file_path.endswith('.py'):
                return self._load_python_file(file_path_obj, execution_globals)
            elif file_path.endswith('.hu'):
                return self._load_hu_file(file_path_obj, execution_globals)
        except Exception as e:
            logger.error(f"Failed to load file {file_path} for function {function_name}: {e}")
            
        return False
    
    def _load_python_file(self, py_file: Path, execution_globals: Dict[str, Any]) -> bool:
        """Load a Python file into the execution globals."""
        if str(py_file) in self.loaded_modules:
            return True  # Already loaded
            
        try:
            # Ensure the file's directory is on sys.path
            script_dir = str(py_file.parent)
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)
            
            # Derive module name
            relative_parts = py_file.with_suffix('').parts
            module_name = '.'.join(relative_parts[-2:]) if len(relative_parts) > 1 else relative_parts[-1]
            
            # Import the module
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                # Add all functions from the module to execution globals
                for name in dir(module):
                    obj = getattr(module, name)
                    if callable(obj) and not name.startswith('_'):
                        execution_globals[name] = obj
                        
                self.loaded_modules.add(str(py_file))
                logger.info(f"Loaded Python file: {py_file}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to load Python file {py_file}: {e}")
            
        return False
    
    def _load_hu_file(self, hu_file: Path, execution_globals: Dict[str, Any]) -> bool:
        """Load a .hu file into the execution globals."""
        if str(hu_file) in self.loaded_hu_files:
            return True  # Already loaded
            
        if not self.lamia:
            logger.error("Cannot load .hu file: no Lamia instance available")
            return False
            
        try:
            from .hybrid_executor import HybridExecutor
            
            # Create a hybrid executor for this file
            executor = HybridExecutor(self.lamia)
            
            # Read and execute the .hu file
            with open(hu_file, 'r') as f:
                source_code = f.read()
                
            # Execute the .hu file and merge results into execution globals
            local_dict = executor.execute(source_code, globals_dict=execution_globals.copy())
            
            # Add all functions from the executed .hu file to execution globals
            for name, obj in local_dict.items():
                if callable(obj) and not name.startswith('_'):
                    execution_globals[name] = obj
                    
            self.loaded_hu_files.add(str(hu_file))
            logger.info(f"Loaded .hu file: {hu_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load .hu file {hu_file}: {e}")
            
        return False


def create_lazy_loading_globals(lamia_instance, base_globals: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a globals dictionary with lazy loading capabilities.
    
    Args:
        lamia_instance: Lamia instance for .hu file execution
        base_globals: Base globals dictionary to extend
        
    Returns:
        Enhanced globals dictionary with lazy loading
    """
    if base_globals is None:
        base_globals = {}
        
    # Create lazy loader
    loader = LazyLoader(lamia_instance)
    
    # Scan current directory for functions
    loader.scan_directory_for_functions(".", recursive=True)
    
    class LazyGlobals(dict):
        """A dictionary that attempts lazy loading when keys are not found."""
        
        def __init__(self, base_dict, loader):
            super().__init__(base_dict)
            self._loader = loader
            self._loading = set()  # Prevent infinite recursion
            
        def __getitem__(self, key):
            try:
                return super().__getitem__(key)
            except KeyError:
                # Attempt lazy loading if the key looks like a function name
                if key not in self._loading and key.isidentifier():
                    self._loading.add(key)
                    try:
                        if self._loader.load_function_file(key, self):
                            # Try again after loading
                            if key in self:
                                return super().__getitem__(key)
                    finally:
                        self._loading.discard(key)
                        
                # If still not found, raise the original KeyError
                raise
    
    return LazyGlobals(base_globals, loader) 