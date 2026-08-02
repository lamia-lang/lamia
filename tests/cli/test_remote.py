"""Unit tests for script analysis utilities (no cloud deps), plus integration
tests for the remote/trigger deploy paths with the lamia_cloud boundary mocked."""

from unittest import mock

import pytest
from pathlib import Path

from lamia.cli.script_analysis import (
    ScriptCapabilities,
    analyze_script,
    script_capability_field_names,
)
from lamia.interpreter.ast_analyzer import extract_script_file_refs
from lamia.scheduling.base import generate_schedule_id


def _write_script(tmp_path: Path, name: str, content: str) -> Path:
    script_path = tmp_path / name
    script_path.write_text(content)
    return script_path


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
    file.read("notes.txt")
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
        "broken.lm",
        """
def run(
    return 1
""".strip(),
    )

    result = analyze_script(script)

    assert result.uses_llm is False
    assert result.uses_browser is False
    assert result.uses_files is False
    assert result.uses_file_context is False


def test_extract_file_refs_single_path(tmp_path):
    script = _write_script(tmp_path, "task.lm", 'with files("data/input.csv"):\n    pass')
    assert extract_script_file_refs(script) == ["data/input.csv"]


def test_extract_file_refs_multiple_paths_same_block(tmp_path):
    script = _write_script(tmp_path, "task.lm", 'with files("docs", "config.json"):\n    pass')
    assert extract_script_file_refs(script) == ["docs", "config.json"]


def test_extract_file_refs_multiple_blocks(tmp_path):
    script = _write_script(tmp_path, "task.lm",
        'with files("a.txt"):\n    pass\nwith files("b/"):\n    pass')
    assert extract_script_file_refs(script) == ["a.txt", "b/"]


def test_extract_file_refs_dynamic_arg_raises(tmp_path):
    script = _write_script(tmp_path, "task.lm", 'with files(some_var):\n    pass')
    with pytest.raises(ValueError, match="literal strings"):
        extract_script_file_refs(script)


def test_extract_file_refs_no_files_blocks(tmp_path):
    script = _write_script(tmp_path, "task.lm", 'x = 1\nprint(x)')
    assert extract_script_file_refs(script) == []


@pytest.mark.integration
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
def test_deploy_trigger_builds_plan_and_calls_provider_deploy(monkeypatch, tmp_path, capsys):
    """_deploy_trigger is lamia's side of the link to lamia_cloud: it must build the
    right TriggerDeploymentPlan and call provider.deploy(). What GCPTriggerProvider
    does with that plan belongs to the lamia-cloud test suite, not here."""
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
    mock_provider_cls = mock.MagicMock()
    mock_provider_cls.from_config.return_value = mock_provider
    monkeypatch.setattr(remote, "GCPTriggerProvider", mock_provider_cls)

    remote._deploy_trigger("task.lm", tmp_path, {"project_id": "proj"}, stages)

    mock_provider_cls.from_config.assert_called_once_with({"project_id": "proj"})
    plan = mock_provider.deploy.call_args[0][0]
    assert isinstance(plan, TriggerDeploymentPlan)
    assert plan.name == generate_schedule_id("task.lm", str(tmp_path))
    assert plan.name.startswith("task-")
    assert plan.mode == "reactive"
    assert plan.stages == stages

    stderr = capsys.readouterr().err
    assert "Deployed: lamia-trigger-task" in stderr


@pytest.mark.integration
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
        mock_provider_cls = mock.MagicMock()
        mock_provider_cls.from_config.return_value = mock_provider
        monkeypatch.setattr(remote, "GCPTriggerProvider", mock_provider_cls)

        remote._deploy_trigger("task.lm", root, {"project_id": "proj"}, stages)
        names.append(mock_provider.deploy.call_args[0][0].name)

    assert names[0] != names[1]
    assert all(n.startswith("task-") for n in names)


@pytest.mark.integration
def test_handle_remote_run_routes_to_deploy_trigger_when_script_has_triggers(monkeypatch, tmp_path):
    """handle_remote_run must detect trigger.* calls and hand off to _deploy_trigger
    instead of the one-shot run path — this is the routing decision lamia owns."""
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    import lamia.cli.remote as remote

    _write_script(tmp_path, "task.lm", "trigger.email_received(sender)")

    fake_stages = [mock.sentinel.stage]
    monkeypatch.setattr(remote, "extract_all_triggers", lambda path: fake_stages)
    deploy_calls = []
    monkeypatch.setattr(
        remote, "_deploy_trigger", lambda *args, **kwargs: deploy_calls.append((args, kwargs))
    )

    remote.handle_remote_run(
        "task.lm", str(tmp_path), {"cloud": {"project_id": "proj"}}, verbose=False
    )

    assert len(deploy_calls) == 1
    args, _ = deploy_calls[0]
    script_name, project_root, cloud_cfg, stages = args
    assert script_name == "task.lm"
    assert project_root == tmp_path
    assert cloud_cfg == {"project_id": "proj"}
    assert stages == fake_stages
