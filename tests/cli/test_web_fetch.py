"""Tests for web_fetch tool using Lamia HTTP actions."""

from lamia.tools.dispatch import ToolName, _web_fetch, execute_tool
from lamia.interpreter.commands import WebActionType


class DummyLamia:
    """Simple Lamia stub for tool tests."""

    def __init__(self, result=None, should_raise: bool = False):
        self.result = result
        self.should_raise = should_raise
        self.last_command = None

    def run(self, command):
        self.last_command = command
        if self.should_raise:
            raise RuntimeError("request failed")
        return self.result


class TestWebFetch:
    def test_missing_url_returns_error(self):
        assert _web_fetch("", DummyLamia()).startswith("Error")

    def test_missing_lamia_returns_error(self):
        assert _web_fetch("https://example.com", None).startswith("Error")

    def test_uses_http_request_command(self):
        lamia = DummyLamia("ok")
        result = _web_fetch("https://example.com", lamia)

        assert result == "ok"
        assert lamia.last_command is not None
        assert lamia.last_command.action == WebActionType.HTTP_REQUEST
        assert lamia.last_command.url == "https://example.com"
        assert lamia.last_command.method == "GET"

    def test_normalizes_url_with_missing_scheme(self):
        lamia = DummyLamia("ok")
        _web_fetch("example.com", lamia)
        assert lamia.last_command.url == "https://example.com"

    def test_serializes_dict_result(self):
        lamia = DummyLamia({"status": "ok", "count": 2})
        result = _web_fetch("https://example.com", lamia)
        assert '"status": "ok"' in result
        assert '"count": 2' in result

    def test_handles_runtime_errors(self):
        lamia = DummyLamia(should_raise=True)
        result = _web_fetch("https://example.com", lamia)
        assert result.startswith("Error fetching:")

    def test_truncates_long_results(self):
        lamia = DummyLamia("x" * 120_000)
        result = _web_fetch("https://example.com", lamia)
        assert "truncated" in result

    def test_execute_tool_routes_web_fetch(self):
        lamia = DummyLamia("hello")
        result, success = execute_tool(
            ToolName.WEB_FETCH, {"url": "https://example.com"}, lamia=lamia
        )
        assert success
        assert result == "hello"
