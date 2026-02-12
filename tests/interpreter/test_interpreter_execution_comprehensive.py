"""Comprehensive tests for Interpreter Execution: hybrid executor, file cache, and lazy loader."""

import pytest
import tempfile
import os
import shutil
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
from lamia.interpreter.hybrid_file_cache import HybridFileCache
from lamia.interpreter.hybrid_files_lazy_loader import LazyLoader, create_lazy_loading_globals
from lamia.interpreter.hybrid_executor import HybridExecutor


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_lamia_instance():
    """Create a mock Lamia instance."""
    lamia = Mock()
    lamia.run_async = AsyncMock(return_value="LLM response")
    return lamia


@pytest.fixture
def sample_hybrid_code():
    """Sample hybrid syntax code."""
    return '''
def greet(name: str) -> str:
    """Greet someone by name."""
    return "Hello, " + name

def generate_joke() -> str:
    """Generate a funny joke."""
    response = lamia("Generate a funny joke")
    return response
'''


@pytest.fixture
def sample_python_file(temp_dir):
    """Create a sample Python file in temp directory."""
    py_content = '''
def helper_function(x):
    """A helper function."""
    return x * 2

def another_helper(y):
    """Another helper function."""
    return y + 10
'''
    py_file = Path(temp_dir) / "helpers.py"
    py_file.write_text(py_content)
    return py_file


@pytest.fixture
def sample_hu_file(temp_dir):
    """Create a sample .hu file in temp directory."""
    hu_content = '''
def llm_helper() -> str:
    """An LLM-powered helper."""
    result = lamia("Help me with something")
    return result
'''
    hu_file = Path(temp_dir) / "llm_helpers.hu"
    hu_file.write_text(hu_content)
    return hu_file


# ============================================================================
# HYBRID FILE CACHE TESTS
# ============================================================================

class TestHybridFileCacheInitialization:
    """Test HybridFileCache initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        cache = HybridFileCache()

        assert cache.cache_enabled is True
        assert cache.cache_dir_name == '.lamia_cache'

    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        cache = HybridFileCache(cache_enabled=False, cache_dir_name='custom_cache')

        assert cache.cache_enabled is False
        assert cache.cache_dir_name == 'custom_cache'

    def test_init_cache_disabled(self):
        """Test initialization with cache disabled."""
        cache = HybridFileCache(cache_enabled=False)

        assert cache.cache_enabled is False


class TestHybridFileCachePathOperations:
    """Test HybridFileCache path operations."""

    def test_get_cache_path(self, temp_dir):
        """Test getting cache path for a hybrid file."""
        cache = HybridFileCache()
        hybrid_file = os.path.join(temp_dir, "script.hu")

        cache_path = cache.get_cache_path(hybrid_file)

        expected_path = os.path.join(temp_dir, ".lamia_cache", "script.py")
        assert cache_path == expected_path

    def test_get_cache_path_creates_directory(self, temp_dir):
        """Test that get_cache_path creates cache directory."""
        cache = HybridFileCache(cache_enabled=True)
        hybrid_file = os.path.join(temp_dir, "script.hu")

        cache_path = cache.get_cache_path(hybrid_file)

        cache_dir = os.path.dirname(cache_path)
        assert os.path.exists(cache_dir)

    def test_get_cache_path_disabled_no_directory(self, temp_dir):
        """Test that disabled cache doesn't create directory."""
        cache = HybridFileCache(cache_enabled=False)
        hybrid_file = os.path.join(temp_dir, "script.hu")

        cache_path = cache.get_cache_path(hybrid_file)

        # Path is returned but directory not created
        cache_dir = os.path.dirname(cache_path)
        assert not os.path.exists(cache_dir)

    def test_get_cache_path_with_subdirectory(self, temp_dir):
        """Test cache path for file in subdirectory."""
        cache = HybridFileCache()
        subdir = os.path.join(temp_dir, "subdir")
        os.makedirs(subdir)
        hybrid_file = os.path.join(subdir, "script.hu")

        cache_path = cache.get_cache_path(hybrid_file)

        expected_path = os.path.join(subdir, ".lamia_cache", "script.py")
        assert cache_path == expected_path


class TestHybridFileCacheValidation:
    """Test HybridFileCache validation."""

    def test_is_cache_valid_no_cache_file(self, temp_dir):
        """Test cache validity when cache file doesn't exist."""
        cache = HybridFileCache()
        hybrid_file = os.path.join(temp_dir, "script.hu")
        cache_path = cache.get_cache_path(hybrid_file)

        is_valid = cache.is_cache_valid(hybrid_file, cache_path)

        assert is_valid is False

    def test_is_cache_valid_cache_disabled(self, temp_dir):
        """Test cache validity when cache is disabled."""
        cache = HybridFileCache(cache_enabled=False)
        hybrid_file = os.path.join(temp_dir, "script.hu")
        cache_path = cache.get_cache_path(hybrid_file)

        is_valid = cache.is_cache_valid(hybrid_file, cache_path)

        assert is_valid is False

    def test_is_cache_valid_newer_cache(self, temp_dir):
        """Test cache validity when cache is newer than source."""
        import time
        cache = HybridFileCache()

        # Create source file
        hybrid_file = os.path.join(temp_dir, "script.hu")
        with open(hybrid_file, 'w') as f:
            f.write("def test(): pass")

        # Ensure different timestamps on fast filesystems
        time.sleep(0.05)

        # Create cache file (will be newer)
        cache_path = cache.get_cache_path(hybrid_file)
        with open(cache_path, 'w') as f:
            f.write("def test(): pass")

        is_valid = cache.is_cache_valid(hybrid_file, cache_path)

        assert is_valid is True

    def test_is_cache_valid_older_cache(self, temp_dir):
        """Test cache validity when source is newer than cache."""
        cache = HybridFileCache()

        # Create cache file first
        hybrid_file = os.path.join(temp_dir, "script.hu")
        cache_path = cache.get_cache_path(hybrid_file)
        with open(cache_path, 'w') as f:
            f.write("def test(): pass")

        # Create source file (will be newer)
        import time
        time.sleep(0.01)  # Ensure different timestamps
        with open(hybrid_file, 'w') as f:
            f.write("def test(): pass")

        is_valid = cache.is_cache_valid(hybrid_file, cache_path)

        assert is_valid is False


class TestHybridFileCacheReadWrite:
    """Test HybridFileCache read and write operations."""

    def test_write_to_cache(self, temp_dir):
        """Test writing transformed code to cache."""
        cache = HybridFileCache()
        cache_path = os.path.join(temp_dir, ".lamia_cache", "test.py")
        transformed_code = "def transformed(): return 42"

        success = cache.write_to_cache(cache_path, transformed_code)

        assert success is True
        assert os.path.exists(cache_path)
        with open(cache_path, 'r') as f:
            assert f.read() == transformed_code

    def test_write_to_cache_disabled(self, temp_dir):
        """Test writing to cache when disabled."""
        cache = HybridFileCache(cache_enabled=False)
        cache_path = os.path.join(temp_dir, "test.py")
        transformed_code = "def transformed(): return 42"

        success = cache.write_to_cache(cache_path, transformed_code)

        assert success is False
        assert not os.path.exists(cache_path)

    def test_read_from_cache(self, temp_dir):
        """Test reading transformed code from cache."""
        cache = HybridFileCache()
        cache_path = os.path.join(temp_dir, ".lamia_cache", "test.py")
        expected_code = "def cached(): return 42"

        # Write to cache first
        cache.write_to_cache(cache_path, expected_code)

        # Read from cache
        result = cache.read_from_cache(cache_path)

        assert result == expected_code

    def test_read_from_cache_disabled(self, temp_dir):
        """Test reading from cache when disabled."""
        cache = HybridFileCache(cache_enabled=False)
        cache_path = os.path.join(temp_dir, "test.py")

        result = cache.read_from_cache(cache_path)

        assert result is None

    def test_read_from_cache_missing_file(self, temp_dir):
        """Test reading from cache when file doesn't exist."""
        cache = HybridFileCache()
        cache_path = os.path.join(temp_dir, "nonexistent.py")

        result = cache.read_from_cache(cache_path)

        assert result is None


# ============================================================================
# LAZY LOADER TESTS
# ============================================================================

class TestLazyLoaderInitialization:
    """Test LazyLoader initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        loader = LazyLoader()

        assert loader.lamia is None
        assert loader.search_directory == "."
        assert len(loader.loaded_modules) == 0
        assert len(loader.function_registry) == 0

    def test_init_with_lamia_instance(self, mock_lamia_instance):
        """Test initialization with Lamia instance."""
        loader = LazyLoader(lamia_instance=mock_lamia_instance)

        assert loader.lamia == mock_lamia_instance

    def test_init_with_custom_directory(self, temp_dir):
        """Test initialization with custom search directory."""
        loader = LazyLoader(search_directory=temp_dir)

        assert loader.search_directory == temp_dir


class TestLazyLoaderDirectoryScanning:
    """Test LazyLoader directory scanning."""

    def test_scan_directory_python_files(self, temp_dir, sample_python_file):
        """Test scanning directory for Python files."""
        loader = LazyLoader()

        loader.scan_directory_for_functions(temp_dir, recursive=False)

        assert "helper_function" in loader.function_registry
        assert "another_helper" in loader.function_registry
        assert loader.function_registry["helper_function"] == str(sample_python_file.resolve())

    def test_scan_directory_recursive(self, temp_dir):
        """Test recursive directory scanning."""
        # Create subdirectory with Python file
        subdir = Path(temp_dir) / "subdir"
        subdir.mkdir()
        py_file = subdir / "nested.py"
        py_file.write_text("def nested_function(): pass")

        loader = LazyLoader()
        loader.scan_directory_for_functions(temp_dir, recursive=True)

        assert "nested_function" in loader.function_registry

    def test_scan_directory_non_recursive(self, temp_dir):
        """Test non-recursive directory scanning."""
        # Create subdirectory with Python file
        subdir = Path(temp_dir) / "subdir"
        subdir.mkdir()
        py_file = subdir / "nested.py"
        py_file.write_text("def nested_function(): pass")

        loader = LazyLoader()
        loader.scan_directory_for_functions(temp_dir, recursive=False)

        assert "nested_function" not in loader.function_registry

    def test_scan_directory_skips_init_files(self, temp_dir):
        """Test that __init__.py files are skipped."""
        init_file = Path(temp_dir) / "__init__.py"
        init_file.write_text("def init_function(): pass")

        loader = LazyLoader()
        loader.scan_directory_for_functions(temp_dir)

        assert "init_function" not in loader.function_registry

    def test_scan_directory_invalid_path(self):
        """Test scanning invalid directory path."""
        loader = LazyLoader()

        # Should not raise exception
        loader.scan_directory_for_functions("/nonexistent/path")

        assert len(loader.function_registry) == 0


class TestLazyLoaderFunctionCataloging:
    """Test LazyLoader function cataloging."""

    def test_catalog_python_file(self, temp_dir):
        """Test cataloging functions in Python file."""
        py_file = Path(temp_dir) / "test.py"
        py_file.write_text('''
def func1():
    pass

def func2():
    return 42

class MyClass:
    def method(self):
        pass
''')

        loader = LazyLoader()
        loader._catalog_python_file(py_file, Path(temp_dir))

        assert "func1" in loader.function_registry
        assert "func2" in loader.function_registry
        # Methods are not cataloged at module level
        assert "method" not in loader.function_registry

    def test_catalog_python_file_syntax_error(self, temp_dir):
        """Test cataloging Python file with syntax error."""
        py_file = Path(temp_dir) / "bad.py"
        py_file.write_text("def bad_syntax(:")  # Invalid syntax

        loader = LazyLoader()

        # Should not raise exception
        loader._catalog_python_file(py_file, Path(temp_dir))

        assert len(loader.function_registry) == 0

    def test_catalog_function_name_conflict(self, temp_dir):
        """Test handling function name conflicts."""
        py_file1 = Path(temp_dir) / "file1.py"
        py_file1.write_text("def duplicate(): pass")

        py_file2 = Path(temp_dir) / "file2.py"
        py_file2.write_text("def duplicate(): pass")

        loader = LazyLoader()
        loader._catalog_python_file(py_file1, Path(temp_dir))
        loader._catalog_python_file(py_file2, Path(temp_dir))

        # First occurrence wins (paths are resolved internally for consistency)
        assert loader.function_registry["duplicate"] == str(py_file1.resolve())


class TestLazyLoaderFunctionLoading:
    """Test LazyLoader function loading."""

    def test_load_function_file_python(self, temp_dir, sample_python_file):
        """Test loading Python file containing a function."""
        loader = LazyLoader()
        loader.scan_directory_for_functions(temp_dir)

        execution_globals = {}
        success = loader.load_function_file("helper_function", execution_globals)

        assert success is True
        assert "helper_function" in execution_globals
        assert callable(execution_globals["helper_function"])

    def test_load_function_file_not_found(self):
        """Test loading non-existent function."""
        loader = LazyLoader()

        execution_globals = {}
        success = loader.load_function_file("nonexistent_function", execution_globals)

        assert success is False

    def test_load_function_file_already_loaded(self, temp_dir, sample_python_file):
        """Test loading already loaded file."""
        loader = LazyLoader()
        loader.scan_directory_for_functions(temp_dir)

        execution_globals = {}
        success1 = loader.load_function_file("helper_function", execution_globals)
        success2 = loader.load_function_file("helper_function", execution_globals)

        assert success1 is True
        assert success2 is True
        # File should only be in loaded_modules once (paths are resolved internally)
        assert str(sample_python_file.resolve()) in loader.loaded_modules


class TestLazyLoaderLazyScanning:
    """Test LazyLoader on-demand scanning."""

    def test_scan_for_function_on_demand(self, temp_dir, sample_python_file):
        """Test that functions are found via on-demand scanning."""
        loader = LazyLoader(search_directory=temp_dir)

        # Don't scan upfront
        assert len(loader.function_registry) == 0

        # Try to find function - should trigger scan
        found = loader._scan_for_function("helper_function")

        assert found is True
        assert "helper_function" in loader.function_registry

    def test_scan_for_function_cached_scan(self, temp_dir, sample_python_file):
        """Test that directory is only scanned once."""
        loader = LazyLoader(search_directory=temp_dir)

        # First scan
        loader._scan_for_function("helper_function")
        # Paths are resolved internally for consistency across platforms (e.g., /var -> /private/var on macOS)
        resolved_temp_dir = str(Path(temp_dir).resolve())
        assert resolved_temp_dir in loader.scanned_directories

        # Second scan should use cache
        initial_count = len(loader.function_registry)
        loader._scan_for_function("another_function")

        # Should not rescan - registry size same
        assert resolved_temp_dir in loader.scanned_directories


# ============================================================================
# LAZY LOADING GLOBALS TESTS
# ============================================================================

class TestLazyLoadingGlobals:
    """Test lazy loading globals dictionary."""

    def test_create_lazy_loading_globals(self, mock_lamia_instance):
        """Test creating lazy loading globals."""
        globals_dict = create_lazy_loading_globals(mock_lamia_instance)

        assert globals_dict is not None
        assert isinstance(globals_dict, dict)

    def test_lazy_loading_globals_with_base(self, mock_lamia_instance):
        """Test creating lazy globals with base dictionary."""
        base = {"existing_func": lambda: 42}
        globals_dict = create_lazy_loading_globals(mock_lamia_instance, base_globals=base)

        assert "existing_func" in globals_dict
        assert globals_dict["existing_func"]() == 42

    def test_lazy_loading_on_missing_key(self, mock_lamia_instance, temp_dir, sample_python_file):
        """Test lazy loading when key is not found."""
        globals_dict = create_lazy_loading_globals(
            mock_lamia_instance,
            file_path=str(sample_python_file)
        )

        # Access function that should be lazy loaded
        result = globals_dict["helper_function"]

        assert callable(result)

    def test_lazy_loading_skips_builtins(self, mock_lamia_instance):
        """Test that lazy loading skips built-in functions."""
        globals_dict = create_lazy_loading_globals(mock_lamia_instance)

        with pytest.raises(KeyError):
            # Should not try to lazy load built-ins
            _ = globals_dict["nonexistent_builtin"]


# ============================================================================
# HYBRID EXECUTOR TESTS
# ============================================================================

class TestHybridExecutorInitialization:
    """Test HybridExecutor initialization."""

    def test_init_with_lamia_instance(self, mock_lamia_instance):
        """Test initialization with Lamia instance."""
        executor = HybridExecutor(mock_lamia_instance)

        assert executor.lamia == mock_lamia_instance
        assert executor.lamia_var_name == 'lamia'
        assert executor.parser is not None
        assert executor.cache is not None

    def test_init_with_custom_var_name(self, mock_lamia_instance):
        """Test initialization with custom Lamia variable name."""
        executor = HybridExecutor(mock_lamia_instance, lamia_var_name='ai')

        assert executor.lamia_var_name == 'ai'

    def test_init_with_cache_disabled(self, mock_lamia_instance):
        """Test initialization with cache disabled."""
        executor = HybridExecutor(mock_lamia_instance, cache_enabled=False)

        assert executor.cache.cache_enabled is False


class TestHybridExecutorCodeTransformation:
    """Test HybridExecutor code transformation."""

    def test_parse_hybrid_code(self, mock_lamia_instance, sample_hybrid_code):
        """Test parsing hybrid syntax code."""
        executor = HybridExecutor(mock_lamia_instance)

        parsed_info = executor.parse(sample_hybrid_code)

        assert parsed_info is not None
        assert isinstance(parsed_info, dict)

    def test_transform_hybrid_code(self, mock_lamia_instance):
        """Test transforming hybrid syntax to Python."""
        executor = HybridExecutor(mock_lamia_instance)
        code = 'def test() -> str:\n    return lamia("hello")'

        transformed = executor.transform(code)

        assert transformed is not None
        assert isinstance(transformed, str)
        # Should contain imports
        assert "import" in transformed or "from" in transformed

    def test_generate_imports_for_types(self, mock_lamia_instance):
        """Test generating imports for used types."""
        executor = HybridExecutor(mock_lamia_instance)
        code = 'def test() -> List[str]:\n    return lamia("generate list")'

        imports = executor._generate_imports(code)

        assert imports is not None
        # Should include SmartTypeResolver
        assert "SmartTypeResolver" in imports


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestInterpreterExecutionIntegration:
    """Integration tests for interpreter execution system."""

    def test_end_to_end_cache_workflow(self, temp_dir, mock_lamia_instance):
        """Test end-to-end caching workflow."""
        cache = HybridFileCache(cache_enabled=True)
        executor = HybridExecutor(mock_lamia_instance)

        # Create hybrid file
        hybrid_file = os.path.join(temp_dir, "test.hu")
        with open(hybrid_file, 'w') as f:
            f.write('def test(): return "hello"')

        # Transform and cache
        with open(hybrid_file, 'r') as f:
            transformed = executor.transform(f.read())

        cache_path = cache.get_cache_path(hybrid_file)
        cache.write_to_cache(cache_path, transformed)

        # Verify cache works
        assert cache.is_cache_valid(hybrid_file, cache_path)
        cached_code = cache.read_from_cache(cache_path)
        assert cached_code == transformed

    def test_end_to_end_lazy_loading_workflow(self, temp_dir, mock_lamia_instance):
        """Test end-to-end lazy loading workflow."""
        # Create helper file
        helper_file = Path(temp_dir) / "helpers.py"
        helper_file.write_text("def my_helper(): return 42")

        # Create lazy loading globals
        globals_dict = create_lazy_loading_globals(
            mock_lamia_instance,
            file_path=str(Path(temp_dir) / "main.hu")
        )

        # Access helper function (should lazy load)
        helper_func = globals_dict["my_helper"]

        assert callable(helper_func)
        assert helper_func() == 42

    def test_executor_with_cache_integration(self, mock_lamia_instance, temp_dir):
        """Test executor integration with caching."""
        executor = HybridExecutor(mock_lamia_instance, cache_enabled=True)

        code = '''
def simple_test():
    return "test"
'''

        # Transform code (should use cache)
        transformed1 = executor.transform(code)
        transformed2 = executor.transform(code)

        # Both should produce same result
        assert transformed1 == transformed2
