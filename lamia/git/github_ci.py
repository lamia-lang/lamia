"""GitHub CI variable setup via REST API and device flow."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


_GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_API_BASE = "https://api.github.com"

_LAMIA_APP_SLUG = "lamia-cloud-connect"
_LAMIA_APP_INSTALL_URL = f"https://github.com/apps/{_LAMIA_APP_SLUG}/installations/new"

# Overridden by LAMIA_GITHUB_OAUTH_CLIENT_ID to target a different app.
_DEFAULT_CLIENT_ID = "Iv23liWCpxdsyPLeeOzx"


def set_repository_ci_variables(
    *,
    repo_url: str,
    connection_id: str,
) -> None:
    """Authorize via GitHub device flow and upsert required repo variables.

    Raises RuntimeError on any failure; callers should fail the command and
    ask users to rerun `lamia cloud connect`.
    """
    owner, repo = _parse_owner_repo(repo_url)
    token = _device_flow_token()

    name = "LAMIA_CONNECTION_ID"
    _upsert_repo_variable(
        token=token, owner=owner, repo=repo, name=name, value=connection_id,
    )
    actual = _get_repo_variable(token=token, owner=owner, repo=repo, name=name)
    if actual != connection_id:
        raise RuntimeError(f"Failed to verify GitHub variable {name}")


def _parse_owner_repo(repo_url: str) -> tuple[str, str]:
    raw = repo_url.strip()
    if "@" in raw and ":" in raw and raw.startswith("git@"):
        path = raw.split(":", 1)[1]
    else:
        parsed = urllib.parse.urlparse(raw)
        path = parsed.path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        raise RuntimeError(f"Cannot parse owner/repo from git remote: {repo_url}")
    return parts[0], parts[1]


def _device_flow_token() -> str:
    client_id = (
        os.environ.get("LAMIA_GITHUB_OAUTH_CLIENT_ID", "").strip() or _DEFAULT_CLIENT_ID
    )

    payload = urllib.parse.urlencode({"client_id": client_id}).encode()
    req = urllib.request.Request(
        _GITHUB_DEVICE_CODE_URL,
        data=payload,
        headers={"Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub device-code request failed: {exc}") from exc

    device_code = data.get("device_code")
    user_code = data.get("user_code")
    verify_uri = data.get("verification_uri")
    interval = int(data.get("interval", 5))
    expires_in = int(data.get("expires_in", 900))
    if not device_code or not user_code or not verify_uri:
        raise RuntimeError("GitHub did not return a valid device-flow payload")

    print("\nGitHub authorization required.")
    print(f"1) Open: {verify_uri}")
    print(f"2) Enter code: {user_code}")
    print("Waiting for authorization...")

    started = time.time()
    while time.time() - started < expires_in:
        payload = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            }
        ).encode()
        token_req = urllib.request.Request(
            _GITHUB_TOKEN_URL,
            data=payload,
            headers={"Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(token_req, timeout=20) as resp:
                token_data = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            raise RuntimeError(f"GitHub token polling failed: {exc}") from exc

        access_token = token_data.get("access_token")
        if access_token:
            return access_token

        err = token_data.get("error")
        if err == "authorization_pending":
            time.sleep(interval)
            continue
        if err == "slow_down":
            interval += 5
            time.sleep(interval)
            continue
        if err == "access_denied":
            raise RuntimeError("GitHub authorization denied")
        if err == "expired_token":
            raise RuntimeError("GitHub authorization timed out")
        raise RuntimeError(f"GitHub token error: {err or 'unknown'}")

    raise RuntimeError("GitHub device-flow authorization timed out")


def _upsert_repo_variable(
    *,
    token: str,
    owner: str,
    repo: str,
    name: str,
    value: str,
) -> None:
    """Create the variable, falling back to PATCH on 409 when it exists."""
    body = json.dumps({"name": name, "value": value}).encode()
    try:
        _api_request(
            token=token,
            url=f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/actions/variables",
            method="POST",
            body=body,
        )
        return
    except urllib.error.HTTPError as exc:
        if exc.code != 409:
            raise RuntimeError(_write_error(name, owner, repo, exc)) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to set variable {name}: {exc}") from exc

    try:
        _api_request(
            token=token,
            url=f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/actions/variables/{name}",
            method="PATCH",
            body=body,
        )
    except urllib.error.HTTPError as exc:
        raise RuntimeError(_write_error(name, owner, repo, exc)) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to set variable {name}: {exc}") from exc


def _write_error(name: str, owner: str, repo: str, exc: urllib.error.HTTPError) -> str:
    reason = exc.read().decode("utf-8", errors="ignore")
    if exc.code in (403, 404):
        return (
            f"Failed to set variable {name}: HTTP {exc.code} {reason}\n"
            f"The Lamia Cloud Connect GitHub App is not installed on {owner}/{repo}, "
            "or its installation lacks read/write access to Actions variables.\n"
            f"Install it for this repository at {_LAMIA_APP_INSTALL_URL} "
            "then rerun `lamia cloud connect`."
        )
    return f"Failed to set variable {name}: HTTP {exc.code} {reason}"


def _api_request(*, token: str, url: str, method: str, body: bytes | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    return urllib.request.urlopen(req, timeout=20)


def _get_repo_variable(*, token: str, owner: str, repo: str, name: str) -> str:
    url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/actions/variables/{name}"
    try:
        with _api_request(token=token, url=url, method="GET") as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        reason = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Failed to read variable {name}: HTTP {exc.code} {reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to read variable {name}: {exc}") from exc
    value = data.get("value")
    if value is None:
        raise RuntimeError(f"GitHub variable {name} missing after write")
    return value
