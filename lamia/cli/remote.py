"""Handle `lamia <script> --remote` — one-shot remote cloud execution."""

import ast
import hashlib
import sys
from dataclasses import dataclass, asdict, fields
from pathlib import Path
from typing import Optional

from lamia.interpreter.detectors import LLMCommandDetector
from lamia.interpreter.ast_analyzer import ActionNamespaceAnalyzer
from lamia.interpreter.commands import WebCommand, FileCommand

SCRIPT_CAPABILITY_FIELDS = (
    "uses_llm",
    "uses_browser",
    "uses_files",
    "uses_file_context",
)


@dataclass
class ScriptCapabilities:
    """Cloud-agnostic metadata about what a .lm script uses."""

    uses_llm: bool = False
    uses_browser: bool = False
    uses_files: bool = False
    uses_file_context: bool = False


def script_capability_field_names() -> tuple[str, ...]:
    """Return ordered ScriptCapabilities field names for contract tests."""
    return tuple(field.name for field in fields(ScriptCapabilities))


def analyze_script(script_path: Path) -> ScriptCapabilities:
    """Analyze a .lm script using existing Lamia AST infrastructure.

    Uses LLMCommandDetector to find resolved LLM commands and
    ActionNamespaceAnalyzer to detect web/file namespace usage.
    """
    try:
        source = script_path.read_text()
    except OSError:
        return ScriptCapabilities()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ScriptCapabilities()

    llm_functions = LLMCommandDetector().detect_commands(source)

    ns_analyzer = ActionNamespaceAnalyzer()
    ns_analyzer.visit(tree)

    return ScriptCapabilities(
        uses_llm=len(llm_functions) > 0,
        uses_browser=(
            WebCommand.__name__ in ns_analyzer.used_types
            or "web" in ns_analyzer.used_namespaces
            or "session" in ns_analyzer.used_namespaces
        ),
        uses_files=(
            FileCommand.__name__ in ns_analyzer.used_types
            or "file" in ns_analyzer.used_namespaces
        ),
        uses_file_context="files" in ns_analyzer.used_namespaces,
    )


def handle_remote_run(
    script: str,
    project_root: str,
    config: Optional[dict],
    verbose: bool,
) -> None:
    """Execute a .lm script remotely and report results."""
    if not script:
        print("Error: --remote requires a script file", file=sys.stderr)
        sys.exit(1)

    try:
        from lamia_cloud.gcp.deployer import (
            collect_project_files, deployment_name, deploy, run_job, fetch_execution_logs,
            get_deployed_source_hash, set_deployed_source_hash,
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
    run_name = _slugify(script_name)
    target = deployment_name(run_name)

    print(f"Remote execution: {script_name}", file=sys.stderr)

    capabilities = analyze_script(root / script_name)

    source_hash = _compute_source_hash(root, collect_project_files)
    deployed_hash = get_deployed_source_hash(project_id, location, target)

    if source_hash == deployed_hash:
        print("  Container up to date, skipping build.", file=sys.stderr)
    else:
        print("  Building and deploying...", file=sys.stderr)
        deploy(
            project_id=project_id,
            location=location,
            project_root=root,
            script_name=script_name,
            name=run_name,
            capabilities=asdict(capabilities),
        )
        set_deployed_source_hash(project_id, location, target, source_hash)

    print("  Running...", file=sys.stderr)
    result = run_job(
        project_id=project_id,
        location=location,
        target=target,
        verbose=verbose,
    )

    stdout, stderr = fetch_execution_logs(
        project_id=project_id,
        target=target,
        execution_name=result.get("execution_name", ""),
    )

    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)

    exit_code = result.get("exit_code", 1)
    elapsed = result.get("elapsed_seconds", 0)
    logs_url = result.get("logs_url", "")

    if elapsed:
        print(f"\n  Completed in {elapsed:.1f}s", file=sys.stderr)
    if logs_url:
        print(f"  Logs: {logs_url}", file=sys.stderr)

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


