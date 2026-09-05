from lamia.tools.loop import _exceeds_call_limit


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
