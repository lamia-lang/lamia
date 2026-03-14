"""
Lazy loader for Python and .lm files.

This module provides efficient lazy loading of Python and .lm (hybrid)
files when functions are not found during script execution.  The companion
``human_files_lazy_loader`` handles ``.hu`` (pure human) files separately.
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
    """Handles lazy loading of Python and .lm files when functions are not found."""

    def __init__(self, lamia_instance=None, search_directory=None):
        self.lamia = lamia_instance
        self.search_directory = search_directory or "."
        self.loaded_modules: Set[str] = set()
        self.loaded_lm_files: Set[str] = set()
        self.function_registry: Dict[str, str] = {}
        self.scanned_directories: Set[str] = set()
        self._parser = HybridSyntaxParser() if lamia_instance else None

    def scan_directory_for_functions(self, directory: str, recursive: bool = True) -> None:
        """Scan *directory* for Python and .lm files and catalog their functions."""
        base_path = Path(directory).expanduser().resolve()
        if not base_path.is_dir():
            logger.warning(f"Directory not found: {directory}")
            return

        py_files = base_path.rglob('*.py') if recursive else base_path.glob('*.py')
        lm_files = base_path.rglob('*.lm') if recursive else base_path.glob('*.lm')

        for py_file in py_files:
            if py_file.name == '__init__.py':
                continue
            self._catalog_python_file(py_file, base_path)

        for lm_file in lm_files:
            self._catalog_lm_file(lm_file)

    def _catalog_python_file(self, py_file: Path, base_path: Path) -> None:
        """Catalog functions in a Python file."""
        try:
            resolved_path = py_file.resolve()

            with open(py_file, 'r') as file:
                node = ast.parse(file.read(), filename=str(py_file))

            for n in node.body:
                if isinstance(n, ast.FunctionDef):
                    func_name = n.name
                    if func_name in self.function_registry:
                        logger.warning(f"Function name conflict: '{func_name}' found in both '{self.function_registry[func_name]}' and '{resolved_path}'. Using first occurrence.")
                    else:
                        self.function_registry[func_name] = str(resolved_path)

        except Exception as e:
            logger.warning(f"Could not parse Python file {py_file}: {e}")

    def _catalog_lm_file(self, lm_file: Path) -> None:
        """Catalog functions in a .lm file."""
        try:
            resolved_path = lm_file.resolve()

            with open(lm_file, 'r') as file:
                content = file.read()

            if self._parser:
                parsed_info = self._parser.parse(content)
                for func_name in parsed_info.get('llm_functions', {}):
                    if func_name in self.function_registry:
                        logger.warning(f"Function name conflict: '{func_name}' found in both '{self.function_registry[func_name]}' and '{resolved_path}'. Using first occurrence.")
                    else:
                        self.function_registry[func_name] = str(resolved_path)

        except Exception as e:
            logger.warning(f"Could not parse .lm file {lm_file}: {e}")

    def _scan_for_function(self, function_name: str) -> bool:
        """Scan the search directory for a specific function on demand."""
        resolved_search_dir = str(Path(self.search_directory).expanduser().resolve())
        if resolved_search_dir not in self.scanned_directories:
            logger.info(f"Lazy loading: scanning directory '{self.search_directory}' for function '{function_name}'")
            self.scan_directory_for_functions(self.search_directory, recursive=True)
            self.scanned_directories.add(resolved_search_dir)
            logger.info(f"Lazy loading: found {len(self.function_registry)} functions: {list(self.function_registry.keys())}")

        return function_name in self.function_registry

    def load_function_file(self, function_name: str, execution_globals: Dict[str, Any]) -> bool:
        """Load the file containing the specified function."""
        if function_name not in self.function_registry:
            if not self._scan_for_function(function_name):
                return False

        file_path = self.function_registry[function_name]
        file_path_obj = Path(file_path)

        try:
            if file_path.endswith('.py'):
                return self._load_python_file(file_path_obj, execution_globals)
            elif file_path.endswith('.lm'):
                return self._load_lm_file(file_path_obj, execution_globals)
        except Exception as e:
            logger.error(f"Failed to load file {file_path} for function {function_name}: {e}")

        return False

    def _load_python_file(self, py_file: Path, execution_globals: Dict[str, Any]) -> bool:
        """Load a Python file into the execution globals."""
        resolved_path = py_file.resolve()
        if str(resolved_path) in self.loaded_modules:
            return True

        try:
            script_dir = str(py_file.parent)
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)

            relative_parts = py_file.with_suffix('').parts
            module_name = '.'.join(relative_parts[-2:]) if len(relative_parts) > 1 else relative_parts[-1]

            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                for name in dir(module):
                    obj = getattr(module, name)
                    if callable(obj) and not name.startswith('_'):
                        execution_globals[name] = obj

                self.loaded_modules.add(str(resolved_path))
                logger.info(f"Loaded Python file: {resolved_path}")
                return True

        except Exception as e:
            logger.error(f"Failed to load Python file {py_file}: {e}")

        return False

    def _load_lm_file(self, lm_file: Path, execution_globals: Dict[str, Any]) -> bool:
        """Load a .lm file into the execution globals."""
        resolved_path = lm_file.resolve()
        if str(resolved_path) in self.loaded_lm_files:
            return True

        if not self.lamia:
            logger.error("Cannot load .lm file: no Lamia instance available")
            return False

        try:
            from .hybrid_executor import HybridExecutor

            executor = HybridExecutor(self.lamia)

            temp_globals = execution_globals.copy()
            executor.execute_file(str(lm_file), globals_dict=temp_globals, enable_lazy_dependency_loading=True)

            for name, obj in temp_globals.items():
                if callable(obj) and not name.startswith('_'):
                    execution_globals[name] = obj

            self.loaded_lm_files.add(str(resolved_path))
            logger.info(f"Loaded .lm file: {resolved_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load .lm file {lm_file}: {e}")

        return False


def create_lazy_loading_globals(lamia_instance, base_globals: Optional[Dict[str, Any]] = None, file_path: Optional[str] = None) -> Dict[str, Any]:
    """Create a globals dictionary with lazy loading capabilities.

    Both the hybrid (.lm / .py) and human (.hu) lazy loaders are wired in.
    The hybrid loader scans first; then the human loader scans and checks
    for name collisions against the hybrid registry.
    """
    from .human_files_lazy_loader import HumanFilesLazyLoader

    if base_globals is None:
        base_globals = {}

    search_dir = str(Path(file_path).parent) if file_path else "."

    loader = LazyLoader(lamia_instance, search_dir)
    hu_loader = HumanFilesLazyLoader()

    class LazyGlobals(dict):
        """A dictionary that attempts lazy loading when keys are not found."""

        def __init__(self, base_dict, hybrid_loader, human_loader):
            super().__init__(base_dict)
            self._loader = hybrid_loader
            self._hu_loader = human_loader
            self._loading: Set[str] = set()
            self._hu_scanned = False

        def __getitem__(self, key):
            try:
                return super().__getitem__(key)
            except KeyError:
                logger.debug(f"Lazy loading: KeyError for '{key}', checking if should load")
                if (key not in self._loading and
                        key.isidentifier() and
                        not key.startswith('_') and
                        self._should_attempt_lazy_load(key)):
                    logger.debug(f"Lazy loading: conditions met for '{key}', attempting load")
                    self._loading.add(key)
                    try:
                        if self._loader.load_function_file(key, self):
                            if key in self:
                                return super().__getitem__(key)

                        self._ensure_hu_scanned()
                        if self._hu_loader.load_function(key, self):
                            if key in self:
                                return super().__getitem__(key)
                    finally:
                        self._loading.discard(key)
                else:
                    logger.debug(f"Lazy loading: skipping '%s' - conditions not met", key)

                raise

        def _ensure_hu_scanned(self):
            if not self._hu_scanned:
                self._hu_scanned = True
                self._loader._scan_for_function("")
                self._hu_loader.scan_directory(
                    self._loader.search_directory,
                    existing_function_registry=self._loader.function_registry,
                )

        def _should_attempt_lazy_load(self, key: str) -> bool:
            try:
                if hasattr(__builtins__, key):
                    return False
                if isinstance(__builtins__, dict) and key in __builtins__:
                    return False
            except Exception:
                pass

            if key[0].isupper():
                return len(key) > 2 and not key.isupper()

            return True

    return LazyGlobals(base_globals, loader, hu_loader)