"""Text-based tool-call parsing and formatting.

Used by:
- CLI JSON mode tool loop (cli/cli.py)
- LLM manager file-context tool loop (engine/managers/llm/llm_manager.py)
"""

from __future__ import annotations

import json
import re

MALFORMED_TOOL_PATTERNS = [
    re.compile(r"<function_calls>", re.IGNORECASE),
    re.compile(r"<tool_call>", re.IGNORECASE),
    re.compile(r"<tool_use>", re.IGNORECASE),
    re.compile(r'<invoke\s+name\s*=\s*["\']', re.IGNORECASE),
    re.compile(r"```tool", re.IGNORECASE),
    re.compile(r"```json\s*\n\s*\{\s*\"tool", re.IGNORECASE),
]

MALFORMED_JSON_KEYS = [
    ("name", "input"),  # Anthropic native tool_use
    ("function", "arguments"),  # OpenAI function_call
    ("name", "parameters"),  # Generic
    ("tool_name", "args"),  # Close but wrong key
    ("tool_name", "parameters"),
]

TOOL_FORMAT_CORRECTION = (
    "Your tool call was NOT in the correct format and could not be executed. "
    "Do NOT use XML tags like <function_calls>, <invoke>, <tool_call>, or <tool_use>. "
    'Do NOT use JSON keys like "name"/"input" or "function"/"arguments".\n\n'
    "You MUST use this EXACT JSON format on its own line:\n"
    '{"tool": "tool_name", "args": {"param": "value"}}\n\n'
    "Retry your tool call now using the correct format."
)


def extract_tool_calls(text: str) -> list[dict]:
    """Extract tool calls from LLM response text.

    Supports:
    - JSON lines: {"tool": "name", "args": {...}}
    - XML blocks: <invoke>...</invoke>
    """
    calls: list[dict] = []

    for line in text.strip().split("\n"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
            if "tool" in obj and isinstance(obj.get("tool"), str):
                calls.append(obj)
        except json.JSONDecodeError:
            continue

    for invoke_match in re.finditer(r"<invoke\b[^>]*>(.*?)</invoke>", text, re.DOTALL):
        block = invoke_match.group(1)
        name_match = re.search(r"<tool_name>\s*(\w+)\s*</tool_name>", block)
        if name_match:
            args: dict = {}
            for pm in re.finditer(
                r'<parameter\s+name="(\w+)">(.*?)</parameter>', block, re.DOTALL
            ):
                args[pm.group(1)] = pm.group(2)
            calls.append({"tool": name_match.group(1), "args": args})

    return calls


def detect_malformed_tool_call(text: str) -> bool:
    """Detect attempted tool calls in unsupported formats."""
    for pattern in MALFORMED_TOOL_PATTERNS:
        if pattern.search(text):
            return True

    for line in text.strip().split("\n"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            for key_a, key_b in MALFORMED_JSON_KEYS:
                if key_a in obj and key_b in obj:
                    return True
        except json.JSONDecodeError:
            continue

    return False


def strip_tool_calls(text: str) -> str:
    """Remove tool-call JSON and XML blocks from response text."""
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("{"):
            try:
                obj = json.loads(stripped)
                if not isinstance(obj, dict):
                    lines.append(line)
                    continue
                if "tool" in obj and isinstance(obj.get("tool"), str):
                    continue
                for key_a, key_b in MALFORMED_JSON_KEYS:
                    if key_a in obj and key_b in obj:
                        break
                else:
                    lines.append(line)
                    continue
            except json.JSONDecodeError:
                lines.append(line)
                continue
        else:
            lines.append(line)
    result = "\n".join(lines)

    result = re.sub(r"<function_calls>.*?</function_calls>", "", result, flags=re.DOTALL)
    result = re.sub(r"<tool_call>.*?</tool_call>", "", result, flags=re.DOTALL)
    result = re.sub(r"<tool_use>.*?</tool_use>", "", result, flags=re.DOTALL)
    result = re.sub(r"<tool_result>.*?</tool_result>", "", result, flags=re.DOTALL)
    result = re.sub(r"<invoke\b[^>]*>.*?</invoke>", "", result, flags=re.DOTALL)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def build_tool_result_entry(tool_name: str, tool_args: dict, tool_result: str) -> dict[str, object]:
    """Build a single tool result entry for the next LLM round."""
    return {
        "tool": tool_name,
        "args": tool_args,
        "result": tool_result,
    }
