"""
Lazy loader for .hu (human) files.

Scans for ``.hu`` files in the project directory, registers each by
filename stem as a callable, and checks for name collisions against
functions already registered by the hybrid (.lm / .py) lazy loader.
"""

import logging
from pathlib import Path
from typing import Dict, Set

from lamia.interpreter.human.parser import parse_hu_file
from lamia.interpreter.human.executor import HuCallable

logger = logging.getLogger(__name__)


class HumanFilesLazyLoader:
    """Catalogs and loads ``.hu`` files as callables."""

    def __init__(self) -> None:
        self.function_registry: Dict[str, str] = {}
        self._callables: Dict[str, HuCallable] = {}
        self._scanned_directories: Set[str] = set()

    def scan_directory(
        self,
        directory: str,
        existing_function_registry: Dict[str, str],
        recursive: bool = True,
    ) -> None:
        """Scan *directory* for ``.hu`` files and register them.

        Args:
            directory: Directory path to scan.
            existing_function_registry: Function names already registered
                by the hybrid / Python lazy loader.  Collisions are raised
                as errors.
            recursive: Whether to scan subdirectories.
        """
        base_path = Path(directory).expanduser().resolve()
        if not base_path.is_dir():
            logger.warning("Directory not found: %s", directory)
            return

        resolved = str(base_path)
        if resolved in self._scanned_directories:
            return
        self._scanned_directories.add(resolved)

        hu_files = base_path.rglob("*.hu") if recursive else base_path.glob("*.hu")

        for hu_file in sorted(hu_files):
            func_name = hu_file.stem
            resolved_path = str(hu_file.resolve())

            if func_name in existing_function_registry:
                raise ValueError(
                    f"Name collision: .hu file '{resolved_path}' defines "
                    f"function '{func_name}' which is already defined in "
                    f"'{existing_function_registry[func_name]}'. "
                    f"Rename the .hu file to resolve the conflict."
                )

            if func_name in self.function_registry:
                raise ValueError(
                    f"Name collision: .hu file '{resolved_path}' defines "
                    f"function '{func_name}' which is already defined by "
                    f"'{self.function_registry[func_name]}'. "
                    f"Each .hu filename must be unique."
                )

            self.function_registry[func_name] = resolved_path
            logger.debug("Registered .hu function '%s' from %s", func_name, resolved_path)

    def load_function(self, function_name: str, execution_globals: Dict[str, object]) -> bool:
        """Load a ``.hu`` callable into *execution_globals*.

        Returns ``True`` if the function was found and loaded.
        """
        if function_name not in self.function_registry:
            return False

        if function_name not in self._callables:
            hu_fn = parse_hu_file(self.function_registry[function_name])
            self._callables[function_name] = HuCallable(hu_fn)

        execution_globals[function_name] = self._callables[function_name]
        return True