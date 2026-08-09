"""Tests for lamia.id_gen — bare 8-hex ID generation."""

from lamia.id_gen import generate_id, generate_unique_id


class TestGenerateId:
    def test_bare_hex_format(self):
        result = generate_id()
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_unique(self):
        a = generate_id()
        b = generate_id()
        assert a != b

    def test_same_as_generate_unique_id(self):
        assert generate_id is generate_unique_id
