"""Tests for cross-file entity reference feedback in tools."""

import tempfile
from pathlib import Path

import pytest

from lamia.tools.dispatch import (
    entity_reference_feedback,
    entity_references_footer,
    FileAction,
    _read_file,
    _write_file,
    _delete_file,
    _copy_file,
    _move_file,
    _patch_file,
    reset_file_writes,
)


@pytest.fixture(autouse=True)
def clean_writes():
    reset_file_writes()
    yield
    reset_file_writes()


@pytest.fixture
def project_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _write(base: str, relpath: str, content: str) -> Path:
    p = Path(base) / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


class TestEntityReferenceFeedbackDelete:

    def test_delete_warns_about_references(self, project_dir):
        hu = _write(project_dir, "team/helper.hu", "{task}")
        _write(project_dir, "main.lm", "result = helper(task=t) -> JSON[X]")

        feedback = entity_reference_feedback(hu, project_dir, FileAction.DELETE)
        assert "deleted" in feedback.lower()
        assert "main.lm" in feedback

    def test_delete_no_references_empty(self, project_dir):
        hu = _write(project_dir, "team/orphan.hu", "{task}")

        feedback = entity_reference_feedback(hu, project_dir, FileAction.DELETE)
        assert feedback == ""


class TestEntityReferenceFeedbackWritePatch:

    def test_write_hu_warns_missing_params(self, project_dir):
        hu = _write(project_dir, "team/worker.hu", "{a} {b} {c}")
        _write(project_dir, "main.lm", "r = worker(a=1) -> JSON[X]")

        feedback = entity_reference_feedback(hu, project_dir, FileAction.WRITE)
        assert "b" in feedback or "c" in feedback
        assert "main.lm" in feedback

    def test_write_hu_all_params_no_warning(self, project_dir):
        hu = _write(project_dir, "team/worker.hu", "{a} {b}")
        _write(project_dir, "main.lm", "r = worker(a=1, b=2) -> JSON[X]")

        feedback = entity_reference_feedback(hu, project_dir, FileAction.WRITE)
        assert feedback == ""

    def test_write_hu_nested_call_arg_does_not_fake_missing_params(self, project_dir):
        hu = _write(project_dir, "team/developer.hu", "{specs} {prd_content} {existing_code} {compile_errors}")
        _write(
            project_dir,
            "orchestrator.lm",
            (
                "impl = developer(specs=s, prd_content=p, "
                "existing_code=read_project_files(project_dir), "
                'compile_errors="(none)") -> JSON[Implementation]'
            ),
        )

        feedback = entity_reference_feedback(hu, project_dir, FileAction.WRITE)
        assert feedback == ""

    def test_write_py_no_feedback(self, project_dir):
        py = _write(project_dir, "utils.py", "def foo(): pass")
        feedback = entity_reference_feedback(py, project_dir, FileAction.WRITE)
        assert feedback == ""


class TestEntityReferenceFeedbackMove:

    def test_move_hu_no_feedback(self, project_dir):
        """Move of .hu files should not produce feedback — .hu resolves by stem."""
        hu = _write(project_dir, "team/agent.hu", "{prompt}")
        _write(project_dir, "main.lm", "r = agent(prompt=p) -> JSON[X]")

        feedback = entity_reference_feedback(hu, project_dir, FileAction.MOVE)
        assert feedback == ""

    def test_move_py_warns_references(self, project_dir):
        py = _write(project_dir, "utils.py", "def helper(): pass")
        _write(project_dir, "main.lm", "import utils\nresult = utils.helper()")

        feedback = entity_reference_feedback(py, project_dir, FileAction.MOVE)
        assert "main.lm" in feedback


class TestEntityReferencesFooter:

    def test_hu_file_shows_references(self, project_dir):
        hu = _write(project_dir, "team/helper.hu", "{task}")
        _write(project_dir, "main.lm", "result = helper(task=t)")

        footer = entity_references_footer(hu, project_dir)
        assert "Referenced by" in footer
        assert "main.lm" in footer

    def test_no_references_empty(self, project_dir):
        hu = _write(project_dir, "team/lonely.hu", "{task}")
        footer = entity_references_footer(hu, project_dir)
        assert footer == ""

    def test_py_file_no_footer(self, project_dir):
        py = _write(project_dir, "utils.py", "def foo(): pass")
        footer = entity_references_footer(py, project_dir)
        assert footer == ""


class TestToolIntegration:

    def test_read_file_includes_footer(self, project_dir):
        _write(project_dir, "team/helper.hu", "{task}")
        _write(project_dir, "main.lm", "r = helper(task=t)")

        result = _read_file("team/helper.hu", (Path(project_dir),))
        assert "Referenced by" in result

    def test_write_file_includes_entity_ref_warning(self, project_dir):
        _write(project_dir, "main.lm", "r = worker(a=1) -> JSON[X]")

        result = _write_file("team/worker.hu", "{a} {b} {c}", project_dir)
        assert "Written:" in result
        assert "USAGE WARNING" in result

    def test_delete_file_includes_entity_ref_warning(self, project_dir):
        _write(project_dir, "team/helper.hu", "{task}")
        _write(project_dir, "main.lm", "r = helper(task=t)")

        result = _delete_file("team/helper.hu", project_dir)
        assert "Deleted:" in result
        assert "main.lm" in result

    def test_copy_hu_warns_name_conflict(self, project_dir):
        _write(project_dir, "team/helper.hu", "{task}")

        result = _copy_file("team/helper.hu", "team2/helper.hu", project_dir)
        assert "same function name" in result.lower()

    def test_copy_hu_different_name_no_warning(self, project_dir):
        _write(project_dir, "team/helper.hu", "{task}")

        result = _copy_file("team/helper.hu", "team2/assistant.hu", project_dir)
        assert "same function name" not in result.lower()

    def test_patch_file_includes_entity_ref_warning(self, project_dir):
        _write(project_dir, "team/worker.hu", "{a}")
        _write(project_dir, "main.lm", "r = worker(a=1) -> JSON[X]")

        result = _patch_file("team/worker.hu", "{a}", "{a} {b} {c}", project_dir)
        assert "Patched:" in result
        assert "USAGE WARNING" in result
