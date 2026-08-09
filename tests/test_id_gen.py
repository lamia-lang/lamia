"""Tests for lamia.id_gen module."""

from lamia.id_gen import generate_unique_id


class TestGenerateUniqueId:
    def test_bare_hex_format(self):
        result = generate_unique_id()
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_each_call_is_unique(self):
        ids = {generate_unique_id() for _ in range(100)}
        assert len(ids) == 100
