"""Tests for lamia.scheduling.cloud_scheduler — the lamia <-> lamia_cloud bridge.

Cloud-touching tests mock the lamia_cloud boundary (GCPTriggerProvider,
get_scheduler) rather than hitting real GCP: this repo only needs to verify
that lamia calls lamia_cloud's interface correctly. What GCPTriggerProvider
itself does belongs to the lamia-cloud project's own test suite.
"""

from pathlib import Path
from unittest import mock

import pytest

from lamia.scheduling import cloud_scheduler


def test_deploy_scheduled_trigger_errors_without_lamia_cloud(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cloud_scheduler, "LAMIA_CLOUD_AVAILABLE", False)

    with pytest.raises(SystemExit) as exc:
        cloud_scheduler.deploy_scheduled_trigger("task.lm", tmp_path, "0 * * * *", [])

    assert exc.value.code == 1
    assert "lamia-cloud package" in capsys.readouterr().err


def test_deploy_scheduled_trigger_errors_without_project_id(tmp_path, capsys):
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    (tmp_path / "config.yaml").write_text("cloud:\n  location: us-central1\n")

    with pytest.raises(SystemExit) as exc:
        cloud_scheduler.deploy_scheduled_trigger("task.lm", tmp_path, "0 * * * *", [])

    assert exc.value.code == 1
    assert "cloud.project_id" in capsys.readouterr().err


def test_fetch_cloud_statuses_returns_empty_without_lamia_cloud(monkeypatch):
    monkeypatch.setattr(cloud_scheduler, "LAMIA_CLOUD_AVAILABLE", False)

    results = cloud_scheduler.fetch_cloud_statuses(
        [{"id": "x", "script": "a.lm", "cron": "* * * * *", "project_root": "."}]
    )

    assert results == {}


@pytest.mark.integration
def test_deploy_scheduled_trigger_builds_plan_and_deploys(monkeypatch, tmp_path, capsys):
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
    from lamia_cloud.types import TriggerDeploymentPlan, TriggerStage

    (tmp_path / "config.yaml").write_text("cloud:\n  project_id: proj\n")
    (tmp_path / "task.lm").write_text("def run():\n    pass\n")

    stages = [
        TriggerStage(
            stage_index=0,
            trigger_method="email_received",
            trigger_config={},
            output_bindings=[],
            script_source="",
        )
    ]

    mock_provider = mock.MagicMock()
    mock_provider.deploy.return_value = "lamia-trigger-task"
    mock_provider_cls = mock.MagicMock()
    mock_provider_cls.from_config.return_value = mock_provider
    monkeypatch.setattr(cloud_scheduler, "GCPTriggerProvider", mock_provider_cls)

    cloud_scheduler.deploy_scheduled_trigger("task.lm", tmp_path, "0 * * * *", stages)

    mock_provider_cls.from_config.assert_called_once_with({"project_id": "proj"})
    plan = mock_provider.deploy.call_args[0][0]
    assert isinstance(plan, TriggerDeploymentPlan)
    assert plan.mode == "scheduled"
    assert plan.cron == "0 * * * *"
    assert plan.stages == stages
    output = capsys.readouterr().out
    assert "Deployed: lamia-trigger-task" in output
    deployed_line = next(line for line in output.splitlines() if line.startswith("Deployed: "))
    deployed_id = deployed_line.split("Deployed: ", 1)[1].strip()
    assert deployed_id.startswith("lamia-")


@pytest.mark.integration
def test_fetch_cloud_statuses_maps_enabled_state(monkeypatch, tmp_path):
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")

    mock_scheduler = mock.MagicMock()
    mock_scheduler.get_installed_config.return_value = {
        "state": "ENABLED",
        "last_attempt_time": "2026-07-01T00:00:00Z",
    }
    monkeypatch.setattr(cloud_scheduler, "get_scheduler", lambda root: mock_scheduler)

    cloud_jobs = [
        {"id": "job-1", "script": "task.lm", "cron": "0 * * * *", "project_root": str(tmp_path)}
    ]

    results = cloud_scheduler.fetch_cloud_statuses(cloud_jobs)

    assert results["job-1"] == {
        "timestamp": "2026-07-01T00:00:00Z",
        "success": True,
        "state": "ENABLED",
    }


@pytest.mark.integration
def test_fetch_cloud_statuses_pauses_job_when_scheduler_reports_paused(monkeypatch, tmp_path):
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")

    mock_scheduler = mock.MagicMock()
    mock_scheduler.get_installed_config.return_value = {"state": "PAUSED"}
    monkeypatch.setattr(cloud_scheduler, "get_scheduler", lambda root: mock_scheduler)
    paused_calls = []
    monkeypatch.setattr(
        cloud_scheduler, "set_paused", lambda job_id, val: paused_calls.append((job_id, val))
    )

    cloud_jobs = [
        {"id": "job-2", "script": "task.lm", "cron": "0 * * * *", "project_root": str(tmp_path)}
    ]

    cloud_scheduler.fetch_cloud_statuses(cloud_jobs)

    assert paused_calls == [("job-2", True)]
