from collections import deque
from pathlib import Path

from lamia.facade.result_types import LamiaResult
from lamia.tools.loop import _run_response_blocks, run_tool_loop


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


async def test_rounds_are_sent_as_a_conversation(monkeypatch):
    tool_call = '{"tool": "read_file", "args": {"path": "a.txt"}}'
    replies = iter([tool_call, "The file says hello."])
    commands = []

    class FakeLamia:
        async def run_async(self, command, _full_result=False):
            commands.append(command)
            return LamiaResult(result_text=next(replies), typed_result=None, tracking_context=None)

    monkeypatch.setattr("lamia.tools.loop.execute_tool", lambda *args, **kwargs: ("hello", True))

    loop_result = await run_tool_loop(FakeLamia(), "Read a.txt", allowed_tools={"read_file"})

    first, second = commands
    assert first.history == []
    assert first.prompt.endswith("Read a.txt")
    assert second.history == [
        {"role": "user", "content": first.prompt},
        {"role": "assistant", "content": tool_call},
    ]
    assert second.prompt.startswith("Tool results JSON:")
    assert loop_result.prompt == second.prompt
    assert loop_result.history == second.history
    assert loop_result.result.result_text == "The file says hello."


async def test_prompt_is_sent_without_inlining_file_references():
    commands = []

    class FakeLamia:
        async def run_async(self, command, _full_result=False):
            commands.append(command)
            return LamiaResult(result_text="done", typed_result=None, tracking_context=None)

    await run_tool_loop(FakeLamia(), "Summarize {@notes.txt}", allowed_tools={"list_files"})

    command, = commands
    assert command.prompt.endswith("Summarize {@notes.txt}")
