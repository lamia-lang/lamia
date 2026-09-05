from collections import deque

from lamia.tools.loop_detection import exceeds_call_limit, history_size


def test_unconfigured_tools_have_no_call_limit():
    history = deque()

    for _ in range(10):
        assert not exceeds_call_limit("read_file", {"path": "a.txt"}, {"write_file": 1}, history)

    assert len(history) == 0


def test_configured_tool_stops_after_its_call_cap():
    history = deque(maxlen=10)
    args = {"path": "a.txt"}

    assert not exceeds_call_limit("write_file", args, {"write_file": 2}, history)
    assert not exceeds_call_limit("write_file", args, {"write_file": 2}, history)
    assert exceeds_call_limit("write_file", args, {"write_file": 2}, history)


def test_different_arguments_do_not_count_as_repeats():
    history = deque(maxlen=10)

    for i in range(5):
        assert not exceeds_call_limit("write_file", {"path": f"file{i}.txt"}, {"write_file": 2}, history)


def test_one_revert_is_not_a_loop_but_a_second_one_is():
    history = deque(maxlen=10)
    write_a = {"path": "a.txt", "content": "original"}
    write_b = {"path": "b.txt", "content": "fix"}
    limits = {"write_file": 2}

    assert not exceeds_call_limit("write_file", write_a, limits, history)
    assert not exceeds_call_limit("write_file", write_b, limits, history)
    assert not exceeds_call_limit("write_file", write_a, limits, history)  # the revert
    assert not exceeds_call_limit("write_file", write_b, limits, history)
    assert exceeds_call_limit("write_file", write_a, limits, history)  # thrashing now


def test_repeat_outside_the_window_is_not_a_loop():
    history = deque(maxlen=10)
    write_a = {"path": "a.txt", "content": "original"}
    other = {"path": "other.txt", "content": "unrelated"}
    limits = {"write_file": 2}

    assert not exceeds_call_limit("write_file", write_a, limits, history)
    for i in range(6):
        assert not exceeds_call_limit("write_file", {**other, "content": f"unrelated{i}"}, limits, history)
    assert not exceeds_call_limit("write_file", write_a, limits, history)


def test_a_bigger_tool_limit_does_not_widen_a_smaller_tools_window():
    limits = {"write_file": 2, "read_file": 12}
    history = deque(maxlen=history_size(limits))
    write_a = {"path": "a.txt", "content": "original"}

    assert not exceeds_call_limit("write_file", write_a, limits, history)
    for i in range(6):
        assert not exceeds_call_limit("read_file", {"path": f"other{i}.txt"}, limits, history)
    assert not exceeds_call_limit("write_file", write_a, limits, history)
