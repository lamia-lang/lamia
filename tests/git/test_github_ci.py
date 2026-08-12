"""Tests for the GitHub Actions variable REST calls."""

import json
import urllib.error
from io import BytesIO

import pytest

from lamia.git import github_ci


class FakeResponse:
    """Minimal stand-in for the object urlopen returns."""

    def __init__(self, payload=None):
        self._payload = json.dumps(payload or {}).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code, url="https://api.github.com/x"):
    return urllib.error.HTTPError(url, code, "err", {}, BytesIO(b"{}"))


class RecordedCalls(list):
    """Requests urlopen received, plus the responses it should hand back."""

    def __init__(self):
        super().__init__()
        self.outcomes = []


@pytest.fixture
def calls(monkeypatch):
    """Record every request urlopen would send."""
    recorded = RecordedCalls()

    def fake_urlopen(req, timeout=None):
        recorded.append(req)
        outcome = recorded.outcomes.pop(0) if recorded.outcomes else FakeResponse()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(github_ci.urllib.request, "urlopen", fake_urlopen)
    return recorded


class TestUpsertRepoVariable:
    def test_creates_with_post_to_collection(self, calls):
        github_ci._upsert_repo_variable(
            token="t", owner="acme", repo="widgets", name="V", value="1",
        )

        assert len(calls) == 1
        req = calls[0]
        assert req.get_method() == "POST"
        assert req.full_url == (
            "https://api.github.com/repos/acme/widgets/actions/variables"
        )
        assert json.loads(req.data) == {"name": "V", "value": "1"}

    def test_falls_back_to_patch_when_variable_exists(self, calls):
        calls.outcomes.extend([http_error(409), FakeResponse()])

        github_ci._upsert_repo_variable(
            token="t", owner="acme", repo="widgets", name="V", value="2",
        )

        assert [c.get_method() for c in calls] == ["POST", "PATCH"]
        assert calls[1].full_url == (
            "https://api.github.com/repos/acme/widgets/actions/variables/V"
        )
        assert json.loads(calls[1].data) == {"name": "V", "value": "2"}

    def test_never_uses_put(self, calls):
        """PUT is the secrets API; variables reject it."""
        calls.outcomes.extend([http_error(409), FakeResponse()])

        github_ci._upsert_repo_variable(
            token="t", owner="acme", repo="widgets", name="V", value="2",
        )

        assert "PUT" not in [c.get_method() for c in calls]

    def test_sends_api_version_and_auth_headers(self, calls):
        github_ci._upsert_repo_variable(
            token="secret-token", owner="acme", repo="widgets", name="V", value="1",
        )

        headers = {k.lower(): v for k, v in calls[0].header_items()}
        assert headers["authorization"] == "Bearer secret-token"
        assert headers["x-github-api-version"] == "2022-11-28"
        assert headers["content-type"] == "application/json"

    @pytest.mark.parametrize("code", [403, 404])
    def test_missing_installation_gets_actionable_error(self, calls, code):
        calls.outcomes.append(http_error(code))

        with pytest.raises(RuntimeError, match="may not be installed"):
            github_ci._upsert_repo_variable(
                token="t", owner="acme", repo="widgets", name="V", value="1",
            )

    def test_other_http_errors_propagate(self, calls):
        calls.outcomes.append(http_error(500))

        with pytest.raises(RuntimeError, match="HTTP 500"):
            github_ci._upsert_repo_variable(
                token="t", owner="acme", repo="widgets", name="V", value="1",
            )

    def test_patch_failure_is_reported(self, calls):
        calls.outcomes.extend([http_error(409), http_error(422)])

        with pytest.raises(RuntimeError, match="HTTP 422"):
            github_ci._upsert_repo_variable(
                token="t", owner="acme", repo="widgets", name="V", value="1",
            )


class TestGetRepoVariable:
    def test_reads_value(self, calls):
        calls.outcomes.append(FakeResponse({"name": "V", "value": "hello"}))

        value = github_ci._get_repo_variable(
            token="t", owner="acme", repo="widgets", name="V",
        )

        assert value == "hello"
        assert calls[0].get_method() == "GET"

    def test_missing_value_raises(self, calls):
        calls.outcomes.append(FakeResponse({"name": "V"}))

        with pytest.raises(RuntimeError, match="missing after write"):
            github_ci._get_repo_variable(
                token="t", owner="acme", repo="widgets", name="V",
            )


class TestSetRepositoryCiVariables:
    def test_writes_and_verifies_both_variables(self, monkeypatch):
        writes = {}
        monkeypatch.setattr(github_ci, "_device_flow_token", lambda: "tok")
        monkeypatch.setattr(
            github_ci, "_upsert_repo_variable",
            lambda *, token, owner, repo, name, value: writes.__setitem__(name, value),
        )
        monkeypatch.setattr(
            github_ci, "_get_repo_variable",
            lambda *, token, owner, repo, name: writes[name],
        )

        github_ci.set_repository_ci_variables(
            repo_url="https://github.com/acme/widgets.git",
            connection_id="v1-123456-abc123def456",
        )

        assert writes == {
            "LAMIA_CONNECTED_REPO": "https://github.com/acme/widgets.git",
            "LAMIA_CONNECTION_ID": "v1-123456-abc123def456",
        }

    def test_readback_mismatch_fails(self, monkeypatch):
        monkeypatch.setattr(github_ci, "_device_flow_token", lambda: "tok")
        monkeypatch.setattr(
            github_ci, "_upsert_repo_variable",
            lambda **kwargs: None,
        )
        monkeypatch.setattr(
            github_ci, "_get_repo_variable",
            lambda *, token, owner, repo, name: "tampered",
        )

        with pytest.raises(RuntimeError, match="Failed to verify"):
            github_ci.set_repository_ci_variables(
                repo_url="https://github.com/acme/widgets.git",
                connection_id="v1-123456-abc123def456",
            )


class TestParseOwnerRepo:
    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/acme/widgets.git",
            "https://github.com/acme/widgets",
            "git@github.com:acme/widgets.git",
            "  https://github.com/acme/widgets/  ",
        ],
    )
    def test_supported_remote_forms(self, url):
        assert github_ci._parse_owner_repo(url) == ("acme", "widgets")

    def test_rejects_remote_without_owner(self):
        with pytest.raises(RuntimeError, match="Cannot parse owner/repo"):
            github_ci._parse_owner_repo("https://github.com/widgets")


class TestDeviceFlowClientId:
    def test_defaults_to_bundled_app(self, monkeypatch):
        monkeypatch.delenv("LAMIA_GITHUB_OAUTH_CLIENT_ID", raising=False)
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["body"] = req.data.decode()
            raise urllib.error.URLError("stop here")

        monkeypatch.setattr(github_ci.urllib.request, "urlopen", fake_urlopen)

        with pytest.raises(RuntimeError):
            github_ci._device_flow_token()

        assert f"client_id={github_ci._DEFAULT_CLIENT_ID}" in captured["body"]

    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("LAMIA_GITHUB_OAUTH_CLIENT_ID", "Iv23liOVERRIDE")
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["body"] = req.data.decode()
            raise urllib.error.URLError("stop here")

        monkeypatch.setattr(github_ci.urllib.request, "urlopen", fake_urlopen)

        with pytest.raises(RuntimeError):
            github_ci._device_flow_token()

        assert "client_id=Iv23liOVERRIDE" in captured["body"]
