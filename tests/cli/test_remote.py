import pytest
from pathlib import Path

from lamia_cloud.contracts import FileSyncEntry
from lamia.cli.remote import (
    ScriptCapabilities,
    SCRIPT_CAPABILITY_FIELDS,
    _warn_about_file_uploads,
    analyze_script,
    script_capability_field_names,
)
from lamia.interpreter.ast_analyzer import extract_script_file_refs


def _write_script(tmp_path: Path, name: str, content: str) -> Path:
    script_path = tmp_path / name
    script_path.write_text(content)
    return script_path


def test_analyze_script_detects_llm_web_file_and_file_context(tmp_path):
    script = _write_script(
        tmp_path,
        "all_features.lm",
        """
def ask_user():
    "Summarize the latest status update"

def run():
    web.navigate("https://example.com")
    file.read("notes.txt")
    with files("docs/"):
        pass
""".strip(),
    )

    result = analyze_script(script)

    assert result.uses_llm is True
    assert result.uses_browser is True
    assert result.uses_files is True
    assert result.uses_file_context is True


def test_analyze_script_detects_no_capabilities_for_plain_script(tmp_path):
    script = _write_script(
        tmp_path,
        "plain.lm",
        """
def run():
    value = 1 + 1
    return value
""".strip(),
    )

    result = analyze_script(script)

    assert result.uses_llm is False
    assert result.uses_browser is False
    assert result.uses_files is False
    assert result.uses_file_context is False


def test_analyze_script_detects_only_llm(tmp_path):
    script = _write_script(
        tmp_path,
        "llm_only.lm",
        """
def ask_user():
    "Write a brief status summary"
""".strip(),
    )

    result = analyze_script(script)

    assert result.uses_llm is True
    assert result.uses_browser is False
    assert result.uses_files is False
    assert result.uses_file_context is False


def test_analyze_script_detects_only_browser(tmp_path):
    script = _write_script(
        tmp_path,
        "browser_only.lm",
        """
def run():
    web.navigate("https://example.com")
""".strip(),
    )

    result = analyze_script(script)

    assert result.uses_llm is False
    assert result.uses_browser is True
    assert result.uses_files is False
    assert result.uses_file_context is False


def test_analyze_script_detects_only_files(tmp_path):
    script = _write_script(
        tmp_path,
        "files_only.lm",
        """
def run():
    file.read("notes.txt")
""".strip(),
    )

    result = analyze_script(script)

    assert result.uses_llm is False
    assert result.uses_browser is False
    assert result.uses_files is True
    assert result.uses_file_context is False


def test_analyze_script_detects_only_file_context(tmp_path):
    script = _write_script(
        tmp_path,
        "file_context_only.lm",
        """
def run():
    with files("docs/"):
        pass
""".strip(),
    )

    result = analyze_script(script)

    assert result.uses_llm is False
    assert result.uses_browser is False
    assert result.uses_files is False
    assert result.uses_file_context is True


def test_analyze_script_syntax_error_falls_back_to_empty_capabilities(tmp_path):
    script = _write_script(
        tmp_path,
        "broken.lm",
        """
def run(
    return 1
""".strip(),
    )

    result = analyze_script(script)

    assert result.uses_llm is False
    assert result.uses_browser is False
    assert result.uses_files is False
    assert result.uses_file_context is False


def test_script_capabilities_contract_field_names():
    field_names = script_capability_field_names()
    assert field_names == tuple(SCRIPT_CAPABILITY_FIELDS), (
        "ScriptCapabilities contract changed. If you add/rename/remove fields, "
        "update BOTH lamia.cli.remote.ScriptCapabilities and "
        "lamia.cli.remote.SCRIPT_CAPABILITY_FIELDS + the mirrored keys in "
        "lamia_cloud.contracts.SCRIPT_CAPABILITY_FIELDS."
    )


def test_warn_about_file_uploads_prints_warning(capsys):
    entries = [
        FileSyncEntry(raw_path="docs/a.txt", resolved_path="/tmp/a.txt", bucket_key="docs/a.txt"),
        FileSyncEntry(raw_path="docs/b.txt", resolved_path="/tmp/b.txt", bucket_key="docs/b.txt"),
    ]
    _warn_about_file_uploads(entries)
    stderr = capsys.readouterr().err
    assert "will upload local files" in stderr
    assert "docs/a.txt" in stderr
    assert "docs/b.txt" in stderr


def test_extract_file_refs_single_path(tmp_path):
    script = _write_script(tmp_path, "task.lm", 'with files("data/input.csv"):\n    pass')
    assert extract_script_file_refs(script) == ["data/input.csv"]


def test_extract_file_refs_multiple_paths_same_block(tmp_path):
    script = _write_script(tmp_path, "task.lm", 'with files("docs", "config.json"):\n    pass')
    assert extract_script_file_refs(script) == ["docs", "config.json"]


def test_extract_file_refs_multiple_blocks(tmp_path):
    script = _write_script(tmp_path, "task.lm",
        'with files("a.txt"):\n    pass\nwith files("b/"):\n    pass')
    assert extract_script_file_refs(script) == ["a.txt", "b/"]


def test_extract_file_refs_dynamic_arg_raises(tmp_path):
    script = _write_script(tmp_path, "task.lm", 'with files(some_var):\n    pass')
    with pytest.raises(ValueError, match="literal strings"):
        extract_script_file_refs(script)


def test_extract_file_refs_no_files_blocks(tmp_path):
    script = _write_script(tmp_path, "task.lm", 'x = 1\nprint(x)')
    assert extract_script_file_refs(script) == []
