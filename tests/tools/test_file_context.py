from lamia.engine.managers.llm.files_context_manager import files
from lamia.tools import file_context
from lamia.tools.file_context import run_with_file_tools


def _listed_paths(prompt: str) -> list[str]:
    block = prompt.split("<available_paths>\n", 1)[1].split("\n</available_paths>", 1)[0]
    return block.splitlines()


async def _captured_loop_call(monkeypatch, *paths: str) -> dict:
    captured = {}

    async def fake_run_tool_loop(lamia, prompt, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        raise StopAsyncIteration

    monkeypatch.setattr(file_context, "run_tool_loop", fake_run_tool_loop)
    with files(*paths):
        try:
            await run_with_file_tools(lamia=None, prompt="Summarize the notes")
        except StopAsyncIteration:
            pass
    return captured


async def test_listed_paths_match_allowed_dirs(monkeypatch, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "report.md").write_text("report")
    notes = tmp_path / "notes.txt"
    notes.write_text("notes")

    call = await _captured_loop_call(monkeypatch, str(notes), str(docs))

    assert call["restrict_to_allowed_dirs"] is True
    assert call["allowed_dirs"] == [notes.resolve(), docs.resolve()]
    assert _listed_paths(call["prompt"]) == [str(notes.resolve()), f"{docs.resolve()}/"]
    assert call["prompt"].endswith("</available_paths>\n\nSummarize the notes")


async def test_missing_path_is_neither_listed_nor_allowed(monkeypatch, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("notes")
    missing = tmp_path / "missing.txt"

    call = await _captured_loop_call(monkeypatch, str(notes), str(missing))

    assert call["allowed_dirs"] == [notes.resolve()]
    assert _listed_paths(call["prompt"]) == [str(notes.resolve())]
