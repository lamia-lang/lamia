"""Handle `lamia <script> --remote` — one-shot cloud execution."""

import hashlib
import json
import sys
from pathlib import Path
from typing import Optional


def handle_remote_run(
    script: str,
    project_root: str,
    config: Optional[dict],
    verbose: bool,
) -> None:
    """Execute a .lm script on Cloud Run and stream output back."""
    if not script:
        print("Error: --remote requires a script file", file=sys.stderr)
        sys.exit(1)

    try:
        from lamia_cloud.gcp.deployer import (
            _collect_project_files, _service_name, deploy,
        )
    except ImportError:
        print(
            'Error: lamia-cloud not installed.\n'
            'Install with: pip install "lamia-lang[cloud]"',
            file=sys.stderr,
        )
        sys.exit(1)

    cloud_cfg = (config or {}).get("cloud", {})
    project_id = cloud_cfg.get("project_id")
    location = cloud_cfg.get("location", "us-central1")

    if not project_id:
        print(
            "Error: cloud.project_id not set in config.yaml.\n"
            "Add:\n  cloud:\n    project_id: your-gcp-project",
            file=sys.stderr,
        )
        sys.exit(1)

    root = Path(project_root)
    script_name = Path(script).name
    schedule_id = f"run-{_slugify(script_name)}"
    service_name = _service_name(schedule_id)

    print(f"Remote execution: {script_name}", file=sys.stderr)

    source_hash = _compute_source_hash(root, _collect_project_files)
    deployed_hash = _get_deployed_hash(project_id, location, service_name)

    if source_hash == deployed_hash:
        print("  Container up to date, skipping build.", file=sys.stderr)
        service_url = _get_service_url(project_id, location, service_name)
    else:
        print("  Building and deploying...", file=sys.stderr)
        service_url = deploy(
            project_id=project_id,
            location=location,
            project_root=root,
            script_name=script_name,
            schedule_id=schedule_id,
        )
        _set_deployed_hash(project_id, location, service_name, source_hash)

    print(f"  Invoking...", file=sys.stderr)
    result = _invoke_service(service_url, verbose)

    if result.get("stdout"):
        print(result["stdout"])
    if result.get("stderr"):
        print(result["stderr"], file=sys.stderr)

    exit_code = result.get("exit_code", 1)
    logs_url = _cloud_logging_url(project_id, service_name)
    print(f"\nCloud Logs: {logs_url}", file=sys.stderr)

    sys.exit(exit_code)


def _slugify(name: str) -> str:
    stem = Path(name).stem
    slug = "".join(c if c.isalnum() else "-" for c in stem.lower()).strip("-")
    return slug[:20]


def _compute_source_hash(project_root: Path, collect_fn) -> str:
    """SHA256 of all project source files for change detection."""
    hasher = hashlib.sha256()
    for f in sorted(collect_fn(project_root)):
        hasher.update(str(f.relative_to(project_root)).encode())
        hasher.update(f.read_bytes())
    return hasher.hexdigest()[:16]


def _get_deployed_hash(project_id: str, location: str, service_name: str) -> Optional[str]:
    """Read source hash from Cloud Run service labels (single metadata call)."""
    try:
        from google.cloud import run_v2
        client = run_v2.ServicesClient()
        name = f"projects/{project_id}/locations/{location}/services/{service_name}"
        service = client.get_service(request={"name": name})
        return (service.labels or {}).get("lamia-source-hash")
    except Exception:
        return None


def _set_deployed_hash(project_id: str, location: str, service_name: str, hash_val: str) -> None:
    """Store source hash as a label on the Cloud Run service."""
    try:
        from google.cloud import run_v2
        client = run_v2.ServicesClient()
        name = f"projects/{project_id}/locations/{location}/services/{service_name}"
        service = client.get_service(request={"name": name})
        if service.labels is None:
            service.labels = {}
        service.labels["lamia-source-hash"] = hash_val
        client.update_service(service=service)
    except Exception:
        pass


def _get_service_url(project_id: str, location: str, service_name: str) -> str:
    """Get the URL of an existing Cloud Run service."""
    from google.cloud import run_v2
    client = run_v2.ServicesClient()
    name = f"projects/{project_id}/locations/{location}/services/{service_name}"
    service = client.get_service(request={"name": name})
    return service.uri


def _invoke_service(url: str, verbose: bool) -> dict:
    """POST to the Cloud Run service with OIDC authentication."""
    import urllib.request

    token = _get_oidc_token(url)
    payload = json.dumps({"verbose": verbose}).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=600)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            return json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return {"exit_code": 1, "stderr": f"Cloud Run error ({e.code}): {body[:2000]}"}


def _get_oidc_token(audience: str) -> str:
    """Get an OIDC identity token for the Cloud Run service."""
    import google.auth.transport.requests
    from google.oauth2 import id_token

    request = google.auth.transport.requests.Request()
    return id_token.fetch_id_token(request, audience)


def _cloud_logging_url(project_id: str, service_name: str) -> str:
    import urllib.parse
    query = (
        f'resource.type="cloud_run_revision" '
        f'resource.labels.service_name="{service_name}"'
    )
    encoded = urllib.parse.quote(query)
    return f"https://console.cloud.google.com/logs/query;query={encoded}?project={project_id}"
