"""Tests for lamia.interpreter.hybrid_executor."""

import os
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from lamia.interpreter.hybrid_file_cache import HybridFileCache
from lamia.interpreter.hybrid_files_lazy_loader import create_lazy_loading_globals
from lamia.interpreter.hybrid_executor import HybridExecutor


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


class TestHybridExecutorInitialization:

    def test_init_with_lamia_instance(self, mock_lamia_instance):
        executor = HybridExecutor(mock_lamia_instance)

        assert executor.lamia == mock_lamia_instance
        assert executor.lamia_var_name == 'lamia'
        assert executor.parser is not None
        assert executor.cache is not None

    def test_init_with_custom_var_name(self, mock_lamia_instance):
        executor = HybridExecutor(mock_lamia_instance, lamia_var_name='ai')

        assert executor.lamia_var_name == 'ai'

    def test_init_with_cache_disabled(self, mock_lamia_instance):
        executor = HybridExecutor(mock_lamia_instance, cache_enabled=False)

        assert executor.cache.cache_enabled is False


class TestHybridExecutorCodeTransformation:

    def test_parse_hybrid_code(self, mock_lamia_instance):
        code = '''
def greet(name: str) -> str:
    return "Hello, " + name

def generate_joke() -> str:
    response = lamia("Generate a funny joke")
    return response
'''
        executor = HybridExecutor(mock_lamia_instance)
        parsed_info = executor.parse(code)

        assert parsed_info is not None
        assert isinstance(parsed_info, dict)

    def test_transform_hybrid_code(self, mock_lamia_instance):
        executor = HybridExecutor(mock_lamia_instance)
        code = 'def test() -> str:\n    return lamia("hello")'

        transformed = executor.transform(code)

        assert transformed is not None
        assert isinstance(transformed, str)
        assert "import" in transformed or "from" in transformed

    def test_generate_imports_for_types(self, mock_lamia_instance):
        executor = HybridExecutor(mock_lamia_instance)
        code = 'def test() -> List[str]:\n    return lamia("generate list")'

        imports = executor._generate_imports(code)

        assert imports is not None
        assert "SmartTypeResolver" in imports


class TestHybridExecutorIntegration:

    def test_end_to_end_cache_workflow(self, temp_dir, mock_lamia_instance):
        cache = HybridFileCache(cache_enabled=True)
        executor = HybridExecutor(mock_lamia_instance)

        hybrid_file = os.path.join(temp_dir, "test.lm")
        with open(hybrid_file, 'w') as f:
            f.write('def test(): return "hello"')

        old_time = os.path.getmtime(hybrid_file) - 1
        os.utime(hybrid_file, (old_time, old_time))

        with open(hybrid_file, 'r') as f:
            transformed = executor.transform(f.read())

        cache_path = cache.get_cache_path(hybrid_file)
        cache.write_to_cache(cache_path, transformed)

        assert cache.is_cache_valid(hybrid_file, cache_path)
        cached_code = cache.read_from_cache(cache_path)
        assert cached_code == transformed

    def test_end_to_end_lazy_loading_workflow(self, temp_dir, mock_lamia_instance):
        helper_file = Path(temp_dir) / "helpers.py"
        helper_file.write_text("def my_helper(): return 42")

        globals_dict = create_lazy_loading_globals(
            mock_lamia_instance,
            file_path=str(Path(temp_dir) / "main.lm")
        )

        helper_func = globals_dict["my_helper"]

        assert callable(helper_func)
        assert helper_func() == 42

    def test_executor_with_cache_produces_stable_output(self, mock_lamia_instance):
        executor = HybridExecutor(mock_lamia_instance, cache_enabled=True)
        code = '''
def simple_test():
    return "test"
'''

        transformed1 = executor.transform(code)
        transformed2 = executor.transform(code)

        assert transformed1 == transformed2
