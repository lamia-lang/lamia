"""Tests for lamia.git.remote — canonical identity parsing and git remote detection."""

from unittest import mock

from lamia.git.remote import (
    canonical_remote_identity,
    get_canonical_remote,
    get_remote_origin,
)


class TestCanonicalRemoteIdentity:
    """canonical_remote_identity must produce host/path for any network remote."""

    def test_https_url(self):
        assert (
            canonical_remote_identity("https://github.com/lamia-lang/lamia.git")
            == "github.com/lamia-lang/lamia"
        )

    def test_https_url_without_dot_git(self):
        assert (
            canonical_remote_identity("https://github.com/lamia-lang/lamia")
            == "github.com/lamia-lang/lamia"
        )

    def test_ssh_url(self):
        assert (
            canonical_remote_identity("ssh://git@github.com/lamia-lang/lamia.git")
            == "github.com/lamia-lang/lamia"
        )

    def test_scp_syntax(self):
        assert (
            canonical_remote_identity("git@github.com:lamia-lang/lamia.git")
            == "github.com/lamia-lang/lamia"
        )

    def test_https_and_ssh_and_scp_all_match(self):
        urls = [
            "https://github.com/lamia-lang/lamia.git",
            "ssh://git@github.com/lamia-lang/lamia.git",
            "git@github.com:lamia-lang/lamia.git",
        ]
        identities = {canonical_remote_identity(u) for u in urls}
        assert len(identities) == 1
        assert identities.pop() == "github.com/lamia-lang/lamia"

    def test_enterprise_host(self):
        url = "ssh://git@github.acme.internal/platform/agent-repo.git"
        assert canonical_remote_identity(url) == "github.acme.internal/platform/agent-repo"

    def test_enterprise_non_default_port(self):
        url = "https://ghe.acme.internal:8443/team/repo.git"
        assert canonical_remote_identity(url) == "ghe.acme.internal:8443/team/repo"

    def test_gitlab_url(self):
        url = "https://gitlab.com/myorg/myrepo.git"
        assert canonical_remote_identity(url) == "gitlab.com/myorg/myrepo"

    def test_file_url_returns_none(self):
        assert canonical_remote_identity("file:///tmp/repo.git") is None

    def test_empty_string_returns_none(self):
        assert canonical_remote_identity("") is None

    def test_trailing_slash_stripped(self):
        url = "https://github.com/lamia-lang/lamia/"
        assert canonical_remote_identity(url) == "github.com/lamia-lang/lamia"

    def test_case_insensitive_host(self):
        a = canonical_remote_identity("https://GitHub.COM/Lamia-Lang/Lamia")
        assert a is not None
        assert a.startswith("github.com/")


class TestGetRemoteOrigin:
    def test_returns_url_when_git_repo(self):
        with mock.patch("lamia.git.remote.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=0,
                stdout="https://github.com/lamia-lang/lamia.git\n",
            )
            assert get_remote_origin("/some/path") == "https://github.com/lamia-lang/lamia.git"

    def test_returns_none_when_not_git_repo(self):
        with mock.patch("lamia.git.remote.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=128, stdout="")
            assert get_remote_origin("/some/path") is None

    def test_returns_none_on_timeout(self):
        with mock.patch("lamia.git.remote.subprocess.run", side_effect=TimeoutError):
            assert get_remote_origin("/some/path") is None


class TestGetCanonicalRemote:
    def test_combines_origin_and_canonicalization(self):
        with mock.patch("lamia.git.remote.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=0,
                stdout="git@github.com:lamia-lang/lamia.git\n",
            )
            assert get_canonical_remote("/any") == "github.com/lamia-lang/lamia"

    def test_returns_none_for_non_git_dir(self):
        with mock.patch("lamia.git.remote.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=128, stdout="")
            assert get_canonical_remote("/any") is None
