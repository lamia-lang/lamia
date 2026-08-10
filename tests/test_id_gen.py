"""Tests for lamia.id_gen module."""

from lamia.id_gen import generate_unique_id, generate_deterministic_id


class TestGenerateUniqueId:
    def test_bare_hex_format(self):
        result = generate_unique_id()
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_each_call_is_unique(self):
        ids = {generate_unique_id() for _ in range(100)}
        assert len(ids) == 100


class TestGenerateDeterministicId:
    def test_bare_hex_format(self):
        result = generate_deterministic_id("script.lm", "/home/user/project")
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_inputs_same_output(self):
        a = generate_deterministic_id("script.lm", "/home/user/project")
        b = generate_deterministic_id("script.lm", "/home/user/project")
        assert a == b

    def test_different_script_different_id(self):
        a = generate_deterministic_id("script_a.lm", "/home/user/project")
        b = generate_deterministic_id("script_b.lm", "/home/user/project")
        assert a != b

    def test_different_project_different_id(self):
        a = generate_deterministic_id("script.lm", "/home/user/project_a")
        b = generate_deterministic_id("script.lm", "/home/user/project_b")
        assert a != b
