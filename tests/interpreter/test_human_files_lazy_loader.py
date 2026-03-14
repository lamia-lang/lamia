"""Tests for the .hu human files lazy loader and collision enforcement."""

import pytest

from lamia.interpreter.human_files_lazy_loader import HumanFilesLazyLoader


class TestHumanFilesLazyLoader:

    def test_registers_hu_file_by_stem(self, tmp_path):
        (tmp_path / "greet.hu").write_text("Hello {name}!")

        loader = HumanFilesLazyLoader()
        loader.scan_directory(str(tmp_path), existing_function_registry={})

        assert "greet" in loader.function_registry

    def test_loads_hu_callable(self, tmp_path):
        (tmp_path / "greet.hu").write_text("Hello {name}!")

        loader = HumanFilesLazyLoader()
        loader.scan_directory(str(tmp_path), existing_function_registry={})

        globs: dict = {}
        assert loader.load_function("greet", globs) is True
        assert "greet" in globs
        assert callable(globs["greet"])
        assert globs["greet"](name="World") == "Hello World!"

    def test_collision_with_existing_lm_function_raises(self, tmp_path):
        (tmp_path / "report.hu").write_text("Generate a report")

        loader = HumanFilesLazyLoader()
        with pytest.raises(ValueError, match="Name collision"):
            loader.scan_directory(
                str(tmp_path),
                existing_function_registry={"report": "/some/file.lm"},
            )

    def test_collision_with_existing_py_function_raises(self, tmp_path):
        (tmp_path / "helper.hu").write_text("Help me")

        loader = HumanFilesLazyLoader()
        with pytest.raises(ValueError, match="Name collision"):
            loader.scan_directory(
                str(tmp_path),
                existing_function_registry={"helper": "/some/utils.py"},
            )

    def test_collision_between_two_hu_files_raises(self, tmp_path):
        sub1 = tmp_path / "a"
        sub2 = tmp_path / "b"
        sub1.mkdir()
        sub2.mkdir()
        (sub1 / "duplicate.hu").write_text("First")
        (sub2 / "duplicate.hu").write_text("Second")

        loader = HumanFilesLazyLoader()
        with pytest.raises(ValueError, match="unique"):
            loader.scan_directory(str(tmp_path), existing_function_registry={})

    def test_load_unknown_function_returns_false(self):
        loader = HumanFilesLazyLoader()
        assert loader.load_function("nonexistent", {}) is False

    def test_scan_nonexistent_directory(self):
        loader = HumanFilesLazyLoader()
        loader.scan_directory("/nonexistent/path", existing_function_registry={})
        assert len(loader.function_registry) == 0

    def test_scan_same_directory_twice_is_idempotent(self, tmp_path):
        (tmp_path / "test.hu").write_text("test")

        loader = HumanFilesLazyLoader()
        loader.scan_directory(str(tmp_path), existing_function_registry={})
        loader.scan_directory(str(tmp_path), existing_function_registry={})

        assert len(loader.function_registry) == 1