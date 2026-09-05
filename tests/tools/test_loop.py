from collections import deque
from pathlib import Path

from lamia.tools.loop import _run_response_blocks


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
        history=deque(),
        on_message=emitted.append,
    )

    assert "repeated" in entries[0]["result"]
    assert emitted[-1].success is False
