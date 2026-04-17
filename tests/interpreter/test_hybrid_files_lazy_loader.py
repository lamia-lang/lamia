"""Tests for lamia.interpreter.hybrid_files_lazy_loader."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from lamia.interpreter.hybrid_files_lazy_loader import (
    LazyLoader,
    create_lazy_loading_globals,
    EXCLUDED_DIRS,
    _is_excluded,
)


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
        assert len(loader.loaded_lm_files) == 0
        assert len(loader.function_registry) == 0

    def test_init_with_lamia_instance(self, mock_lamia_instance):
        loader = LazyLoader(lamia_instance=mock_lamia_instance)

        assert loader.lamia == mock_lamia_instance

    def test_init_with_custom_directory(self, temp_dir):
        loader = LazyLoader(search_directory=temp_dir)

        assert loader.search_directory == temp_dir


class TestLazyLoaderDirectoryScanning:

    def test_scan_directory_does_not_pick_up_python_files(self, temp_dir):
        py_file = Path(temp_dir) / "helpers.py"
        py_file.write_text("def helper_function(x): return x * 2\n")

        loader = LazyLoader()
        loader.scan_directory_for_functions(temp_dir, recursive=False)

        assert "helper_function" not in loader.function_registry

    def test_scan_directory_invalid_path(self):
        loader = LazyLoader()
        loader.scan_directory_for_functions("/nonexistent/path")

        assert len(loader.function_registry) == 0


class TestLazyLoaderLmCataloging:

    def test_catalog_lm_file_classes(self, temp_dir, mock_lamia_instance):
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


class TestDirectoryExclusion:

    def test_excluded_dirs_constant(self):
        assert "venv" in EXCLUDED_DIRS
        assert "node_modules" in EXCLUDED_DIRS
        assert "__pycache__" in EXCLUDED_DIRS
        assert "site-packages" in EXCLUDED_DIRS

    def test_is_excluded_returns_true_for_any_hidden_dir(self):
        base = Path("/project")
        assert _is_excluded(Path("/project/.venv/lib/models.lm"), base) is True
        assert _is_excluded(Path("/project/.git/hooks/pre.lm"), base) is True
        assert _is_excluded(Path("/project/.mypy_cache/x.lm"), base) is True
        assert _is_excluded(Path("/project/.anything/x.lm"), base) is True

    def test_is_excluded_returns_true_for_named_exclusions(self):
        base = Path("/project")
        assert _is_excluded(Path("/project/node_modules/pkg/tool.lm"), base) is True
        assert _is_excluded(Path("/project/sub/__pycache__/cache.lm"), base) is True

    def test_is_excluded_returns_false_for_user_dir(self):
        base = Path("/project")
        assert _is_excluded(Path("/project/src/models.lm"), base) is False
        assert _is_excluded(Path("/project/prompts/deep/nested.lm"), base) is False

    def test_scan_skips_excluded_directories(self, temp_dir):
        venv_dir = Path(temp_dir) / ".venv" / "lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "installed.lm").write_text("class Installed: pass\n")

        user_dir = Path(temp_dir) / "src"
        user_dir.mkdir()
        (user_dir / "mymodels.lm").write_text("class UserModel: pass\n")

        loader = LazyLoader(lamia_instance=Mock())

        with patch.object(loader, '_catalog_lm_file') as mock_catalog:
            loader.scan_directory_for_functions(temp_dir, recursive=True)

            cataloged_paths = [call.args[0] for call in mock_catalog.call_args_list]
            cataloged_names = [p.name for p in cataloged_paths]
            assert "mymodels.lm" in cataloged_names
            assert "installed.lm" not in cataloged_names

    def test_scan_non_recursive_ignores_exclusion(self, temp_dir):
        lm_file = Path(temp_dir) / "top.lm"
        lm_file.write_text("class TopLevel: pass\n")

        loader = LazyLoader(lamia_instance=Mock())

        with patch.object(loader, '_catalog_lm_file') as mock_catalog:
            loader.scan_directory_for_functions(temp_dir, recursive=False)

            cataloged_paths = [call.args[0] for call in mock_catalog.call_args_list]
            cataloged_names = [p.name for p in cataloged_paths]
            assert "top.lm" in cataloged_names


class TestLazyLoaderFunctionLoading:

    def test_load_function_file_not_found(self):
        loader = LazyLoader()

        execution_globals = {}
        success = loader.load_function_file("nonexistent_function", execution_globals)

        assert success is False


class TestLazyLoaderLazyScanning:

    def test_scan_for_function_cached_scan(self, temp_dir, sample_lm_file):
        loader = LazyLoader(search_directory=temp_dir)

        loader._scan_for_function("llm_helper")
        resolved_temp_dir = str(Path(temp_dir).resolve())
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

    def test_lazy_loading_skips_builtins(self, mock_lamia_instance):
        globals_dict = create_lazy_loading_globals(mock_lamia_instance)

        with pytest.raises(KeyError):
            _ = globals_dict["nonexistent_builtin"]