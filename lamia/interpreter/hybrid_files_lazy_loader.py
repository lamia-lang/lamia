"""
Lazy loader for .lm (hybrid) files.

This module provides efficient lazy loading of ``.lm`` files when
functions/classes are not found during script execution.  Python (``.py``)
files are **not** scanned; users should rely on explicit ``import``
statements for Python code.  The companion ``human_files_lazy_loader``
handles ``.hu`` (pure human) files separately.
"""

import ast
import logging
from pathlib import Path
from typing import Dict, Set, Any, Optional
from .hybrid_syntax_parser import HybridSyntaxParser
from lamia.hooks.runner import HookRunner
from lamia.hooks.discovery import _extract_hooks_from_source

logger = logging.getLogger(__name__)


EXCLUDED_DIRS: Set[str] = {
    "node_modules",
    "__pycache__",
    "site-packages",
    "venv", "env",
    "dist", "build",
}


class LazyLoader:
    """Handles lazy loading of .lm files when functions are not found."""

    def __init__(self, lamia_instance=None, search_directory=None, hook_runner: Optional[HookRunner] = None):
        self.lamia = lamia_instance
        self.search_directory = search_directory or "."
        self.loaded_lm_files: Set[str] = set()
        self.function_registry: Dict[str, str] = {}
        self.scanned_directories: Set[str] = set()
        self._parser = HybridSyntaxParser() if lamia_instance else None
        self._hook_runner = hook_runner

    def scan_directory_for_functions(self, directory: str, recursive: bool = True) -> None:
        """Scan *directory* for .lm files and catalog their functions/classes."""
        base_path = Path(directory).expanduser().resolve()
        if not base_path.is_dir():
            logger.warning(f"Directory not found: {directory}")
            return

        if recursive:
            lm_files = (
                p for p in base_path.rglob('*.lm')
                if not _is_excluded(p, base_path)
            )
        else:
            lm_files = base_path.glob('*.lm')

        for lm_file in lm_files:
            self._catalog_lm_file(lm_file)

    def _catalog_lm_file(self, lm_file: Path) -> None:
        """Catalog functions and classes in a .lm file. Also registers hooks."""
        try:
            resolved_path = lm_file.resolve()

            with open(lm_file, 'r') as file:
                content = file.read()

            if self._parser:
                parsed_info = self._parser.parse(content)
                for func_name in parsed_info.get('llm_functions', {}):
                    if func_name not in self.function_registry:
                        self.function_registry[func_name] = str(resolved_path)

                # Preprocess hybrid syntax so ast.parse succeeds, then
                # catalog class and function definitions not already found
                # by the LLM detector (e.g. Pydantic models, helper funcs).
                try:
                    preprocessed, _ = self._parser._preprocessor.preprocess(content)
                    tree = ast.parse(preprocessed)
                    for n in tree.body:
                        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                            if n.name not in self.function_registry:
                                self.function_registry[n.name] = str(resolved_path)
                except SyntaxError:
                    pass

            # Discover and register hooks from this file
            if self._hook_runner:
                for hook in _extract_hooks_from_source(content, str(resolved_path)):
                    self._hook_runner.register(hook)

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
        """Load the .lm file containing the specified function."""
        if function_name not in self.function_registry:
            if not self._scan_for_function(function_name):
                return False

        file_path = self.function_registry[function_name]

        try:
            return self._load_lm_file(Path(file_path), execution_globals)
        except Exception as e:
            logger.error(f"Failed to load file {file_path} for function {function_name}: {e}")

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
            # Disable lazy loading for nested loads: execute_file replaces
            # globals_dict with a new LazyGlobals object when enabled, so
            # class/function definitions would go into the new dict while
            # temp_globals still points to the old one.
            executor.execute_file(str(lm_file), globals_dict=temp_globals)

            for name, obj in temp_globals.items():
                if callable(obj) and not name.startswith('_'):
                    execution_globals[name] = obj

            self.loaded_lm_files.add(str(resolved_path))
            logger.info(f"Loaded .lm file: {resolved_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load .lm file {lm_file}: {e}")

        return False


def _is_excluded(path: Path, base_path: Path) -> bool:
    """Return ``True`` if *path* is inside a hidden or excluded directory."""
    try:
        rel_parts = path.relative_to(base_path).parts
    except ValueError:
        return False
    return any(part.startswith(".") or part in EXCLUDED_DIRS for part in rel_parts)


def create_lazy_loading_globals(lamia_instance, base_globals: Optional[Dict[str, Any]] = None, file_path: Optional[str] = None) -> Dict[str, Any]:
    """Create a globals dictionary with lazy loading capabilities.

    Both the hybrid (``.lm``) and human (``.hu``) lazy loaders are wired
    in.  The hybrid loader scans first; then the human loader scans and
    checks for name collisions against the hybrid registry.

    Hooks are discovered during the same scan and registered into the
    engine's HookRunner (no separate discovery pass needed).
    """
    from .human_files_lazy_loader import HumanFilesLazyLoader

    if base_globals is None:
        base_globals = {}

    search_dir = str(Path(file_path).parent) if file_path else "."

    hook_runner = lamia_instance._engine.hook_runner if lamia_instance else None
    loader = LazyLoader(lamia_instance, search_dir, hook_runner=hook_runner)
    if hook_runner is not None:
        # Hooks must be available before the first LLM call; eager scan keeps
        # hook registration on the same .lm scanner path as normal symbols.
        loader.scan_directory_for_functions(search_dir, recursive=True)
        loader.scanned_directories.add(str(Path(search_dir).expanduser().resolve()))
    hu_loader = HumanFilesLazyLoader(lamia_instance)

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