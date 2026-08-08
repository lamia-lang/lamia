"""Tests for lamia.id_gen module."""

from lamia.id_gen import generate_unique_id


class TestGenerateUniqueId:
    def test_deterministic(self):
        a = generate_unique_id("x.lm", "/p")
        b = generate_unique_id("x.lm", "/p")
        assert a == b

    def test_twelve_char_hex(self):
        result = generate_unique_id("script.lm", "/home/user/project")
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_different_scripts_different_ids(self):
        a = generate_unique_id("a.lm", "/p")
        b = generate_unique_id("b.lm", "/p")
        assert a != b

    def test_different_roots_different_ids(self):
        a = generate_unique_id("a.lm", "/p1")
        b = generate_unique_id("a.lm", "/p2")
        assert a != b

    def test_same_for_schedules_and_triggers(self):
        """Same script + root always produces the same ID regardless of context."""
        id1 = generate_unique_id("task.lm", "/project/a")
        id2 = generate_unique_id("task.lm", "/project/a")
        assert id1 == id2
