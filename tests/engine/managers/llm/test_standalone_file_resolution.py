"""Tests for standalone {@...} file-reference resolution (no FilesContext)."""

import os
import pytest
from unittest.mock import patch, MagicMock

from lamia.engine.managers.llm.files_context_manager import (
    push_source_file,
    pop_source_file,
    get_current_source_file,
    resolve_standalone_file_references,
    read_file_content,
    _find_project_root,
    _has_path_components,
    _resolve_standalone_reference,
)
from lamia.errors import AmbiguousFileError, FileReferenceError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def project_tree(tmp_path):
    """Create a minimal project tree with config.yaml and sample files."""
    (tmp_path / "config.yaml").write_text("model: openai:gpt-4\n")
    (tmp_path / "data.json").write_text('{"key": "value"}')
    sub = tmp_path / "prompts"
    sub.mkdir()
    (sub / "greet.hu").write_text("Hello {name}!")
    (sub / "helper.txt").write_text("helper content")
    nested = tmp_path / "deep" / "nested"
    nested.mkdir(parents=True)
    (nested / "notes.md").write_text("# Notes")
    return tmp_path


# ---------------------------------------------------------------------------
# Source-file context stack
# ---------------------------------------------------------------------------

class TestSourceFileStack:

    def test_push_pop(self):
        push_source_file("/tmp/a.lm")
        assert get_current_source_file() is not None
        pop_source_file()
        assert get_current_source_file() is None

    def test_nested_push_pop(self):
        push_source_file("/tmp/outer.lm")
        push_source_file("/tmp/inner.hu")
        assert get_current_source_file().endswith("inner.hu")
        pop_source_file()
        assert get_current_source_file().endswith("outer.lm")
        pop_source_file()
        assert get_current_source_file() is None

    def test_pop_on_empty_is_safe(self):
        pop_source_file()


# ---------------------------------------------------------------------------
# _has_path_components
# ---------------------------------------------------------------------------

class TestHasPathComponents:

    def test_bare_filename(self):
        assert _has_path_components("data.json") is False

    def test_relative_prefix(self):
        assert _has_path_components("../data.json") is True

    def test_subdir(self):
        assert _has_path_components("sub/data.json") is True

    def test_dot_slash(self):
        assert _has_path_components("./data.json") is True


# ---------------------------------------------------------------------------
# _find_project_root
# ---------------------------------------------------------------------------

class TestFindProjectRoot:

    def test_finds_root_from_file(self, project_tree):
        hu_file = str(project_tree / "prompts" / "greet.hu")
        root = _find_project_root(hu_file)
        assert root == str(project_tree)

    def test_finds_root_from_nested_dir(self, project_tree):
        deep_file = str(project_tree / "deep" / "nested" / "notes.md")
        root = _find_project_root(deep_file)
        assert root == str(project_tree)

    def test_returns_none_when_no_config(self, tmp_path):
        some_file = tmp_path / "no_project" / "file.txt"
        some_file.parent.mkdir(parents=True)
        some_file.write_text("x")
        assert _find_project_root(str(some_file)) is None


# ---------------------------------------------------------------------------
# read_file_content (module-level)
# ---------------------------------------------------------------------------

class TestReadFileContent:

    def test_plain_text(self, project_tree):
        content = read_file_content(str(project_tree / "data.json"))
        assert '"key"' in content

    def test_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            read_file_content("/does/not/exist.txt")

    def test_pdf_extracted_via_pypdf2(self, tmp_path):
        pdf_file = tmp_path / "resume.pdf"
        pdf_file.write_bytes(b"%PDF-fake")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "John Doe\nAI Engineer"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("lamia.engine.managers.llm.files_context_manager.PyPDF2") as mock_pypdf2:
            mock_pypdf2.PdfReader.return_value = mock_reader
            content = read_file_content(str(pdf_file))

        assert "John Doe" in content
        assert "Page 1" in content

    def test_pdf_standalone_resolution(self, project_tree):
        """A .pdf reference is located via project search and content is extracted."""
        pdf_file = project_tree / "resume.pdf"
        pdf_file.write_bytes(b"%PDF-fake")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Jane Smith"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        source = str(project_tree / "prompts" / "greet.hu")
        with patch("lamia.engine.managers.llm.files_context_manager.PyPDF2") as mock_pypdf2:
            mock_pypdf2.PdfReader.return_value = mock_reader
            result = resolve_standalone_file_references("{@resume.pdf}", source)

        assert "Jane Smith" in result
        assert "--- resume.pdf ---" in result


# ---------------------------------------------------------------------------
# _resolve_standalone_reference
# ---------------------------------------------------------------------------

class TestResolveStandaloneReference:

    def test_absolute_path(self, project_tree):
        abs_path = str(project_tree / "data.json")
        resolved = _resolve_standalone_reference(abs_path, str(project_tree / "prompts" / "greet.hu"))
        assert resolved == abs_path

    def test_relative_path_from_source(self, project_tree):
        source = str(project_tree / "prompts" / "greet.hu")
        resolved = _resolve_standalone_reference("../data.json", source)
        assert resolved == str(project_tree / "data.json")

    def test_relative_same_dir(self, project_tree):
        source = str(project_tree / "prompts" / "greet.hu")
        resolved = _resolve_standalone_reference("./helper.txt", source)
        assert resolved == str(project_tree / "prompts" / "helper.txt")

    def test_bare_filename_uses_project_search(self, project_tree):
        source = str(project_tree / "prompts" / "greet.hu")
        resolved = _resolve_standalone_reference("data.json", source)
        assert resolved == str(project_tree / "data.json")

    def test_bare_filename_nested(self, project_tree):
        source = str(project_tree / "prompts" / "greet.hu")
        resolved = _resolve_standalone_reference("notes.md", source)
        assert os.path.basename(resolved) == "notes.md"

    def test_bare_filename_not_found(self, project_tree):
        source = str(project_tree / "prompts" / "greet.hu")
        with pytest.raises(FileReferenceError):
            _resolve_standalone_reference("nonexistent_file.xyz", source)

    def test_relative_not_found(self, project_tree):
        source = str(project_tree / "prompts" / "greet.hu")
        with pytest.raises(FileReferenceError):
            _resolve_standalone_reference("../nonexistent.txt", source)

    def test_no_project_root_raises(self, tmp_path):
        orphan = tmp_path / "orphan.hu"
        orphan.write_text("hi")
        with pytest.raises(FileReferenceError):
            _resolve_standalone_reference("something.txt", str(orphan))


# ---------------------------------------------------------------------------
# resolve_standalone_file_references (full prompt)
# ---------------------------------------------------------------------------

class TestResolveStandaloneFileReferences:

    def test_replaces_bare_filename(self, project_tree):
        source = str(project_tree / "prompts" / "greet.hu")
        prompt = "Use this config: {@data.json}"
        result = resolve_standalone_file_references(prompt, source)
        assert "{@data.json}" not in result
        assert '"key"' in result
        assert "--- data.json ---" in result

    def test_replaces_relative_path(self, project_tree):
        source = str(project_tree / "prompts" / "greet.hu")
        prompt = "Read {@../data.json}"
        result = resolve_standalone_file_references(prompt, source)
        assert '"key"' in result

    def test_no_refs_returns_unchanged(self, project_tree):
        source = str(project_tree / "prompts" / "greet.hu")
        prompt = "Just a normal prompt"
        assert resolve_standalone_file_references(prompt, source) == prompt

    def test_multiple_refs(self, project_tree):
        source = str(project_tree / "prompts" / "greet.hu")
        prompt = "A: {@data.json} B: {@helper.txt}"
        result = resolve_standalone_file_references(prompt, source)
        assert '"key"' in result
        assert "helper content" in result

    def test_not_found_raises(self, project_tree):
        source = str(project_tree / "prompts" / "greet.hu")
        prompt = "Load {@totally_missing.bin}"
        with pytest.raises(FileReferenceError):
            resolve_standalone_file_references(prompt, source)

    def test_ambiguous_raises(self, project_tree):
        """Two files with very similar names should raise AmbiguousFileError."""
        (project_tree / "report_v1.txt").write_text("v1")
        (project_tree / "report_v2.txt").write_text("v2")
        source = str(project_tree / "prompts" / "greet.hu")
        prompt = "Diff {@report}"
        with pytest.raises((AmbiguousFileError, FileReferenceError)):
            resolve_standalone_file_references(prompt, source)


# ---------------------------------------------------------------------------
# FilesContext takes priority over standalone
# ---------------------------------------------------------------------------

class TestPriorityOrder:

    def test_files_context_takes_priority(self, project_tree):
        """When FilesContext is active, HuCallable leaves {@...} intact."""
        from lamia.interpreter.human.parser import HuFunction
        from lamia.interpreter.human.executor import HuCallable

        fn = HuFunction(
            name="test",
            template="Check {@data.json}",
            params=frozenset(),
            source_path=str(project_tree / "prompts" / "greet.hu"),
        )
        c = HuCallable(fn)

        with patch("lamia.interpreter.human.executor.get_active_files_context") as mock_ctx:
            mock_ctx.return_value = MagicMock()
            result = c()
            assert "{@data.json}" in result

    def test_standalone_resolves_when_no_context(self, project_tree):
        """Without FilesContext, HuCallable resolves {@...} via standalone."""
        from lamia.interpreter.human.parser import HuFunction
        from lamia.interpreter.human.executor import HuCallable

        fn = HuFunction(
            name="test",
            template="Check {@data.json}",
            params=frozenset(),
            source_path=str(project_tree / "prompts" / "greet.hu"),
        )
        c = HuCallable(fn)

        with patch("lamia.interpreter.human.executor.get_active_files_context") as mock_ctx:
            mock_ctx.return_value = None
            result = c()
            assert "{@data.json}" not in result
            assert '"key"' in result