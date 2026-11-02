"""Tests for the tools system prompt."""
from lamia.tools.definitions import FILE_CONTEXT_TOOL_NAMES, HU_FILE_HINT, TOOL_DEFINITIONS
from lamia.tools.dispatch import _get_docs, get_tools_system_prompt
from lamia.tools.signature import render_signature


def test_required_optional_and_defaults():
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "offset": {"type": "integer", "default": 0},
            "ratio": {"type": "number", "default": 1.5},
            "depth": {"type": "integer"},
        },
        "required": ["path"],
    }
    assert render_signature("f", schema) == (
        "f(path: str, offset: int = 0, ratio: float = 1.5, depth: int | None = None)"
    )


def test_no_params():
    assert render_signature("f", {"type": "object", "properties": {}}) == "f()"


def test_prompt_lists_every_tool_with_signature():
    prompt = get_tools_system_prompt()
    for t in TOOL_DEFINITIONS:
        assert f"- {render_signature(t['name'], t['parameters'])}:" in prompt


def test_prompt_shows_defaults():
    prompt = get_tools_system_prompt()
    assert "read_file(path: str, offset: int = 0, chunk_size: int = 100000)" in prompt
    assert "browser_wait(selector: str, timeout: float = 10)" in prompt


def test_prompt_explains_required_marker():
    assert "Parameters without '=' are required" in get_tools_system_prompt()


def test_hu_hint_appears_once():
    assert get_tools_system_prompt().count(HU_FILE_HINT) == 1


def test_hu_hint_omitted_for_read_only_tools():
    prompt = get_tools_system_prompt(set(FILE_CONTEXT_TOOL_NAMES))
    assert HU_FILE_HINT not in prompt


def test_get_docs_empty_topic_lists_topics():
    out = _get_docs("")
    assert out.startswith("Available topics:")
    assert "lm-syntax" in out
