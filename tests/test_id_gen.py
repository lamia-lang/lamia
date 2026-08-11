"""Tests for lamia.id_gen module."""

from unittest import mock

from lamia.id_gen import (
    generate_unique_id,
    generate_deterministic_id,
    _get_git_remote_origin,
)


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


class TestGitRemoteStableIds:
    """IDs must be stable across machines when inside a git repo."""

    def _mock_git_remote(self, url):
        """Return a patcher that makes _get_git_remote_origin return *url*."""
        return mock.patch(
            "lamia.id_gen._get_git_remote_origin", return_value=url,
        )

    def test_same_repo_different_checkout_paths_same_id(self):
        url = "https://github.com/lamia-lang/lamia"
        with self._mock_git_remote(url):
            a = generate_deterministic_id("script.lm", "/home/runner/work/lamia/lamia")
            b = generate_deterministic_id("script.lm", "/Users/sergey/projects/lamia")
        assert a == b

    def test_different_repos_different_ids(self):
        with mock.patch(
            "lamia.id_gen._get_git_remote_origin",
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
        with self._mock_git_remote(None):
            a = generate_deterministic_id("script.lm", "/home/sergey/project_a")
            b = generate_deterministic_id("script.lm", "/home/sergey/project_b")
        assert a != b

    def test_git_url_normalized_trailing_dot_git(self):
        """URLs with/without .git suffix produce the same canonical result."""
        from lamia.id_gen import _get_git_remote_origin as fn
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=0,
                stdout="https://github.com/lamia-lang/lamia.git\n",
            )
            a = fn("/any/path")
            mock_run.return_value = mock.Mock(
                returncode=0,
                stdout="https://github.com/lamia-lang/lamia\n",
            )
            b = fn("/any/path")
        assert a == b

    def test_ssh_and_https_forms_map_to_same_repo_identity(self):
        from lamia.id_gen import _canonical_git_remote

        https_form = _canonical_git_remote("https://github.com/lamia-lang/lamia.git")
        ssh_form = _canonical_git_remote("git@github.com:lamia-lang/lamia.git")
        assert https_form == ssh_form == "github.com/lamia-lang/lamia"

    def test_enterprise_remote_supported(self):
        from lamia.id_gen import _canonical_git_remote

        url = "ssh://git@github.acme.internal/platform/agent-repo.git"
        assert _canonical_git_remote(url) == "github.acme.internal/platform/agent-repo"

    def test_non_default_port_enterprise_remote_supported(self):
        from lamia.id_gen import _canonical_git_remote

        url = "https://ghe.acme.internal:8443/team/repo.git"
        assert _canonical_git_remote(url) == "ghe.acme.internal:8443/team/repo"

    def test_local_file_remote_not_used_for_shared_identity(self):
        from lamia.id_gen import _canonical_git_remote

        assert _canonical_git_remote("file:///tmp/repo.git") is None
