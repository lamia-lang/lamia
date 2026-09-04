"""Unit tests for script analysis utilities (no cloud deps), plus integration
tests for the remote/trigger deploy paths with the lamia_cloud boundary mocked."""

import importlib.util
from unittest import mock

import pytest
from pathlib import Path

from lamia.cli.script_analysis import (
    ScriptCapabilities,
    analyze_script,
    script_capability_field_names,
)
from lamia.interpreter.ast_analyzer import extract_script_file_refs




def _gcp_connector(project_root):
    """Real GCP connector without reading config.yaml from disk."""
    from lamia_cloud.gcp.connect import GCPRepositoryConnector
    return GCPRepositoryConnector.from_config({"project_id": "proj"})


def _write_script(tmp_path: Path, name: str, content: str) -> Path:
    script_path = tmp_path / name
    script_path.write_text(content)
    return script_path


def _make_mock_deployer():
    """Create a mock deployer with sensible defaults for all CloudDeployer methods."""
    deployer = mock.MagicMock()
    deployer.deployment_name.side_effect = lambda name: f"lamia-{name}"
    deployer.collect_project_files.side_effect = lambda root: list(root.glob("*.lm"))
    deployer.get_deployed_source_hash.return_value = None
    deployer.set_deployed_source_hash.return_value = None
    deployer.sync_runtime_files.return_value = {"uploaded": 0, "skipped": 0, "overwrite_warnings": []}
    deployer.deploy.return_value = "lamia-task"
    deployer.run_job.return_value = {
        "exit_code": 0, "elapsed_seconds": 1.5,
        "logs_url": "https://logs.example", "execution_name": "exec-1",
    }
    deployer.fetch_execution_logs.return_value = ("", "")
    return deployer


@pytest.fixture(autouse=True)
def _stub_cloud_factories(monkeypatch):
    """Stub get_deployer, get_trigger_provider, and CI detection so tests never hit real GCP."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    if importlib.util.find_spec("lamia_cloud") is None:
        return
    import lamia.cli.remote as remote
    monkeypatch.setattr(remote, "get_deployer", lambda root: _make_mock_deployer())
    monkeypatch.setattr(remote, "get_trigger_provider", lambda root: mock.MagicMock())


def test_analyze_script_detects_llm_web_file_and_file_context(tmp_path):
    script = _write_script(
        tmp_path,
        "all_features.lm",
        """
def ask_user():
    "Summarize the latest status update"

def run():
    web.navigate("https://example.com")
    file.read("notes.txt")
    with files("docs/"):
        pass
""".strip(),
    )

    result = analyze_script(script)

    assert result.uses_llm is True
    assert result.uses_browser is True
    assert result.uses_files is True
    assert result.uses_file_context is True


def test_analyze_script_detects_no_capabilities_for_plain_script(tmp_path):
    script = _write_script(
        tmp_path,
        "plain.lm",
        """
def run():
    value = 1 + 1
    return value
""".strip(),
    )

    result = analyze_script(script)

    assert result.uses_llm is False
    assert result.uses_browser is False
    assert result.uses_files is False
    assert result.uses_file_context is False


def test_analyze_script_detects_only_llm(tmp_path):
    script = _write_script(
        tmp_path,
        "llm_only.lm",
        """
def ask_user():
    "Write a brief status summary"
""".strip(),
    )

    result = analyze_script(script)

    assert result.uses_llm is True
    assert result.uses_browser is False
    assert result.uses_files is False
    assert result.uses_file_context is False


def test_analyze_script_detects_only_browser(tmp_path):
    script = _write_script(
        tmp_path,
        "browser_only.lm",
        """
def run():
    web.navigate("https://example.com")
    web.click("Login")
""".strip(),
    )

    result = analyze_script(script)

    assert result.uses_llm is False
    assert result.uses_browser is True
    assert result.uses_files is False
    assert result.uses_file_context is False


def test_analyze_script_detects_only_files(tmp_path):
    script = _write_script(
        tmp_path,
        "files_only.lm",
        """
def run():
    data = file.read("data.csv")
    file.write("output.json", data)
""".strip(),
    )

    result = analyze_script(script)

    assert result.uses_llm is False
    assert result.uses_browser is False
    assert result.uses_files is True
    assert result.uses_file_context is False


def test_analyze_script_detects_only_file_context(tmp_path):
    script = _write_script(
        tmp_path,
        "file_context_only.lm",
        """
def run():
    with files("docs/"):
        pass
""".strip(),
    )

    result = analyze_script(script)

    assert result.uses_llm is False
    assert result.uses_browser is False
    assert result.uses_files is False
    assert result.uses_file_context is True


def test_analyze_script_syntax_error_falls_back_to_empty_capabilities(tmp_path):
    script = _write_script(
        tmp_path,
        "bad.lm",
        "def run(:\n    pass  # syntax error",
    )

    result = analyze_script(script)

    assert result.uses_llm is False
    assert result.uses_browser is False
    assert result.uses_files is False
    assert result.uses_file_context is False


def test_extract_file_refs_single_path(tmp_path):
    script = _write_script(
        tmp_path,
        "task.lm",
        'with files("data/report.csv"):\n    pass',
    )
    refs = extract_script_file_refs(script)
    assert refs == ["data/report.csv"]


def test_extract_file_refs_multiple_paths_same_block(tmp_path):
    script = _write_script(
        tmp_path,
        "task.lm",
        'with files("a.txt", "b.txt"):\n    pass',
    )
    refs = extract_script_file_refs(script)
    assert set(refs) == {"a.txt", "b.txt"}


def test_extract_file_refs_multiple_blocks(tmp_path):
    script = _write_script(
        tmp_path,
        "task.lm",
        'with files("a.txt"):\n    pass\nwith files("b.txt"):\n    pass',
    )
    refs = extract_script_file_refs(script)
    assert set(refs) == {"a.txt", "b.txt"}


def test_extract_file_refs_dynamic_arg_raises(tmp_path):
    script = _write_script(
        tmp_path,
        "task.lm",
        'path = "a.txt"\nwith files(path):\n    pass',
    )
    with pytest.raises(ValueError, match="literal strings"):
        extract_script_file_refs(script)


def test_extract_file_refs_no_files_blocks(tmp_path):
    script = _write_script(tmp_path, "task.lm", 'x = 1\nprint(x)')
    assert extract_script_file_refs(script) == []


@pytest.mark.integration
@pytest.mark.cloud
def test_script_capabilities_contract_field_names():
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    from lamia_cloud.contracts import SCRIPT_CAPABILITY_FIELDS

    field_names = script_capability_field_names()
    assert field_names == tuple(SCRIPT_CAPABILITY_FIELDS), (
        "ScriptCapabilities contract changed. If you add/rename/remove fields, "
        "update BOTH lamia.cli.script_analysis.ScriptCapabilities and "
        "lamia_cloud.contracts.SCRIPT_CAPABILITY_FIELDS."
    )


@pytest.mark.integration
@pytest.mark.cloud
def test_warn_about_file_uploads_prints_warning(capsys):
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    from lamia_cloud.contracts import FileSyncEntry
    from lamia.cli.remote import _warn_about_file_uploads

    entries = [
        FileSyncEntry(raw_path="docs/a.txt", resolved_path="/tmp/a.txt", bucket_key="docs/a.txt"),
        FileSyncEntry(raw_path="docs/b.txt", resolved_path="/tmp/b.txt", bucket_key="docs/b.txt"),
    ]
    _warn_about_file_uploads(entries)
    stderr = capsys.readouterr().err
    assert "will upload local files" in stderr
    assert "docs/a.txt" in stderr
    assert "docs/b.txt" in stderr


@pytest.mark.integration
@pytest.mark.cloud
def test_deploy_trigger_builds_plan_and_calls_provider_deploy(monkeypatch, tmp_path, capsys):
    """_deploy_trigger must build the right TriggerDeploymentPlan and call provider.deploy()."""
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    from lamia_cloud.types import TriggerDeploymentPlan, TriggerStage
    import lamia.cli.remote as remote

    stages = [
        TriggerStage(
            stage_index=0,
            trigger_method="email_received",
            trigger_config={"to": "pricing@company.com"},
            output_bindings=[],
            script_source="",
        )
    ]

    mock_provider = mock.MagicMock()
    mock_provider.deploy.return_value = "lamia-trigger-task"
    monkeypatch.setattr(remote, "get_trigger_provider", lambda root: mock_provider)

    remote._deploy_trigger("task.lm", tmp_path, stages)

    plan = mock_provider.deploy.call_args[0][0]
    assert isinstance(plan, TriggerDeploymentPlan)
    assert len(plan.name) == 12
    assert all(c in "0123456789abcdef" for c in plan.name)
    assert plan.mode == "reactive"
    assert plan.stages == stages
    assert plan.script_name == "task.lm"

    stderr = capsys.readouterr().err
    assert "Deployed: lamia-trigger-task" in stderr


@pytest.mark.integration
@pytest.mark.cloud
def test_deploy_trigger_same_script_same_name(monkeypatch, tmp_path):
    """Deploying the same script from the same project twice must produce the same plan name."""
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    from lamia_cloud.types import TriggerStage
    import lamia.cli.remote as remote

    stages = [
        TriggerStage(
            stage_index=0,
            trigger_method="email_received",
            trigger_config={},
            output_bindings=[],
            script_source="",
        )
    ]

    names = []
    for _ in range(2):
        mock_provider = mock.MagicMock()
        mock_provider.deploy.return_value = "lamia-trigger-task"
        monkeypatch.setattr(remote, "get_trigger_provider", lambda root: mock_provider)
        remote._deploy_trigger("task.lm", tmp_path, stages)
        names.append(mock_provider.deploy.call_args[0][0].name)

    assert names[0] == names[1], "same script + same project must produce identical name"


@pytest.mark.integration
@pytest.mark.cloud
def test_deploy_trigger_ids_differ_across_project_roots(monkeypatch, tmp_path):
    """The same script name in two projects must not deploy onto the same trigger."""
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    from lamia_cloud.types import TriggerStage
    import lamia.cli.remote as remote

    stages = [
        TriggerStage(
            stage_index=0,
            trigger_method="email_received",
            trigger_config={},
            output_bindings=[],
            script_source="",
        )
    ]

    names = []
    for project in ("alpha", "beta"):
        root = tmp_path / project
        root.mkdir()
        mock_provider = mock.MagicMock()
        monkeypatch.setattr(remote, "get_trigger_provider", lambda root, mp=mock_provider: mp)

        remote._deploy_trigger("task.lm", root, stages)
        names.append(mock_provider.deploy.call_args[0][0].name)

    assert names[0] != names[1]
    for n in names:
        assert len(n) == 12
        assert all(c in "0123456789abcdef" for c in n)


@pytest.mark.integration
@pytest.mark.cloud
def test_handle_remote_run_routes_to_deploy_trigger_when_script_has_triggers(monkeypatch, tmp_path):
    """handle_remote_run must detect trigger.* calls and hand off to _deploy_trigger."""
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    import lamia.cli.remote as remote

    (tmp_path / "config.yaml").write_text("cloud:\n  provider: gcp\n  project_id: proj\n")
    _write_script(tmp_path, "task.lm", "trigger.email_received(sender)")

    fake_stages = [mock.sentinel.stage]
    monkeypatch.setattr(remote, "extract_all_triggers", lambda path: fake_stages)
    deploy_calls = []
    monkeypatch.setattr(
        remote, "_deploy_trigger", lambda *args, **kwargs: deploy_calls.append((args, kwargs))
    )

    deployer = _make_mock_deployer()
    monkeypatch.setattr(remote, "get_deployer", lambda root: deployer)

    remote.handle_remote_run(
        "task.lm", str(tmp_path), {"cloud": {"project_id": "proj"}}, verbose=False
    )

    assert len(deploy_calls) == 1
    args, _ = deploy_calls[0]
    script_name, project_root, stages = args
    assert script_name == "task.lm"
    assert project_root == tmp_path
    assert stages == fake_stages


@pytest.mark.integration
@pytest.mark.cloud
def test_handle_remote_run_fetches_logs_when_run_job_raises(monkeypatch, tmp_path, capsys):
    """Even if run_job raises unexpectedly, container logs should still be fetched."""
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    import lamia.cli.remote as remote

    (tmp_path / "config.yaml").write_text("cloud:\n  provider: gcp\n  project_id: proj\n")
    _write_script(tmp_path, "task.lm", 'def run():\n    raise Exception("boom")')

    deployer = _make_mock_deployer()
    deployer.run_job.side_effect = RuntimeError("The container exited with an error")
    deployer.fetch_execution_logs.return_value = ("container stdout", "container stderr")
    deployer.get_deployed_source_hash.return_value = "abc"
    monkeypatch.setattr(remote, "get_deployer", lambda root: deployer)
    monkeypatch.setattr(remote, "extract_all_triggers", lambda path: [])
    monkeypatch.setattr(remote, "build_file_sync_plan", lambda **kwargs: [])
    monkeypatch.setattr(remote, "_compute_source_hash", lambda root, d: "abc")

    with pytest.raises(RuntimeError, match="container exited with an error"):
        remote.handle_remote_run(
            "task.lm", str(tmp_path), {"cloud": {"project_id": "proj"}}, verbose=False
        )

    captured = capsys.readouterr()
    assert "container stdout" in captured.out
    assert "container stderr" in captured.err


@pytest.mark.integration
@pytest.mark.cloud
def test_handle_remote_run_displays_logs_on_container_failure(monkeypatch, tmp_path, capsys):
    """Failed remote runs must print container logs and the logs URL."""
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    import lamia.cli.remote as remote

    (tmp_path / "config.yaml").write_text("cloud:\n  provider: gcp\n  project_id: proj\n")
    _write_script(tmp_path, "task.lm", 'def run():\n    raise Exception("boom")')

    deployer = _make_mock_deployer()
    deployer.run_job.return_value = {
        "exit_code": 1,
        "elapsed_seconds": 3.2,
        "logs_url": "https://console.cloud.google.com/logs/exec-1",
        "execution_name": "projects/p/locations/us-central1/jobs/lamia-task/executions/exec-1",
    }
    deployer.fetch_execution_logs.return_value = ("Traceback: boom", "")
    deployer.get_deployed_source_hash.return_value = "abc"
    monkeypatch.setattr(remote, "get_deployer", lambda root: deployer)
    monkeypatch.setattr(remote, "extract_all_triggers", lambda path: [])
    monkeypatch.setattr(remote, "build_file_sync_plan", lambda **kwargs: [])
    monkeypatch.setattr(remote, "_compute_source_hash", lambda root, d: "abc")

    with pytest.raises(SystemExit) as exc_info:
        remote.handle_remote_run(
            "task.lm", str(tmp_path), {"cloud": {"project_id": "proj"}}, verbose=False
        )

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Traceback: boom" in captured.out
    assert "https://console.cloud.google.com/logs/exec-1" in captured.err
    assert "Completed in 3.2s" in captured.err


def _remote_module():
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    import lamia.cli.remote as remote
    return remote


def _plain_script(tmp_path: Path) -> None:
    _write_script(
        tmp_path,
        "task.lm",
        """
def run():
    return 1
""".strip(),
    )


def _setup_deployer(monkeypatch, remote, tmp_path, **overrides):
    """Create a mock deployer, patch it into remote, and write config.yaml."""
    (tmp_path / "config.yaml").write_text("cloud:\n  provider: gcp\n  project_id: proj\n")
    deployer = _make_mock_deployer()
    for attr, val in overrides.items():
        setattr(deployer, attr, val)
    monkeypatch.setattr(remote, "get_deployer", lambda root: deployer)
    monkeypatch.setattr(remote, "extract_all_triggers", lambda path: [])
    monkeypatch.setattr(remote, "build_file_sync_plan", lambda **kwargs: [])
    return deployer


@pytest.mark.integration
@pytest.mark.cloud
class TestHandleRemoteRun:
    def test_happy_path_deploy_run_fetch_logs(self, monkeypatch, tmp_path, capsys):
        remote = _remote_module()
        _plain_script(tmp_path)

        deployer = _setup_deployer(monkeypatch, remote, tmp_path)
        deployer.fetch_execution_logs.return_value = ("hello out", "hello err")

        with pytest.raises(SystemExit) as exc:
            remote.handle_remote_run(
                "task.lm", str(tmp_path),
                {"cloud": {"project_id": "proj", "location": "us-central1"}},
                verbose=False,
            )

        assert exc.value.code == 0
        deployer.deploy.assert_called_once()
        captured = capsys.readouterr()
        assert "hello out" in captured.out
        assert "hello err" in captured.err
        assert "Completed in 1.5s" in captured.err

    def test_prints_pending_and_running_breakdown_when_available(self, monkeypatch, tmp_path, capsys):
        remote = _remote_module()
        _plain_script(tmp_path)

        deployer = _setup_deployer(monkeypatch, remote, tmp_path)
        deployer.run_job.return_value = {
            "exit_code": 0, "elapsed_seconds": 100.0,
            "pending_seconds": 83.0, "running_seconds": 17.0,
            "logs_url": "https://logs.example", "execution_name": "exec-1",
        }

        assert self._run(remote, tmp_path) == 0
        assert "Completed in 100.0s (pending 83.0s, execution 17.0s)" in capsys.readouterr().err

    def _run(self, remote, tmp_path):
        with pytest.raises(SystemExit) as exc:
            remote.handle_remote_run(
                "task.lm", str(tmp_path),
                {"cloud": {"project_id": "proj", "location": "us-central1"}},
                verbose=False,
            )
        return exc.value.code

    def test_logs_url_hidden_on_success(self, monkeypatch, tmp_path, capsys):
        """On a clean run the script output is the answer; the URL is noise."""
        remote = _remote_module()
        _plain_script(tmp_path)
        _setup_deployer(monkeypatch, remote, tmp_path)

        assert self._run(remote, tmp_path) == 0
        assert "Logs:" not in capsys.readouterr().err

    def test_logs_url_shown_on_failure(self, monkeypatch, tmp_path, capsys):
        remote = _remote_module()
        _plain_script(tmp_path)
        deployer = _setup_deployer(monkeypatch, remote, tmp_path)
        deployer.run_job.return_value = {
            "exit_code": 3, "elapsed_seconds": 1.5,
            "logs_url": "https://console.example/logs", "execution_name": "exec-1",
        }

        assert self._run(remote, tmp_path) == 3
        assert "Logs: https://console.example/logs" in capsys.readouterr().err

    def test_logs_url_shown_when_log_fetch_fails(self, monkeypatch, tmp_path, capsys):
        """Without container output the URL is the only way to see anything."""
        remote = _remote_module()
        _plain_script(tmp_path)
        deployer = _setup_deployer(monkeypatch, remote, tmp_path)
        deployer.fetch_execution_logs.side_effect = RuntimeError("logging denied")

        assert self._run(remote, tmp_path) == 0
        err = capsys.readouterr().err
        assert "Failed to fetch container logs" in err
        assert "Logs: https://logs.example" in err

    def test_skips_deploy_when_source_hash_matches(self, monkeypatch, tmp_path, capsys):
        remote = _remote_module()
        _plain_script(tmp_path)

        deployer = _setup_deployer(monkeypatch, remote, tmp_path)
        deployer.get_deployed_source_hash.return_value = "abc123"
        monkeypatch.setattr(remote, "_compute_source_hash", lambda root, d: "abc123")

        with pytest.raises(SystemExit):
            remote.handle_remote_run(
                "task.lm", str(tmp_path),
                {"cloud": {"project_id": "proj"}},
                verbose=False,
            )

        deployer.deploy.assert_not_called()
        assert "skipping build" in capsys.readouterr().err

    def test_missing_project_id_exits_with_error(self, monkeypatch, tmp_path, capsys):
        remote = _remote_module()
        _plain_script(tmp_path)

        def _raise_no_config(root):
            raise ValueError("cloud.project_id is required in config.yaml.")
        monkeypatch.setattr(remote, "get_deployer", _raise_no_config)

        with pytest.raises(ValueError, match="project_id"):
            remote.handle_remote_run("task.lm", str(tmp_path), {}, verbose=False)

    def test_file_sync_warnings_printed_for_nonempty_entries(self, monkeypatch, tmp_path, capsys):
        remote = _remote_module()
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
        from lamia_cloud.contracts import FileSyncEntry

        _plain_script(tmp_path)
        entries = [
            FileSyncEntry(raw_path="data.csv", resolved_path="/tmp/data.csv", bucket_key="data.csv"),
        ]

        deployer = _setup_deployer(monkeypatch, remote, tmp_path)
        deployer.get_deployed_source_hash.return_value = "same"
        monkeypatch.setattr(remote, "build_file_sync_plan", lambda **kwargs: entries)
        monkeypatch.setattr(remote, "_compute_source_hash", lambda root, d: "same")

        with pytest.raises(SystemExit):
            remote.handle_remote_run(
                "task.lm", str(tmp_path),
                {"cloud": {"project_id": "proj"}},
                verbose=False,
            )

        stderr = capsys.readouterr().err
        assert "will upload local files" in stderr
        assert "data.csv" in stderr


@pytest.mark.integration
@pytest.mark.cloud
def test_handle_remote_run_calls_ensure_apis_enabled_before_deploy(monkeypatch, tmp_path):
    """handle_remote_run must enable cloud APIs before any deploy/run calls."""
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    import lamia.cli.remote as remote

    (tmp_path / "config.yaml").write_text("cloud:\n  provider: gcp\n  project_id: proj\n")
    _write_script(tmp_path, "task.lm", 'def run():\n    return 1\n')

    call_order = []
    deployer = _make_mock_deployer()
    deployer.ensure_apis_enabled.side_effect = lambda: call_order.append("ensure_apis")
    deployer.deploy.side_effect = lambda **kw: call_order.append("deploy") or "lamia-task"
    deployer.run_job.side_effect = (
        lambda **kw: call_order.append("run_job")
        or {"exit_code": 0, "elapsed_seconds": 0, "logs_url": "", "execution_name": "e1"}
    )

    monkeypatch.setattr(remote, "get_deployer", lambda root: deployer)
    monkeypatch.setattr(remote, "extract_all_triggers", lambda path: [])
    monkeypatch.setattr(remote, "build_file_sync_plan", lambda **kwargs: [])
    monkeypatch.setattr(
        remote, "analyze_script",
        lambda path: ScriptCapabilities(),
    )

    with pytest.raises(SystemExit) as exc_info:
        remote.handle_remote_run(
            "task.lm", str(tmp_path), {"cloud": {"project_id": "proj"}}, verbose=False
        )

    assert exc_info.value.code == 0
    assert call_order[0] == "ensure_apis"
    assert "deploy" in call_order
    assert call_order.index("ensure_apis") < call_order.index("deploy")


@pytest.mark.integration
@pytest.mark.cloud
def test_handle_remote_run_propagates_ensure_apis_enabled_failure(monkeypatch, tmp_path):
    """If API enablement fails, surface the error instead of deploying regardless."""
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    import lamia.cli.remote as remote

    (tmp_path / "config.yaml").write_text("cloud:\n  provider: gcp\n  project_id: proj\n")
    _write_script(tmp_path, "task.lm", 'def run():\n    return 1\n')

    deployer = _make_mock_deployer()
    deployer.ensure_apis_enabled.side_effect = RuntimeError("API enable failed")
    monkeypatch.setattr(remote, "get_deployer", lambda root: deployer)
    monkeypatch.setattr(remote, "extract_all_triggers", lambda path: [])

    with pytest.raises(RuntimeError, match="API enable failed"):
        remote.handle_remote_run(
            "task.lm", str(tmp_path), {"cloud": {"project_id": "proj"}}, verbose=False
        )

    deployer.deploy.assert_not_called()


@pytest.mark.integration
@pytest.mark.cloud
class TestResolveDeployMode:
    """_resolve_deploy_mode picks the right source mode and repo URL."""

    @pytest.fixture(autouse=True)
    def _require_cloud(self):
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")

    def test_defaults_to_git_when_remote_exists(self, monkeypatch, tmp_path):
        import lamia.cli.remote as remote
        monkeypatch.setattr(
            remote, "get_remote_origin",
            lambda path: "https://github.com/lamia-lang/lamia",
        )

        mode, url = remote._resolve_deploy_mode(None, tmp_path)
        assert mode == "git"
        assert url == "https://github.com/lamia-lang/lamia"

    def test_defaults_to_local_when_no_git(self, monkeypatch, tmp_path):
        import lamia.cli.remote as remote
        monkeypatch.setattr(remote, "get_remote_origin", lambda path: None)

        mode, url = remote._resolve_deploy_mode(None, tmp_path)
        assert mode == "local"
        assert url is None

    def test_config_override_local_ignores_git(self, monkeypatch, tmp_path):
        import lamia.cli.remote as remote
        monkeypatch.setattr(
            remote, "get_remote_origin",
            lambda path: "https://github.com/lamia-lang/lamia",
        )

        config = {"cloud": {"deploy_mode": "local"}}
        mode, url = remote._resolve_deploy_mode(config, tmp_path)
        assert mode == "local"
        assert url is None

    def test_config_git_without_remote_falls_back(self, monkeypatch, tmp_path, capsys):
        import lamia.cli.remote as remote
        monkeypatch.setattr(remote, "get_remote_origin", lambda path: None)

        config = {"cloud": {"deploy_mode": "git"}}
        mode, url = remote._resolve_deploy_mode(config, tmp_path)
        assert mode == "local"
        assert url is None
        assert "Falling back to local" in capsys.readouterr().err


@pytest.mark.integration
@pytest.mark.cloud
class TestHandleRemoteRunGitMode:
    """handle_remote_run passes deploy_mode and repo_url through to deployer."""

    def test_git_mode_passes_repo_url_to_deploy(self, monkeypatch, tmp_path):
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
        import lamia.cli.remote as remote

        _write_script(tmp_path, "task.lm", 'def run():\n    return 1\n')

        deployer = _make_mock_deployer()
        monkeypatch.setattr(remote, "get_deployer", lambda root: deployer)
        monkeypatch.setattr(remote, "extract_all_triggers", lambda path: [])
        monkeypatch.setattr(remote, "build_file_sync_plan", lambda **kwargs: [])
        monkeypatch.setattr(
            remote, "analyze_script", lambda path: ScriptCapabilities(),
        )
        monkeypatch.setattr(
            remote, "get_remote_origin",
            lambda path: "https://github.com/lamia-lang/lamia",
        )

        with pytest.raises(SystemExit) as exc_info:
            remote.handle_remote_run(
                "task.lm", str(tmp_path), None, verbose=False,
            )

        assert exc_info.value.code == 0
        deploy_kwargs = deployer.deploy.call_args.kwargs
        assert deploy_kwargs["deploy_mode"] == "git"
        assert deploy_kwargs["repo_url"] == "https://github.com/lamia-lang/lamia"

    def test_local_mode_no_repo_url(self, monkeypatch, tmp_path):
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
        import lamia.cli.remote as remote

        _write_script(tmp_path, "task.lm", 'def run():\n    return 1\n')

        deployer = _make_mock_deployer()
        monkeypatch.setattr(remote, "get_deployer", lambda root: deployer)
        monkeypatch.setattr(remote, "extract_all_triggers", lambda path: [])
        monkeypatch.setattr(remote, "build_file_sync_plan", lambda **kwargs: [])
        monkeypatch.setattr(
            remote, "analyze_script", lambda path: ScriptCapabilities(),
        )
        monkeypatch.setattr(remote, "get_remote_origin", lambda path: None)

        with pytest.raises(SystemExit) as exc_info:
            remote.handle_remote_run(
                "task.lm", str(tmp_path), None, verbose=False,
            )

        assert exc_info.value.code == 0
        deploy_kwargs = deployer.deploy.call_args.kwargs
        assert deploy_kwargs["deploy_mode"] == "local"
        assert deploy_kwargs["repo_url"] is None


@pytest.mark.integration
@pytest.mark.cloud
class TestCiAuthMandatoryConnect:
    """CI must fail fast without prior lamia cloud connect."""

    @pytest.fixture(autouse=True)
    def _require_cloud(self):
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")

    def test_ci_fails_without_required_env_vars(self, monkeypatch, capsys):
        import lamia.cli.remote as remote

        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_REPOSITORY", "acme/widgets")
        monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
        monkeypatch.delenv("LAMIA_CONNECTION_ID", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            remote._setup_ci_auth_if_needed(Path("."))

        assert exc_info.value.code == 1
        stderr = capsys.readouterr().err
        assert "LAMIA_CONNECTION_ID" in stderr

    def test_connection_id_from_another_repo_rejected(self, monkeypatch, capsys):
        """A connection ID copied from a different repository must not work."""
        import lamia.cli.remote as remote

        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_REPOSITORY", "acme/widgets")
        monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
        monkeypatch.setenv("LAMIA_CONNECTION_ID", "v1-123456-ac0d478df1c7")

        with pytest.raises(SystemExit) as exc_info:
            remote._setup_ci_auth_if_needed(Path("."))

        assert exc_info.value.code == 1
        assert "different repository" in capsys.readouterr().err

    def test_missing_github_repository_rejected(self, monkeypatch, capsys):
        import lamia.cli.remote as remote

        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            remote._setup_ci_auth_if_needed(Path("."))

        assert exc_info.value.code == 1
        assert "GITHUB_REPOSITORY" in capsys.readouterr().err

    def test_ci_fails_fast_with_none_config(self, monkeypatch, capsys):
        import lamia.cli.remote as remote

        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            remote._setup_ci_auth_if_needed(Path("."))

        assert exc_info.value.code == 1

    def test_not_in_ci_skips_auth_setup(self, monkeypatch):
        """Outside CI, _setup_ci_auth_if_needed is a no-op even without config."""
        import lamia.cli.remote as remote

        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        remote._setup_ci_auth_if_needed(Path("."))

    def test_not_in_ci_with_empty_env(self, monkeypatch):
        import lamia.cli.remote as remote

        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        remote._setup_ci_auth_if_needed(Path("."))


@pytest.mark.integration
@pytest.mark.cloud
class TestCiAuthEventGuard:
    """S8: only events running already-merged code may authenticate."""

    @pytest.fixture(autouse=True)
    def _require_cloud(self):
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")

    @pytest.mark.parametrize(
        "event",
        [
            "pull_request_target",
            "workflow_run",
            "issue_comment",
            "pull_request_review_comment",
            "pull_request",
            "fork",
        ],
    )
    def test_untrusted_events_rejected(self, monkeypatch, capsys, event):
        import lamia.cli.remote as remote

        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_EVENT_NAME", event)
        monkeypatch.setenv("GITHUB_REPOSITORY", "acme/widgets")
        monkeypatch.setenv("LAMIA_CONNECTION_ID", "v1-123456-f60ecdb16e5e")

        with pytest.raises(SystemExit) as exc_info:
            remote._setup_ci_auth_if_needed(Path("."))

        assert exc_info.value.code == 1
        assert event in capsys.readouterr().err

    def test_push_event_allowed(self, monkeypatch):
        import lamia.cli.remote as remote

        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
        monkeypatch.setenv(
            "ACTIONS_ID_TOKEN_REQUEST_URL",
            "https://vstoken.actions.githubusercontent.com/token",
        )
        monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ghs_fake")
        monkeypatch.setenv("GITHUB_REPOSITORY", "acme/widgets")
        monkeypatch.setenv("LAMIA_CONNECTION_ID", "v1-123456-f60ecdb16e5e")
        monkeypatch.setattr(
            remote, "get_remote_origin",
            lambda path: "https://github.com/acme/widgets.git",
        )
        monkeypatch.setattr(remote, "get_connector", _gcp_connector)

        remote._setup_ci_auth_if_needed(Path("."))

        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)


@pytest.mark.integration
@pytest.mark.cloud
class TestCiAuthRepoValidation:
    """Workspace git remote must match the repository being built."""

    @pytest.fixture(autouse=True)
    def _require_cloud(self):
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")

    def test_mismatched_repo_rejected(self, monkeypatch, capsys):
        import lamia.cli.remote as remote

        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
        monkeypatch.setenv("GITHUB_REPOSITORY", "acme/widgets")
        monkeypatch.setenv("LAMIA_CONNECTION_ID", "v1-123456-f60ecdb16e5e")
        monkeypatch.setattr(
            remote, "get_remote_origin",
            lambda path: "https://github.com/attacker/malware.git",
        )

        with pytest.raises(SystemExit) as exc_info:
            remote._setup_ci_auth_if_needed(Path("."))

        assert exc_info.value.code == 1
        stderr = capsys.readouterr().err
        assert "mismatch" in stderr.lower()

    def test_matching_repo_passes(self, monkeypatch):
        import lamia.cli.remote as remote

        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
        monkeypatch.setenv(
            "ACTIONS_ID_TOKEN_REQUEST_URL",
            "https://vstoken.actions.githubusercontent.com/token",
        )
        monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ghs_fake")
        monkeypatch.setenv("GITHUB_REPOSITORY", "acme/widgets")
        monkeypatch.setenv("LAMIA_CONNECTION_ID", "v1-123456-f60ecdb16e5e")
        monkeypatch.setattr(
            remote, "get_remote_origin",
            lambda path: "https://github.com/acme/widgets.git",
        )
        monkeypatch.setattr(remote, "get_connector", _gcp_connector)

        remote._setup_ci_auth_if_needed(Path("."))

        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)


@pytest.mark.integration
@pytest.mark.cloud
class TestCiAuthEnvVarSpoofing:
    """V3: Spoofing GITHUB_ACTIONS has no security escalation."""

    @pytest.fixture(autouse=True)
    def _require_cloud(self):
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")

    def test_spoofed_ci_without_oidc_token_fails(self, monkeypatch, capsys):
        """Spoofing GITHUB_ACTIONS without OIDC runtime -> exit."""
        import lamia.cli.remote as remote

        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
        monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_URL", raising=False)
        monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", raising=False)
        monkeypatch.setenv("GITHUB_REPOSITORY", "acme/widgets")
        monkeypatch.setenv("LAMIA_CONNECTION_ID", "v1-123456-f60ecdb16e5e")
        monkeypatch.setattr(
            remote, "get_remote_origin",
            lambda path: "https://github.com/acme/widgets.git",
        )
        monkeypatch.setattr(remote, "get_connector", _gcp_connector)

        with pytest.raises(SystemExit) as exc_info:
            remote._setup_ci_auth_if_needed(Path("."))

        assert exc_info.value.code == 1
        stderr = capsys.readouterr().err
        assert "id-token: write" in stderr

    def test_env_var_detection_is_exact_match(self, monkeypatch):
        """GITHUB_ACTIONS must be exactly 'true', not truthy."""
        import lamia.cli.remote as remote

        monkeypatch.setenv("GITHUB_ACTIONS", "1")
        remote._setup_ci_auth_if_needed(Path("."))

        monkeypatch.setenv("GITHUB_ACTIONS", "yes")
        remote._setup_ci_auth_if_needed(Path("."))


@pytest.mark.integration
@pytest.mark.cloud
class TestCiCredentialConfig:
    """V2: Credential config is created correctly for WIF OIDC exchange."""

    @pytest.fixture(autouse=True)
    def _require_cloud(self):
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")

    def test_creates_external_account_credential_file(self, monkeypatch, tmp_path):
        """V8: WIF provider and SA derived by convention, not from config."""
        import json
        import os
        import stat
        import lamia.cli.remote as remote

        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
        monkeypatch.setenv(
            "ACTIONS_ID_TOKEN_REQUEST_URL",
            "https://vstoken.actions.githubusercontent.com/token",
        )
        monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ghs_fake_token")
        monkeypatch.setenv("GITHUB_REPOSITORY", "acme/widgets")
        monkeypatch.setenv("LAMIA_CONNECTION_ID", "v1-123456-f60ecdb16e5e")
        monkeypatch.setattr(
            remote, "get_remote_origin",
            lambda path: "https://github.com/acme/widgets.git",
        )
        monkeypatch.setattr(remote, "get_connector", _gcp_connector)

        remote._setup_ci_auth_if_needed(Path("."))

        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        assert cred_path is not None
        assert Path(cred_path).exists()

        cred = json.loads(Path(cred_path).read_text())
        assert cred["type"] == "external_account"
        assert "lamia-github-pool" in cred["audience"]
        assert "lamia-gh-f60ecdb16e5e" in cred["audience"]
        assert cred["token_url"] == "https://sts.googleapis.com/v1/token"
        assert "lm-ci-f60ecdb16e5e" in cred["service_account_impersonation_url"]
        assert "ghs_fake_token" in cred["credential_source"]["headers"]["Authorization"]

        mode = stat.S_IMODE(os.stat(cred_path).st_mode)
        assert mode == 0o600, f"Credential file should be 0600, got {oct(mode)}"

        Path(cred_path).unlink(missing_ok=True)
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)


@pytest.mark.skipif(
    importlib.util.find_spec("lamia_cloud") is None,
    reason="lamia_cloud not installed",
)
class TestExtractScriptModels:
    """Tests for _extract_script_models which parses models= from .lm scripts."""

    def test_single_model(self, tmp_path):
        from lamia.cli.remote import _extract_script_models
        script = tmp_path / "test.lm"
        script.write_text('def my_func(models="openai:gpt-4"):\n    "do stuff"\n')
        result = _extract_script_models(script)
        assert result == {("openai", "gpt-4")}

    def test_multiple_functions(self, tmp_path):
        from lamia.cli.remote import _extract_script_models
        script = tmp_path / "test.lm"
        script.write_text(
            'def a(models="google:gemini-2.5-flash"):\n    "a"\n\n'
            'def b(models="mistralai:mistral-small-2503"):\n    "b"\n'
        )
        result = _extract_script_models(script)
        assert ("google", "gemini-2.5-flash") in result
        assert ("mistralai", "mistral-small-2503") in result

    def test_list_models(self, tmp_path):
        from lamia.cli.remote import _extract_script_models
        script = tmp_path / "test.lm"
        script.write_text(
            'def my_func(models=["openai:gpt-4", "anthropic:claude-sonnet-4-5"]):\n'
            '    "do stuff"\n'
        )
        result = _extract_script_models(script)
        assert ("openai", "gpt-4") in result
        assert ("anthropic", "claude-sonnet-4-5") in result

    def test_no_models_param(self, tmp_path):
        from lamia.cli.remote import _extract_script_models
        script = tmp_path / "test.lm"
        script.write_text('def my_func():\n    "do stuff"\n')
        result = _extract_script_models(script)
        assert result == set()

    def test_nonexistent_file(self, tmp_path):
        from lamia.cli.remote import _extract_script_models
        result = _extract_script_models(tmp_path / "nope.lm")
        assert result == set()


@pytest.mark.integration
@pytest.mark.cloud
class TestCheckCloudModelAccessHints:
    """_check_cloud_model_access must print provider-supplied hints verbatim
    without adding any GCP/Vertex/Model-Garden-specific text of its own."""

    @pytest.fixture(autouse=True)
    def _require_cloud(self):
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")

    def _run(self, monkeypatch, tmp_path, capsys, check_result):
        """Run _check_cloud_model_access with a fake LLM router and deployer."""
        import lamia.cli.remote as remote
        from lamia_cloud.interfaces import CloudDeployer

        deployer = mock.MagicMock(spec=CloudDeployer)
        deployer.get_verified_model_access.return_value = set()
        deployer.remember_verified_model_access.return_value = None

        fake_llm = mock.MagicMock()
        fake_llm.check_model_access.return_value = check_result
        fake_llm.model_catalog_url.return_value = "https://example.com/catalog"
        monkeypatch.setattr(remote, "get_llm_router", lambda root: fake_llm)

        script = tmp_path / "task.lm"
        script.write_text('def ask(models="anthropic:claude-sonnet-4-5"):\n    "hi"\n')

        try:
            remote._check_cloud_model_access(
                {"cloud": {"provider": "test"}},
                str(tmp_path),
                deployer,
                script_path=script,
            )
        except SystemExit:
            pass

        return capsys.readouterr().err

    def test_inconclusive_hint_printed_verbatim(self, monkeypatch, tmp_path, capsys):
        """Hints for inconclusive models must appear verbatim in stderr."""
        hint_text = "Some opaque provider hint about quota."
        result = (
            [],
            [],
            {},
            {("anthropic", "claude-sonnet-4-5"): hint_text},
        )
        stderr = self._run(monkeypatch, tmp_path, capsys, result)
        assert hint_text in stderr

    def test_missing_hint_printed_verbatim(self, monkeypatch, tmp_path, capsys):
        """Hints for missing models must appear verbatim in stderr."""
        hint_text = "Accept terms at https://example.com/terms"
        result = (
            [("anthropic", "claude-sonnet-4-5")],
            [],
            {},
            {("anthropic", "claude-sonnet-4-5"): hint_text},
        )
        stderr = self._run(monkeypatch, tmp_path, capsys, result)
        assert hint_text in stderr
        assert "need action" in stderr

    def test_no_gcp_wording_in_output(self, monkeypatch, tmp_path, capsys):
        """remote.py must never inject its own GCP/Vertex/Model Garden text."""
        hint_text = "Provider-agnostic hint."
        result = (
            [("anthropic", "claude-sonnet-4-5")],
            [],
            {},
            {("anthropic", "claude-sonnet-4-5"): hint_text},
        )
        stderr = self._run(monkeypatch, tmp_path, capsys, result)
        assert "Vertex AI" not in stderr
        assert "Model Garden" not in stderr

    def test_catalog_url_label_is_generic(self, monkeypatch, tmp_path, capsys):
        """The catalog link label should say 'Browse available models', not
        'Browse Model Garden'."""
        result = (
            [("anthropic", "claude-sonnet-4-5")],
            [],
            {},
            {},
        )
        stderr = self._run(monkeypatch, tmp_path, capsys, result)
        assert "Browse available models:" in stderr
