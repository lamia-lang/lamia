from pathlib import Path

from lamia.tools.loop import _exceeds_call_limit, _run_response_blocks
from lamia.tools.parsing import extract_response_blocks


def test_unconfigured_tools_have_no_call_limit():
    call_counts = {}

    for _ in range(10):
        assert not _exceeds_call_limit("read_file", {"write_file": 1}, call_counts)

    assert call_counts == {}


def test_configured_tool_stops_after_its_call_cap():
    call_counts = {}

    assert not _exceeds_call_limit("write_file", {"write_file": 2}, call_counts)
    assert not _exceeds_call_limit("write_file", {"write_file": 2}, call_counts)
    assert _exceeds_call_limit("write_file", {"write_file": 2}, call_counts)


def test_response_blocks_keep_assistant_text_between_calls():
    response_blocks = extract_response_blocks(
        'I will read it.\n'
        '{"tool": "read_file", "args": {"path": "one.txt"}}\n'
        'Now I will update it.\n'
        '{"tool": "patch_file", "args": {"path": "one.txt"}}\n'
    )

    assert response_blocks == [
        "I will read it.\n",
        {"tool": "read_file", "args": {"path": "one.txt"}},
        "Now I will update it.\n",
        {"tool": "patch_file", "args": {"path": "one.txt"}},
    ]


def test_call_over_limit_is_returned_to_the_model(monkeypatch, tmp_path):
    emitted = []
    monkeypatch.setattr("lamia.tools.loop.execute_tool", lambda *args, **kwargs: ("ok", True))

    entries = _run_response_blocks(
        [{"tool": "read_file", "args": {"path": "a.txt"}}],
        lamia=None,
        allowed_tools=None,
        allowed_dirs=[Path(tmp_path)],
        restrict_to_allowed_dirs=False,
        max_calls_by_tool={"read_file": 0},
        call_counts={},
        on_message=emitted.append,
    )

    assert "limit reached" in entries[0]["result"]
    assert emitted[-1].success is False
