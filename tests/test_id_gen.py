"""Tests for lamia.id_gen module."""

from unittest import mock

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


class TestDeterministicIdUsesGitRemote:
    """Deterministic IDs must be stable across machines when inside a git repo."""

    def _mock_canonical(self, val):
        return mock.patch("lamia.id_gen.get_canonical_remote", return_value=val)

    def test_same_repo_different_checkout_paths_same_id(self):
        with self._mock_canonical("github.com/lamia-lang/lamia"):
            a = generate_deterministic_id("script.lm", "/home/runner/work/lamia/lamia")
            b = generate_deterministic_id("script.lm", "/Users/sergey/projects/lamia")
        assert a == b

    def test_different_repos_different_ids(self):
        with mock.patch(
            "lamia.id_gen.get_canonical_remote",
            side_effect=lambda p: (
                "github.com/lamia-lang/lamia"
                if p.endswith("/lamia") else
                "github.com/lamia-lang/lamia-examples"
            ),
        ):
            a = generate_deterministic_id("script.lm", "/home/sergey/lamia")
            b = generate_deterministic_id("script.lm", "/home/sergey/lamia-examples")
        assert a != b

    def test_no_git_falls_back_to_project_root(self):
        with self._mock_canonical(None):
            a = generate_deterministic_id("script.lm", "/home/sergey/project_a")
            b = generate_deterministic_id("script.lm", "/home/sergey/project_b")
        assert a != b
