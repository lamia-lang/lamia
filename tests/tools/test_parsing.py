import json

from lamia.tools.definitions import ToolName
from lamia.tools.parsing import (
    build_tool_result_entry as _build_tool_result_entry,
    extract_response_blocks,
    extract_tool_calls as _extract_tool_calls,
    strip_tool_calls as _strip_tool_calls,
)


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


class TestToolCallExtraction:
    """Unit tests for batched tool-call extraction."""

    def test_extracts_multiple_json_tool_calls(self):
        text = """
Here is what I will do:
{"tool": "read_file", "args": {"path": "team/product_manager.hu"}}
And then patch:
{"tool": "patch_file", "args": {"path": "team/product_manager.hu", "old_text": "a", "new_text": "b"}}
"""
        calls = _extract_tool_calls(text)
        assert len(calls) == 2
        assert calls[0]["tool"] == ToolName.READ_FILE
        assert calls[0]["args"]["path"] == "team/product_manager.hu"
        assert calls[1]["tool"] == ToolName.PATCH_FILE
        assert calls[1]["args"]["path"] == "team/product_manager.hu"

    def test_extracts_multiple_invoke_tool_calls(self):
        text = """
<invoke>
  <tool_name>read_file</tool_name>
  <parameter name="path">team/product_manager.hu</parameter>
</invoke>
<invoke>
  <tool_name>patch_file</tool_name>
  <parameter name="path">team/product_manager.hu</parameter>
  <parameter name="old_text">a</parameter>
  <parameter name="new_text">b</parameter>
</invoke>
"""
        calls = _extract_tool_calls(text)
        assert len(calls) == 2
        assert calls[0]["tool"] == ToolName.READ_FILE
        assert calls[1]["tool"] == ToolName.PATCH_FILE

    def test_ignores_non_tool_json(self):
        text = """
{"note": "this is not a tool call"}
{"tool": "read_file", "args": {"path": "x.hu"}}
"""
        calls = _extract_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["tool"] == ToolName.READ_FILE

    def test_strip_tool_calls_removes_tool_result_blocks(self):
        text = """
Now let me update the file:
{"tool": "patch_file", "args": {"path": "orchestrator.lm", "old_text": "a", "new_text": "b"}}

<tool_result>
✓ File updated: orchestrator.lm
</tool_result>

Done.
"""
        cleaned = _strip_tool_calls(text)
        assert "<tool_result>" not in cleaned
        assert "File updated: orchestrator.lm" not in cleaned
        assert "Done." in cleaned

    def test_build_tool_result_entry_includes_tool_and_args(self):
        entry = _build_tool_result_entry(
            ToolName.WRITE_FILE,
            {"path": "orchestrator.lm", "content": "x"},
            "File written successfully",
        )
        assert entry["tool"] == ToolName.WRITE_FILE
        assert entry["args"]["path"] == "orchestrator.lm"
        assert entry["result"] == "File written successfully"

    def test_tool_result_entries_are_json_serializable(self):
        entries = [
            _build_tool_result_entry(
                ToolName.WRITE_FILE,
                {"path": "orchestrator.lm"},
                "File written successfully",
            ),
            _build_tool_result_entry(
                ToolName.PATCH_FILE,
                {"path": "team/product_manager.hu", "old_text": "a", "new_text": "b"},
                "File patched successfully",
            ),
        ]
        payload = {"tool_results": entries}
        encoded = json.dumps(payload)
        assert '"tool_results"' in encoded
        assert '"tool": "write_file"' in encoded
        assert '"tool": "patch_file"' in encoded

    def test_strip_tool_calls_removes_tool_result_block(self):
        text = """
<tool_result>
File written successfully
</tool_result>
Final answer.
"""
        cleaned = _strip_tool_calls(text)
        assert "<tool_result>" not in cleaned
        assert "Final answer." in cleaned
