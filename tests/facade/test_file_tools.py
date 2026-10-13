"""Tests for when the facade answers a prompt through a tool loop that reads files."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from lamia import Lamia
from lamia.engine.managers.llm.files_context_manager import (
    INLINED_FILE_CHAR_LIMIT,
    files,
    pop_source_file,
    push_source_file,
)
from lamia.facade import lamia as facade_module
from lamia.facade.result_types import LamiaResult
from lamia.tools.loop import ToolLoopResult


@pytest.fixture
def lamia():
    lamia = Lamia("ollama")
    lamia._engine.execute = AsyncMock(return_value=SimpleNamespace(
        is_valid=True, raw_text="single call", validated_text="single call",
        typed_result=None, execution_context=None, error_message=None,
    ))
    return lamia


@pytest.fixture
def tool_loop(monkeypatch):
    calls = []

    async def fake_run_tool_loop(lamia, prompt, **kwargs):
        calls.append({"prompt": prompt, **kwargs})
        return ToolLoopResult(
            result=LamiaResult(result_text="tool loop", typed_result=None, tracking_context=None),
            prompt="Tool results JSON:\n{}",
            history=[],
        )

    monkeypatch.setattr(facade_module, "run_tool_loop", fake_run_tool_loop)
    return calls


@pytest.fixture
def script(tmp_path):
    push_source_file(str(tmp_path / "script.lm"))
    yield tmp_path
    pop_source_file()


def _listed_paths(prompt: str) -> list[str]:
    block = prompt.split("<available_paths>\n", 1)[1].split("\n</available_paths>", 1)[0]
    return block.splitlines()


async def test_no_context_and_no_reference_is_one_call(lamia, tool_loop):
    assert await lamia.run_async("Write a haiku") == "single call"
    assert tool_loop == []


async def test_small_referenced_file_without_context_is_one_call(lamia, tool_loop, script):
    (script / "small.txt").write_text("hello")

    assert await lamia.run_async("Summarize {@small.txt}") == "single call"

    assert tool_loop == []
    assert "hello" in lamia._engine.execute.await_args.args[0].prompt


async def test_cut_file_without_context_gets_tools_for_that_file(lamia, tool_loop, script):
    big = script / "big.csv"
    big.write_text("x" * (INLINED_FILE_CHAR_LIMIT + 10))

    assert await lamia.run_async("Summarize {@big.csv}") == "tool loop"

    call, = tool_loop
    assert call["allowed_dirs"] == [big]
    assert call["restrict_to_allowed_dirs"] is True
    assert "use available tools to read more if needed" in call["prompt"]


async def test_context_of_referenced_files_is_one_call(lamia, tool_loop, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("notes")

    with files(str(notes)):
        assert await lamia.run_async("Summarize {@notes.txt}") == "single call"

    assert tool_loop == []


async def test_context_with_unreferenced_file_gets_tools(lamia, tool_loop, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("notes")

    with files(str(notes)):
        assert await lamia.run_async("Summarize the notes") == "tool loop"

    call, = tool_loop
    assert call["allowed_dirs"] == [notes.resolve()]


async def test_context_paths_are_listed_and_allowed(lamia, tool_loop, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "report.md").write_text("report")
    notes = tmp_path / "notes.txt"
    notes.write_text("notes")

    with files(str(notes), str(docs), str(tmp_path / "missing.txt")):
        await lamia.run_async("Summarize {@notes.txt} and the report")

    call, = tool_loop
    assert call["allowed_dirs"] == [notes.resolve(), docs.resolve()]
    assert _listed_paths(call["prompt"]) == [str(notes.resolve()), f"{docs.resolve()}/"]
    assert call["prompt"].endswith("and the report")


async def test_context_with_cut_referenced_file_gets_tools(lamia, tool_loop, tmp_path):
    big = tmp_path / "big.csv"
    big.write_text("x" * (INLINED_FILE_CHAR_LIMIT + 10))

    with files(str(big)):
        assert await lamia.run_async("Summarize {@big.csv}") == "tool loop"

    call, = tool_loop
    assert call["allowed_dirs"] == [big.resolve()]
