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
    _has_path_components,
    _resolve_standalone_reference,
    FilesContext,
)
from lamia.project import find_project_root
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
# find_project_root
# ---------------------------------------------------------------------------

class TestFindProjectRoot:

    def test_finds_root_from_file(self, project_tree):
        hu_file = str(project_tree / "prompts" / "greet.hu")
        root = find_project_root(hu_file)
        assert root == str(project_tree)

    def test_finds_root_from_nested_dir(self, project_tree):
        deep_file = str(project_tree / "deep" / "nested" / "notes.md")
        root = find_project_root(deep_file)
        assert root == str(project_tree)

    def test_returns_none_when_no_config(self, tmp_path):
        some_file = tmp_path / "no_project" / "file.txt"
        some_file.parent.mkdir(parents=True)
        some_file.write_text("x")
        assert find_project_root(str(some_file)) is None


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
        """A .pdf reference in the source dir is resolved and extracted."""
        pdf_file = project_tree / "prompts" / "resume.pdf"
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

    def test_bare_filename_resolves_relative_to_source_dir(self, project_tree):
        (project_tree / "prompts" / "data.json").write_text('{"local": true}')
        source = str(project_tree / "prompts" / "greet.hu")
        resolved = _resolve_standalone_reference("data.json", source)
        assert resolved == str(project_tree / "prompts" / "data.json")

    def test_bare_filename_not_in_source_dir_raises(self, project_tree):
        source = str(project_tree / "prompts" / "greet.hu")
        with pytest.raises(FileReferenceError):
            _resolve_standalone_reference("notes.md", source)

    def test_bare_filename_not_found(self, project_tree):
        source = str(project_tree / "prompts" / "greet.hu")
        with pytest.raises(FileReferenceError):
            _resolve_standalone_reference("nonexistent_file.xyz", source)

    def test_relative_not_found(self, project_tree):
        source = str(project_tree / "prompts" / "greet.hu")
        with pytest.raises(FileReferenceError):
            _resolve_standalone_reference("../nonexistent.txt", source)

    def test_no_project_root_still_raises(self, tmp_path):
        orphan = tmp_path / "orphan.hu"
        orphan.write_text("hi")
        with pytest.raises(FileReferenceError):
            _resolve_standalone_reference("something.txt", str(orphan))


# ---------------------------------------------------------------------------
# resolve_standalone_file_references (full prompt)
# ---------------------------------------------------------------------------

class TestResolveStandaloneFileReferences:

    def test_replaces_bare_filename_from_same_dir(self, project_tree):
        (project_tree / "prompts" / "data.json").write_text('{"local": true}')
        source = str(project_tree / "prompts" / "greet.hu")
        prompt = "Use this config: {@data.json}"
        result = resolve_standalone_file_references(prompt, source)
        assert "{@data.json}" not in result
        assert '"local"' in result
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
        (project_tree / "prompts" / "data.json").write_text('{"local": true}')
        source = str(project_tree / "prompts" / "greet.hu")
        prompt = "A: {@data.json} B: {@helper.txt}"
        result = resolve_standalone_file_references(prompt, source)
        assert '"local"' in result
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

        (project_tree / "prompts" / "data.json").write_text('{"key": "local"}')
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
            assert '"local"' in result


class TestFilesContextErrorMessages:
    def test_file_reference_error_message_has_plain_filename(self):
        err = FileReferenceError("memos.txt", [])
        assert "File 'memos.txt' not found in files context." in str(err)
        assert "{memos.txt}" not in str(err)

    def test_empty_files_context_shows_paths_hint(self):
        ctx = FilesContext("~/Dcouments")
        ctx.__enter__()
        try:
            with pytest.raises(FileReferenceError) as exc:
                ctx.resolve_file_reference("memos.txt")
            msg = str(exc.value)
            assert "File 'memos.txt' not found in files context." in msg
            assert "indexed 0 files" in msg
            assert "~/Dcouments" in msg
        finally:
            ctx.__exit__(None, None, None)

    def test_nonexistent_path_shows_does_not_exist(self):
        ctx = FilesContext("~/Document", "~/projects/linkedin/", "./config/")
        ctx.__enter__()
        try:
            with pytest.raises(FileReferenceError) as exc:
                ctx.resolve_file_reference("credentials.json")
            msg = str(exc.value)
            assert "~/Document" in msg
            assert "~/projects/linkedin/" in msg
            assert "./config/" in msg
            assert "Does not exist" in msg
        finally:
            ctx.__exit__(None, None, None)

    def test_captured_context_preserves_original_paths(self, tmp_path):
        from lamia.engine.managers.llm.files_context_manager import CapturedFilesContext
        f = tmp_path / "data.txt"
        f.write_text("hello")

        captured = CapturedFilesContext([str(f)], ("~/Documents/", "./config/"))
        ctx = captured.__enter__()
        try:
            assert ctx.paths == ("~/Documents/", "./config/")
        finally:
            captured.__exit__(None, None, None)


class TestExactMatchResolution:
    """Exact suffix matching — no fuzzy file loading."""

    def test_exact_basename_single_match(self, tmp_path):
        """Single file with matching basename resolves correctly."""
        f = tmp_path / "resume.pdf"
        f.write_text("my resume")

        with FilesContext(str(tmp_path)) as ctx:
            result = ctx.resolve_file_reference("resume.pdf")
            assert result == str(f)

    def test_exact_subpath_match(self, tmp_path):
        """User can provide a partial path suffix to resolve."""
        (tmp_path / "docs").mkdir()
        f = tmp_path / "docs" / "resume.pdf"
        f.write_text("my resume")

        with FilesContext(str(tmp_path)) as ctx:
            result = ctx.resolve_file_reference("docs/resume.pdf")
            assert result == str(f)

    def test_no_fuzzy_loading_of_wrong_file(self, tmp_path):
        """resume.pdf must NOT resolve to README.md via fuzzy matching."""
        (tmp_path / "README.md").write_text("readme")
        (tmp_path / "sum.py").write_text("x=1")

        with FilesContext(str(tmp_path)) as ctx:
            with pytest.raises(FileReferenceError) as exc:
                ctx.resolve_file_reference("resume.pdf")
            msg = str(exc.value)
            assert "not found" in msg.lower()

    def test_not_found_suggests_similar_names(self, tmp_path):
        """When file not found, 'Did you mean?' uses difflib, not fuzzy load."""
        (tmp_path / "credentials.json").write_text("{}")

        with FilesContext(str(tmp_path)) as ctx:
            with pytest.raises(FileReferenceError) as exc:
                ctx.resolve_file_reference("credential.json")
            msg = str(exc.value)
            assert "Did you mean" in msg
            assert "credentials.json" in msg

    def test_absolute_path_still_works(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b")

        with FilesContext(str(tmp_path)) as ctx:
            result = ctx.resolve_file_reference(str(f))
            assert result == str(f)

    def test_case_insensitive_not_used(self, tmp_path):
        """Exact matching is case-sensitive on case-sensitive filesystems."""
        (tmp_path / "Data.csv").write_text("a,b")

        with FilesContext(str(tmp_path)) as ctx:
            with pytest.raises(FileReferenceError):
                ctx.resolve_file_reference("data.csv")


class TestDuplicateFileDetection:
    """When the same filename exists in multiple directories."""

    def test_same_name_two_dirs_raises_ambiguous(self, tmp_path):
        """resume.pdf in two different dirs → AmbiguousFileError."""
        dir_a = tmp_path / "docs"
        dir_b = tmp_path / "archive"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "resume.pdf").write_text("v1")
        (dir_b / "resume.pdf").write_text("v2")

        with FilesContext(str(tmp_path)) as ctx:
            with pytest.raises(AmbiguousFileError) as exc:
                ctx.resolve_file_reference("resume.pdf")
            msg = str(exc.value)
            assert "docs/resume.pdf" in msg
            assert "archive/resume.pdf" in msg

    def test_disambiguate_with_subpath(self, tmp_path):
        """User resolves ambiguity by adding parent dir to the reference."""
        dir_a = tmp_path / "docs"
        dir_b = tmp_path / "archive"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "resume.pdf").write_text("v1")
        (dir_b / "resume.pdf").write_text("v2")

        with FilesContext(str(tmp_path)) as ctx:
            result = ctx.resolve_file_reference("docs/resume.pdf")
            assert result == str(dir_a / "resume.pdf")

            result2 = ctx.resolve_file_reference("archive/resume.pdf")
            assert result2 == str(dir_b / "resume.pdf")

    def test_same_name_across_separate_roots(self, tmp_path):
        """Duplicate across two separate root dirs passed to files()."""
        root_a = tmp_path / "root_a"
        root_b = tmp_path / "root_b"
        root_a.mkdir()
        root_b.mkdir()
        (root_a / "config.yaml").write_text("a: 1")
        (root_b / "config.yaml").write_text("b: 2")

        with FilesContext(str(root_a), str(root_b)) as ctx:
            with pytest.raises(AmbiguousFileError) as exc:
                ctx.resolve_file_reference("config.yaml")
            msg = str(exc.value)
            assert "root_a/config.yaml" in msg
            assert "root_b/config.yaml" in msg

    def test_disambiguate_across_roots_with_folder_name(self, tmp_path):
        """Provide enough path to uniquely identify across roots."""
        root_a = tmp_path / "root_a"
        root_b = tmp_path / "root_b"
        root_a.mkdir()
        root_b.mkdir()
        (root_a / "config.yaml").write_text("a: 1")
        (root_b / "config.yaml").write_text("b: 2")

        with FilesContext(str(root_a), str(root_b)) as ctx:
            result = ctx.resolve_file_reference("root_a/config.yaml")
            assert result == str(root_a / "config.yaml")

    def test_deeper_nesting_minimal_path(self, tmp_path):
        """a/b/resume.pdf vs a/b/c/resume.pdf — minimal unique paths differ."""
        (tmp_path / "a" / "b").mkdir(parents=True)
        (tmp_path / "a" / "b" / "c").mkdir()
        (tmp_path / "a" / "b" / "resume.pdf").write_text("shallow")
        (tmp_path / "a" / "b" / "c" / "resume.pdf").write_text("deep")

        with FilesContext(str(tmp_path)) as ctx:
            with pytest.raises(AmbiguousFileError) as exc:
                ctx.resolve_file_reference("resume.pdf")
            msg = str(exc.value)
            assert "b/resume.pdf" in msg
            assert "c/resume.pdf" in msg

    def test_three_duplicates_across_dirs(self, tmp_path):
        """Three copies of same file across three directories."""
        for name in ["alpha", "beta", "gamma"]:
            d = tmp_path / name
            d.mkdir()
            (d / "settings.json").write_text(f"{name}")

        with FilesContext(str(tmp_path)) as ctx:
            with pytest.raises(AmbiguousFileError) as exc:
                ctx.resolve_file_reference("settings.json")
            msg = str(exc.value)
            assert "alpha/settings.json" in msg
            assert "beta/settings.json" in msg
            assert "gamma/settings.json" in msg

    def test_unique_file_not_affected_by_others(self, tmp_path):
        """A file that exists only once should resolve even if dir has duplicates."""
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "resume.pdf").write_text("v1")
        (dir_b / "resume.pdf").write_text("v2")
        (dir_a / "cover_letter.pdf").write_text("unique")

        with FilesContext(str(tmp_path)) as ctx:
            result = ctx.resolve_file_reference("cover_letter.pdf")
            assert result == str(dir_a / "cover_letter.pdf")


class TestMinimalUniquePaths:
    """Unit tests for _compute_minimal_unique_paths."""

    def test_single_path(self):
        from lamia.engine.managers.llm.files_context_manager import _compute_minimal_unique_paths
        result = _compute_minimal_unique_paths(["/a/b/file.txt"])
        assert result == {"/a/b/file.txt": "file.txt"}

    def test_two_paths_different_parent(self):
        from lamia.engine.managers.llm.files_context_manager import _compute_minimal_unique_paths
        result = _compute_minimal_unique_paths(["/a/b/file.txt", "/a/c/file.txt"])
        assert result["/a/b/file.txt"] == "b/file.txt"
        assert result["/a/c/file.txt"] == "c/file.txt"

    def test_deeper_nesting_needs_more_components(self):
        from lamia.engine.managers.llm.files_context_manager import _compute_minimal_unique_paths
        result = _compute_minimal_unique_paths([
            "/x/y/sub/file.txt",
            "/x/z/sub/file.txt",
        ])
        assert result["/x/y/sub/file.txt"] == "y/sub/file.txt"
        assert result["/x/z/sub/file.txt"] == "z/sub/file.txt"

    def test_three_paths(self):
        from lamia.engine.managers.llm.files_context_manager import _compute_minimal_unique_paths
        result = _compute_minimal_unique_paths([
            "/a/alpha/f.txt",
            "/a/beta/f.txt",
            "/a/gamma/f.txt",
        ])
        assert result["/a/alpha/f.txt"] == "alpha/f.txt"
        assert result["/a/beta/f.txt"] == "beta/f.txt"
        assert result["/a/gamma/f.txt"] == "gamma/f.txt"

    def test_same_parent_different_grandparent(self):
        from lamia.engine.managers.llm.files_context_manager import _compute_minimal_unique_paths
        result = _compute_minimal_unique_paths([
            "/a/b/shared/f.txt",
            "/a/c/shared/f.txt",
        ])
        assert result["/a/b/shared/f.txt"] == "b/shared/f.txt"
        assert result["/a/c/shared/f.txt"] == "c/shared/f.txt"


class TestVariablePathsInFilesContext:
    """files() must work with variable paths, not just string literals."""

    def test_variable_holding_directory_path(self, tmp_path):
        """A variable pointing to a directory should index files."""
        (tmp_path / "report.txt").write_text("Q3 results")
        dir_path = str(tmp_path)

        with FilesContext(dir_path) as ctx:
            result = ctx.resolve_file_reference("report.txt")
            assert result == str(tmp_path / "report.txt")

    def test_variable_holding_single_file_path(self, tmp_path):
        """A variable pointing to a single file should index just that file."""
        f = tmp_path / "resume.pdf"
        f.write_text("John Doe")
        file_path = str(f)

        with FilesContext(file_path) as ctx:
            assert len(ctx.indexed_files) == 1
            result = ctx.resolve_file_reference("resume.pdf")
            assert result == str(f)

    def test_multiple_variable_paths(self, tmp_path):
        """Multiple variable paths are all indexed."""
        dir_a = tmp_path / "docs"
        dir_b = tmp_path / "config"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "readme.md").write_text("Hello")
        (dir_b / "settings.json").write_text("{}")

        path_a = str(dir_a)
        path_b = str(dir_b)

        with FilesContext(path_a, path_b) as ctx:
            assert ctx.resolve_file_reference("readme.md") == str(dir_a / "readme.md")
            assert ctx.resolve_file_reference("settings.json") == str(dir_b / "settings.json")

    def test_single_file_no_with_required_for_exact(self, tmp_path):
        """When files() gets a single file, it indexes just that file."""
        f = tmp_path / "data.csv"
        f.write_text("a,b,c")

        with FilesContext(str(f)) as ctx:
            assert len(ctx.indexed_files) == 1
            assert ctx.resolve_file_reference("data.csv") == str(f)

    def test_variable_path_nonexistent_warns(self, tmp_path):
        """A variable pointing to a non-existent path: zero files indexed."""
        bad_path = str(tmp_path / "nonexistent_dir")

        with FilesContext(bad_path) as ctx:
            assert len(ctx.indexed_files) == 0

    def test_mix_of_file_and_dir_paths(self, tmp_path):
        """Mix of a single file and a directory."""
        single = tmp_path / "standalone.txt"
        single.write_text("solo")
        subdir = tmp_path / "extras"
        subdir.mkdir()
        (subdir / "bonus.txt").write_text("extra")

        with FilesContext(str(single), str(subdir)) as ctx:
            assert ctx.resolve_file_reference("standalone.txt") == str(single)
            assert ctx.resolve_file_reference("bonus.txt") == str(subdir / "bonus.txt")


class TestHuVariableFileReferences:
    """Test {@variable} resolution in .hu executor with kwargs."""

    def test_kwarg_replaces_file_ref(self):
        """When caller passes doc_path kwarg, {@doc_path} becomes {@value}."""
        from lamia.interpreter.human.parser import HuFunction
        from lamia.interpreter.human.executor import HuCallable

        fn = HuFunction(
            name="summarize",
            template="Summarize {@doc_path}",
            params=frozenset(),
            source_path="/tmp/test.hu",
        )
        c = HuCallable(fn)

        with patch("lamia.interpreter.human.executor.get_active_files_context") as mock:
            mock.return_value = MagicMock()
            result = c(doc_path="report.pdf")
            assert "{@report.pdf}" in result
            assert "{@doc_path}" not in result

    def test_no_kwarg_keeps_literal_filename(self):
        """Without kwarg, {@article.txt} stays as-is for file resolution."""
        from lamia.interpreter.human.parser import HuFunction
        from lamia.interpreter.human.executor import HuCallable

        fn = HuFunction(
            name="summarize",
            template="Summarize {@article.txt}",
            params=frozenset(),
            source_path="/tmp/test.hu",
        )
        c = HuCallable(fn)

        with patch("lamia.interpreter.human.executor.get_active_files_context") as mock:
            mock.return_value = MagicMock()
            result = c()
            assert "{@article.txt}" in result

    def test_variable_ref_with_extension_stays_literal(self):
        """If template has {@resume.pdf} and no kwarg named 'resume.pdf', it stays."""
        from lamia.interpreter.human.parser import HuFunction
        from lamia.interpreter.human.executor import HuCallable

        fn = HuFunction(
            name="extract",
            template="Extract from {@resume.pdf}",
            params=frozenset(),
            source_path="/tmp/test.hu",
        )
        c = HuCallable(fn)

        with patch("lamia.interpreter.human.executor.get_active_files_context") as mock:
            mock.return_value = MagicMock()
            result = c()
            assert "{@resume.pdf}" in result

    def test_param_substitution_and_file_ref_coexist(self):
        """Both {variable} and {@file} work in the same template."""
        from lamia.interpreter.human.parser import HuFunction
        from lamia.interpreter.human.executor import HuCallable

        fn = HuFunction(
            name="answer",
            template="Answer {question} using {@resume.pdf}",
            params=frozenset({"question"}),
            source_path="/tmp/test.hu",
        )
        c = HuCallable(fn)

        with patch("lamia.interpreter.human.executor.get_active_files_context") as mock:
            mock.return_value = MagicMock()
            result = c(question="What are my skills?")
            assert "What are my skills?" in result
            assert "{@resume.pdf}" in result
            assert "{question}" not in result


class TestStandaloneVariablePathResolution:
    """Verify {@variable_path} resolves without files() context."""

    def test_kwarg_absolute_path_resolves_standalone(self, tmp_path):
        """Pass absolute file path as kwarg — resolves without files()."""
        from lamia.interpreter.human.parser import HuFunction
        from lamia.interpreter.human.executor import HuCallable

        f = tmp_path / "article.txt"
        f.write_text("The quick brown fox")

        fn = HuFunction(
            name="summarize",
            template="Summarize: {@doc_path}",
            params=frozenset(),
            source_path=str(tmp_path / "test.hu"),
        )
        c = HuCallable(fn)

        with patch("lamia.interpreter.human.executor.get_active_files_context") as mock:
            mock.return_value = None
            result = c(doc_path=str(f))
            assert "The quick brown fox" in result
            assert "{@" not in result

    def test_kwarg_relative_path_resolves_standalone(self, tmp_path):
        """Pass relative path as kwarg — resolves relative to .hu file."""
        from lamia.interpreter.human.parser import HuFunction
        from lamia.interpreter.human.executor import HuCallable

        subdir = tmp_path / "data"
        subdir.mkdir()
        f = subdir / "report.txt"
        f.write_text("Q3 earnings")

        fn = HuFunction(
            name="summarize",
            template="Summarize: {@doc_path}",
            params=frozenset(),
            source_path=str(tmp_path / "test.hu"),
        )
        c = HuCallable(fn)

        with patch("lamia.interpreter.human.executor.get_active_files_context") as mock:
            mock.return_value = None
            result = c(doc_path="./data/report.txt")
            assert "Q3 earnings" in result

    def test_kwarg_bare_filename_resolves_relative_to_hu_file(self, tmp_path):
        """Bare filename resolves relative to the .hu file first."""
        from lamia.interpreter.human.parser import HuFunction
        from lamia.interpreter.human.executor import HuCallable

        prompts = tmp_path / "prompts"
        prompts.mkdir()
        (prompts / "notes.txt").write_text("Local notes")

        fn = HuFunction(
            name="read",
            template="Read: {@doc_path}",
            params=frozenset(),
            source_path=str(prompts / "reader.hu"),
        )
        c = HuCallable(fn)

        with patch("lamia.interpreter.human.executor.get_active_files_context") as mock:
            mock.return_value = None
            result = c(doc_path="notes.txt")
            assert "Local notes" in result

    def test_kwarg_bare_filename_not_in_hu_dir_raises(self, tmp_path):
        """Bare filename must exist in the .hu file directory."""
        from lamia.interpreter.human.parser import HuFunction
        from lamia.interpreter.human.executor import HuCallable

        prompts = tmp_path / "prompts"
        prompts.mkdir()
        (tmp_path / "notes.txt").write_text("Project root notes")

        fn = HuFunction(
            name="read",
            template="Read: {@doc_path}",
            params=frozenset(),
            source_path=str(prompts / "reader.hu"),
        )
        c = HuCallable(fn)

        with patch("lamia.interpreter.human.executor.get_active_files_context") as mock:
            mock.return_value = None
            with pytest.raises(FileReferenceError):
                c(doc_path="notes.txt")