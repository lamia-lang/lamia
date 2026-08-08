"""Unit tests for lamia.cli.debug_runner."""

import os
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel

from lamia.cli.debug_runner import LamiaDebugger, _fallback_offset_map


class MockCode:
    def __init__(self, filename: str, name: str = "run") -> None:
        self.co_filename = filename
        self.co_name = name


class MockFrame:
    def __init__(
        self,
        lineno: int,
        filename: str,
        *,
        f_locals: dict[str, Any] | None = None,
        f_globals: dict[str, Any] | None = None,
        f_back: "MockFrame | None" = None,
    ) -> None:
        self.f_lineno = lineno
        self.f_code = MockCode(filename)
        self.f_locals = f_locals if f_locals is not None else {}
        self.f_globals = f_globals if f_globals is not None else {}
        self.f_back = f_back


class QueueProtocolIO:
    """In-memory JSON protocol I/O for testing."""

    def __init__(self, commands: list[dict[str, Any]]) -> None:
        self._commands = list(commands)
        self.responses: list[dict[str, Any]] = []

    def send(self, obj: dict[str, Any]) -> None:
        self.responses.append(obj)

    def recv(self) -> dict[str, Any] | None:
        if self._commands:
            return self._commands.pop(0)
        return None


class SampleModel(BaseModel):
    name: str
    count: int


@dataclass
class PlainObject:
    label: str
    value: int


@pytest.fixture
def lm_file(tmp_path):
    path = tmp_path / "sample.lm"
    path.write_text("def run():\n    x = 1\n    return x\n")
    return str(path)


@pytest.fixture
def debugger(lm_file):
    return LamiaDebugger(lm_file, json_mode=False)


class TestFallbackOffsetMap:
    def test_identity_mapping_when_import_counts_match(self):
        original = "import os\n\ndef main():\n    pass\n"
        transformed = "import os\n\ndef main():\n    pass\n"

        lmap = _fallback_offset_map(original, transformed)

        assert len(lmap) == len(original.splitlines())
        for t_line, o_line in lmap.items():
            assert t_line == o_line
            assert o_line >= 1

    def test_positive_offset_when_transform_adds_imports(self):
        original = "def main():\n    pass\n"
        transformed = "import sys\nimport os\n\ndef main():\n    pass\n"

        lmap = _fallback_offset_map(original, transformed)

        assert lmap[4] == 1
        assert lmap[5] == 2
        assert 1 not in lmap
        assert all(orig >= 1 for orig in lmap.values())

    def test_all_mapped_lines_are_valid_original_lines(self):
        original = "import json\n\nprint('hi')\nprint('bye')\n"
        transformed = "import json\nimport sys\n\nprint('hi')\nprint('bye')\n"

        lmap = _fallback_offset_map(original, transformed)
        orig_count = len(original.splitlines())

        assert lmap
        for orig_line in lmap.values():
            assert 1 <= orig_line <= orig_count


class TestTraceBreakpointLogic:
    def _trace_line(self, debugger: LamiaDebugger, frame: MockFrame) -> list[dict[str, Any]]:
        stops: list[dict[str, Any]] = []

        def capture_stop(frame_obj, reason, lineno=None, filename=None):
            stops.append({
                "reason": reason,
                "lineno": lineno,
                "filename": filename,
            })

        debugger._stop = capture_stop  # type: ignore[method-assign]
        debugger._trace(frame, "line", None)
        return stops

    def test_breakpoint_hit_on_mapped_line(self, debugger, lm_file):
        filename = os.path.abspath(lm_file)
        debugger.line_maps[filename] = {10: 5}
        debugger.breakpoints[filename] = {5}
        frame = MockFrame(10, filename)

        stops = self._trace_line(debugger, frame)

        assert len(stops) == 1
        assert stops[0]["reason"] == "breakpoint"
        assert stops[0]["lineno"] == 5

    def test_no_stop_when_breakpoint_not_on_current_line(self, debugger, lm_file):
        filename = os.path.abspath(lm_file)
        debugger.line_maps[filename] = {10: 5}
        debugger.breakpoints[filename] = {99}
        frame = MockFrame(10, filename)

        stops = self._trace_line(debugger, frame)

        assert stops == []

    def test_step_in_stops_on_every_line(self, debugger, lm_file):
        filename = os.path.abspath(lm_file)
        debugger.line_maps[filename] = {3: 3}
        debugger.step_mode = "stepIn"
        frame = MockFrame(3, filename)

        stops = self._trace_line(debugger, frame)

        assert len(stops) == 1
        assert stops[0]["reason"] == "step"

    def test_next_stops_only_at_same_or_shallower_depth(self, debugger, lm_file):
        filename = os.path.abspath(lm_file)
        debugger.line_maps[filename] = {3: 3}
        debugger.step_mode = "next"
        debugger.step_depth = 1
        debugger.current_depth = 1
        frame = MockFrame(3, filename)

        stops_at_same_depth = self._trace_line(debugger, frame)
        assert len(stops_at_same_depth) == 1

        debugger.current_depth = 2
        stops_at_deeper_depth = self._trace_line(debugger, frame)
        assert stops_at_deeper_depth == []

    def test_step_out_stops_when_depth_decreases(self, debugger, lm_file):
        filename = os.path.abspath(lm_file)
        debugger.line_maps[filename] = {1: 1}
        debugger.step_mode = "stepOut"
        debugger.step_depth = 2
        debugger.current_depth = 2
        frame = MockFrame(1, filename)

        stops: list[dict[str, Any]] = []

        def capture_stop(frame_obj, reason, lineno=None, filename=None):
            stops.append({"reason": reason, "filename": filename})

        debugger._stop = capture_stop  # type: ignore[method-assign]
        debugger._trace(frame, "return", None)

        assert len(stops) == 1
        assert stops[0]["reason"] == "step"
        assert debugger.step_mode is None
        assert debugger.current_depth == 1

    def test_call_and_return_update_depth(self, debugger, lm_file):
        filename = os.path.abspath(lm_file)
        debugger.line_maps[filename] = {1: 1}
        frame = MockFrame(1, filename)

        debugger._trace(frame, "call", None)
        assert debugger.current_depth == 1

        debugger._trace(frame, "return", None)
        assert debugger.current_depth == 0


class TestJsonProtocol:
    def test_set_breakpoints_command(self, lm_file):
        debugger = LamiaDebugger(lm_file, json_mode=False)
        abs_path = os.path.abspath(lm_file)
        debugger.io = QueueProtocolIO([
            {"command": "setBreakpoints", "file": lm_file, "lines": [3, 7]},
            {"command": "disconnect"},
        ])

        debugger._json_command_loop()

        assert debugger.breakpoints[abs_path] == {3, 7}
        response = next(
            msg for msg in debugger.io.responses
            if msg.get("command") == "setBreakpoints"
        )
        assert response == {
            "type": "response",
            "command": "setBreakpoints",
            "breakpoints": [3, 7],
        }

    def test_get_variables_command(self, lm_file):
        debugger = LamiaDebugger(lm_file, json_mode=False)
        debugger.current_frame = MockFrame(
            1,
            lm_file,
            f_locals={"items": {"a": 1}, "count": 42},
        )
        debugger.io = QueueProtocolIO([
            {"command": "getVariables", "reference": 1},
            {"command": "disconnect"},
        ])

        debugger._json_command_loop()

        response = next(
            msg for msg in debugger.io.responses
            if msg.get("command") == "getVariables"
        )
        variables = response["variables"]
        names = {var["name"] for var in variables}
        assert names == {"items", "count"}
        items_var = next(var for var in variables if var["name"] == "items")
        assert items_var["variablesReference"] > 0
        count_var = next(var for var in variables if var["name"] == "count")
        assert count_var["variablesReference"] == 0

    def test_continue_clears_step_mode(self, lm_file):
        debugger = LamiaDebugger(lm_file, json_mode=False)
        debugger.step_mode = "next"
        debugger.paused.clear()
        debugger.io = QueueProtocolIO([
            {"command": "continue"},
            {"command": "disconnect"},
        ])

        debugger._json_command_loop()

        assert debugger.step_mode is None
        assert debugger.paused.is_set()


class TestVariableInspection:
    def test_variables_for_dict_list_tuple_set(self, debugger):
        dict_vars = debugger._variables_for_value({"a": 1, "b": 2})
        assert {v["name"] for v in dict_vars} == {"a", "b"}
        assert all(v["variablesReference"] == 0 for v in dict_vars)

        list_vars = debugger._variables_for_value([10, 20])
        assert [v["name"] for v in list_vars] == ["[0]", "[1]"]

        tuple_vars = debugger._variables_for_value((True, False))
        assert [v["name"] for v in tuple_vars] == ["[0]", "[1]"]

        set_vars = debugger._variables_for_value({1, 2})
        assert len(set_vars) == 2
        assert all(v["name"].startswith("[") for v in set_vars)

    def test_variables_for_pydantic_model(self, debugger):
        model = SampleModel(name="widget", count=3)
        variables = debugger._variables_for_value(model)

        by_name = {var["name"]: var for var in variables}
        assert by_name["name"]["value"] == "'widget'"
        assert by_name["count"]["value"] == "3"
        assert by_name["name"]["variablesReference"] == 0

    def test_collect_variables_expands_nested_values(self, debugger, lm_file):
        debugger.current_frame = MockFrame(
            1,
            lm_file,
            f_locals={
                "data": {"key": "value"},
                "empty_list": [],
                "model": SampleModel(name="x", count=1),
            },
        )

        top_level = debugger._collect_variables(reference=1)
        data_var = next(v for v in top_level if v["name"] == "data")
        empty_list_var = next(v for v in top_level if v["name"] == "empty_list")
        model_var = next(v for v in top_level if v["name"] == "model")

        assert data_var["variablesReference"] > 0
        assert empty_list_var["variablesReference"] == 0
        assert model_var["variablesReference"] > 0

        nested = debugger._collect_variables(reference=data_var["variablesReference"])
        assert len(nested) == 1
        assert nested[0]["name"] == "key"
        assert nested[0]["value"] == "'value'"

    def test_collect_variables_plain_object_attrs(self, debugger, lm_file):
        debugger.current_frame = MockFrame(
            1,
            lm_file,
            f_locals={"obj": PlainObject(label="test", value=7)},
        )

        top_level = debugger._collect_variables(reference=1)
        obj_var = next(v for v in top_level if v["name"] == "obj")
        assert obj_var["variablesReference"] > 0

        attrs = debugger._collect_variables(reference=obj_var["variablesReference"])
        by_name = {v["name"]: v for v in attrs}
        assert by_name["label"]["value"] == "'test'"
        assert by_name["value"]["value"] == "7"

    def test_collect_variables_returns_empty_without_frame(self, debugger):
        assert debugger._collect_variables() == []

    def test_collect_variables_unknown_reference(self, debugger, lm_file):
        debugger.current_frame = MockFrame(1, lm_file, f_locals={"x": 1})
        debugger._collect_variables(reference=1)
        assert debugger._collect_variables(reference=999) == []
