"""Tests for lamia.interpreter.hybrid_files_lazy_loader."""

import os
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from lamia.interpreter.hybrid_files_lazy_loader import LazyLoader, create_lazy_loading_globals


@pytest.fixture
def temp_dir():
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_lamia_instance():
    lamia = Mock()
    lamia.run_async = AsyncMock(return_value="LLM response")
    return lamia


@pytest.fixture
def sample_python_file(temp_dir):
    py_content = '''
def helper_function(x):
    return x * 2

def another_helper(y):
    return y + 10
'''
    py_file = Path(temp_dir) / "helpers.py"
    py_file.write_text(py_content)
    return py_file


@pytest.fixture
def sample_lm_file(temp_dir):
    lm_content = '''
def llm_helper() -> str:
    result = lamia("Help me with something")
    return result
'''
    lm_file = Path(temp_dir) / "llm_helpers.lm"
    lm_file.write_text(lm_content)
    return lm_file


class TestLazyLoaderInitialization:

    def test_init_with_defaults(self):
        loader = LazyLoader()

        assert loader.lamia is None
        assert loader.search_directory == "."
        assert len(loader.loaded_modules) == 0
        assert len(loader.function_registry) == 0

    def test_init_with_lamia_instance(self, mock_lamia_instance):
        loader = LazyLoader(lamia_instance=mock_lamia_instance)

        assert loader.lamia == mock_lamia_instance

    def test_init_with_custom_directory(self, temp_dir):
        loader = LazyLoader(search_directory=temp_dir)

        assert loader.search_directory == temp_dir


class TestLazyLoaderDirectoryScanning:

    def test_scan_directory_python_files(self, temp_dir, sample_python_file):
        loader = LazyLoader()
        loader.scan_directory_for_functions(temp_dir, recursive=False)

        assert "helper_function" in loader.function_registry
        assert "another_helper" in loader.function_registry
        assert loader.function_registry["helper_function"] == str(sample_python_file.resolve())

    def test_scan_directory_recursive(self, temp_dir):
        subdir = Path(temp_dir) / "subdir"
        subdir.mkdir()
        py_file = subdir / "nested.py"
        py_file.write_text("def nested_function(): pass")

        loader = LazyLoader()
        loader.scan_directory_for_functions(temp_dir, recursive=True)

        assert "nested_function" in loader.function_registry

    def test_scan_directory_non_recursive(self, temp_dir):
        subdir = Path(temp_dir) / "subdir"
        subdir.mkdir()
        py_file = subdir / "nested.py"
        py_file.write_text("def nested_function(): pass")

        loader = LazyLoader()
        loader.scan_directory_for_functions(temp_dir, recursive=False)

        assert "nested_function" not in loader.function_registry

    def test_scan_directory_skips_init_files(self, temp_dir):
        init_file = Path(temp_dir) / "__init__.py"
        init_file.write_text("def init_function(): pass")

        loader = LazyLoader()
        loader.scan_directory_for_functions(temp_dir)

        assert "init_function" not in loader.function_registry

    def test_scan_directory_invalid_path(self):
        loader = LazyLoader()
        loader.scan_directory_for_functions("/nonexistent/path")

        assert len(loader.function_registry) == 0


class TestLazyLoaderFunctionCataloging:

    def test_catalog_python_file(self, temp_dir):
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
        assert "MyClass" in loader.function_registry
        assert "method" not in loader.function_registry

    def test_catalog_python_file_syntax_error(self, temp_dir):
        py_file = Path(temp_dir) / "bad.py"
        py_file.write_text("def bad_syntax(:")

        loader = LazyLoader()
        loader._catalog_python_file(py_file, Path(temp_dir))

        assert len(loader.function_registry) == 0

    def test_catalog_function_name_conflict(self, temp_dir):
        py_file1 = Path(temp_dir) / "file1.py"
        py_file1.write_text("def duplicate(): pass")

        py_file2 = Path(temp_dir) / "file2.py"
        py_file2.write_text("def duplicate(): pass")

        loader = LazyLoader()
        loader._catalog_python_file(py_file1, Path(temp_dir))
        loader._catalog_python_file(py_file2, Path(temp_dir))

        assert loader.function_registry["duplicate"] == str(py_file1.resolve())


class TestLazyLoaderClassCataloging:

    def test_catalog_classes_from_python_file(self, temp_dir):
        py_file = Path(temp_dir) / "models.py"
        py_file.write_text('''
class Task:
    pass

class Implementation:
    pass

def helper():
    pass
''')
        loader = LazyLoader()
        loader._catalog_python_file(py_file, Path(temp_dir))

        assert "Task" in loader.function_registry
        assert "Implementation" in loader.function_registry
        assert "helper" in loader.function_registry

    def test_catalog_classes_from_lm_file(self, temp_dir, mock_lamia_instance):
        lm_file = Path(temp_dir) / "models.lm"
        lm_file.write_text('''
class TaskBreakdown(BaseModel):
    tasks: list[str]
    risks: list[str]

class Implementation(BaseModel):
    files: list[str]
''')
        loader = LazyLoader(lamia_instance=mock_lamia_instance)
        loader._catalog_lm_file(lm_file)

        assert "TaskBreakdown" in loader.function_registry
        assert "Implementation" in loader.function_registry

    def test_load_class_from_python_file(self, temp_dir):
        py_file = Path(temp_dir) / "models.py"
        py_file.write_text('''
class MyModel:
    def __init__(self, name):
        self.name = name
''')
        loader = LazyLoader()
        loader.scan_directory_for_functions(temp_dir)

        execution_globals = {}
        success = loader.load_function_file("MyModel", execution_globals)

        assert success is True
        assert "MyModel" in execution_globals
        obj = execution_globals["MyModel"]("test")
        assert obj.name == "test"

    def test_lazy_load_class_on_missing_key(self, mock_lamia_instance, temp_dir):
        py_file = Path(temp_dir) / "models.py"
        py_file.write_text('''
class MyModel:
    def __init__(self, value):
        self.value = value
''')
        globals_dict = create_lazy_loading_globals(
            mock_lamia_instance,
            file_path=str(py_file),
        )

        result = globals_dict["MyModel"]
        assert callable(result)
        obj = result(42)
        assert obj.value == 42


class TestLazyLoaderFunctionLoading:

    def test_load_function_file_python(self, temp_dir, sample_python_file):
        loader = LazyLoader()
        loader.scan_directory_for_functions(temp_dir)

        execution_globals = {}
        success = loader.load_function_file("helper_function", execution_globals)

        assert success is True
        assert "helper_function" in execution_globals
        assert callable(execution_globals["helper_function"])

    def test_load_function_file_not_found(self):
        loader = LazyLoader()

        execution_globals = {}
        success = loader.load_function_file("nonexistent_function", execution_globals)

        assert success is False

    def test_load_function_file_already_loaded(self, temp_dir, sample_python_file):
        loader = LazyLoader()
        loader.scan_directory_for_functions(temp_dir)

        execution_globals = {}
        success1 = loader.load_function_file("helper_function", execution_globals)
        success2 = loader.load_function_file("helper_function", execution_globals)

        assert success1 is True
        assert success2 is True
        assert str(sample_python_file.resolve()) in loader.loaded_modules


class TestLazyLoaderLazyScanning:

    def test_scan_for_function_on_demand(self, temp_dir, sample_python_file):
        loader = LazyLoader(search_directory=temp_dir)
        assert len(loader.function_registry) == 0

        found = loader._scan_for_function("helper_function")

        assert found is True
        assert "helper_function" in loader.function_registry

    def test_scan_for_function_cached_scan(self, temp_dir, sample_python_file):
        loader = LazyLoader(search_directory=temp_dir)

        loader._scan_for_function("helper_function")
        resolved_temp_dir = str(Path(temp_dir).resolve())
        assert resolved_temp_dir in loader.scanned_directories

        initial_count = len(loader.function_registry)
        loader._scan_for_function("another_function")

        assert resolved_temp_dir in loader.scanned_directories


class TestLazyLoadingGlobals:

    def test_create_lazy_loading_globals(self, mock_lamia_instance):
        globals_dict = create_lazy_loading_globals(mock_lamia_instance)

        assert globals_dict is not None
        assert isinstance(globals_dict, dict)

    def test_lazy_loading_globals_with_base(self, mock_lamia_instance):
        base = {"existing_func": lambda: 42}
        globals_dict = create_lazy_loading_globals(mock_lamia_instance, base_globals=base)

        assert "existing_func" in globals_dict
        assert globals_dict["existing_func"]() == 42

    def test_lazy_loading_on_missing_key(self, mock_lamia_instance, temp_dir, sample_python_file):
        globals_dict = create_lazy_loading_globals(
            mock_lamia_instance,
            file_path=str(sample_python_file)
        )

        result = globals_dict["helper_function"]

        assert callable(result)

    def test_lazy_loading_skips_builtins(self, mock_lamia_instance):
        globals_dict = create_lazy_loading_globals(mock_lamia_instance)

        with pytest.raises(KeyError):
            _ = globals_dict["nonexistent_builtin"]
