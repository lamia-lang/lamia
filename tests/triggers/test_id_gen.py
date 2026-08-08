"""Tests for lamia.id_gen — shared ID generation for schedules and triggers."""

from lamia.id_gen import generate_id, slugify


class TestSlugify:
    def test_basic_underscore(self):
        assert slugify("publish_pins.lm") == "publish-pins"

    def test_complex_name(self):
        assert slugify("My Complex Script (v2).lm") == "my-complex-scrip"

    def test_empty_fallback(self):
        assert slugify("....") == "script"

    def test_no_extension(self):
        assert slugify("hello") == "hello"

    def test_truncates_long_names(self):
        result = slugify("very-long-script-name-that-goes-on-forever.lm")
        assert len(result) <= 16


class TestGenerateId:
    def test_deterministic(self):
        id1 = generate_id("test.lm", "/project/root")
        id2 = generate_id("test.lm", "/project/root")
        assert id1 == id2

    def test_different_projects_give_different_ids(self):
        id1 = generate_id("test.lm", "/project/a")
        id2 = generate_id("test.lm", "/project/b")
        assert id1 != id2

    def test_format(self):
        result = generate_id("pricing_reply.lm", "/home/user/proj")
        assert "-" in result
        parts = result.rsplit("-", 1)
        assert len(parts[1]) == 4

    def test_same_as_schedule_id(self):
        """Verify that trigger and schedule IDs use the same logic."""
        from lamia.scheduling.base import generate_schedule_id
        trigger_id = generate_id("test.lm", "/proj")
        schedule_id = generate_schedule_id("test.lm", "/proj")
        assert trigger_id == schedule_id
