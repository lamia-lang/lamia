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
from lamia.scheduling.base import JobStatus, ScheduleJob
from lamia.scheduling.cloud_scheduler import CloudSchedulerBridge, _to_cloud_job


def _schedule_job(tmp_path: Path) -> ScheduleJob:
    return ScheduleJob(
        script="task.lm",
        cron="0 * * * *",
        schedule_id="task-abc1",
        catch_up=False,
        project_root=tmp_path,
    )


class TestCloudSchedulerBridge:
    def test_install_delegates_with_converted_job(self, tmp_path):
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
        mock_scheduler = mock.MagicMock()
        bridge = CloudSchedulerBridge(mock_scheduler)
        job = _schedule_job(tmp_path)

        bridge.install(job, lamia_bin="/usr/bin/lamia")

        mock_scheduler.install.assert_called_once()
        cloud_job, lamia_bin = mock_scheduler.install.call_args[0]
        assert lamia_bin == "/usr/bin/lamia"
        assert cloud_job.script == "task.lm"
        assert cloud_job.cron == "0 * * * *"
        assert cloud_job.schedule_id == "task-abc1"
        assert cloud_job.catch_up is False
        assert cloud_job.project_root == tmp_path

    def test_uninstall_delegates_with_converted_job(self, tmp_path):
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
        mock_scheduler = mock.MagicMock()
        bridge = CloudSchedulerBridge(mock_scheduler)
        job = _schedule_job(tmp_path)

        bridge.uninstall(job)

        mock_scheduler.uninstall.assert_called_once()
        cloud_job = mock_scheduler.uninstall.call_args[0][0]
        assert cloud_job.schedule_id == "task-abc1"

    def test_get_status_converts_cloud_status_to_job_status(self, tmp_path):
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
        from lamia_cloud.types import CloudJobStatus

        mock_scheduler = mock.MagicMock()
        mock_scheduler.get_status.return_value = CloudJobStatus.ACTIVE
        bridge = CloudSchedulerBridge(mock_scheduler)

        status = bridge.get_status(_schedule_job(tmp_path))

        assert status == JobStatus.ACTIVE
        mock_scheduler.get_status.assert_called_once()

    def test_pause_and_resume_delegate(self, tmp_path):
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
        mock_scheduler = mock.MagicMock()
        bridge = CloudSchedulerBridge(mock_scheduler)
        job = _schedule_job(tmp_path)

        bridge.pause(job)
        bridge.resume(job)

        mock_scheduler.pause.assert_called_once()
        mock_scheduler.resume.assert_called_once()
        assert mock_scheduler.pause.call_args[0][0].schedule_id == "task-abc1"
        assert mock_scheduler.resume.call_args[0][0].schedule_id == "task-abc1"


class TestToCloudJob:
    def test_maps_schedule_job_fields(self, tmp_path):
        pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")
        from lamia_cloud.types import CloudScheduleJob

        job = ScheduleJob(
            script="hello.lm",
            cron="@reboot",
            schedule_id="hello-dead",
            catch_up=True,
            project_root=tmp_path,
        )

        cloud_job = _to_cloud_job(job)

        assert isinstance(cloud_job, CloudScheduleJob)
        assert cloud_job.script == "hello.lm"
        assert cloud_job.cron == "@reboot"
        assert cloud_job.schedule_id == "hello-dead"
        assert cloud_job.catch_up is True
        assert cloud_job.project_root == tmp_path


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
def test_fetch_cloud_statuses_uses_execution_status(monkeypatch, tmp_path):
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")

    mock_scheduler = mock.MagicMock()
    mock_scheduler.get_installed_config.return_value = {
        "state": "ENABLED",
        "last_attempt_time": "2026-07-01T00:00:00Z",
    }
    mock_scheduler.get_last_execution_status.return_value = {
        "timestamp": "2026-07-01T01:00:00Z",
        "success": False,
        "exit_code": 1,
    }
    monkeypatch.setattr(cloud_scheduler, "get_scheduler", lambda root: mock_scheduler)

    cloud_jobs = [
        {"id": "job-1", "script": "task.lm", "cron": "0 * * * *", "project_root": str(tmp_path)}
    ]

    results = cloud_scheduler.fetch_cloud_statuses(cloud_jobs)

    assert results["job-1"] == {
        "timestamp": "2026-07-01T01:00:00Z",
        "success": False,
    }
    mock_scheduler.get_last_execution_status.assert_called_once()


@pytest.mark.integration
def test_fetch_cloud_statuses_fallback_when_no_executions(monkeypatch, tmp_path):
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")

    mock_scheduler = mock.MagicMock()
    mock_scheduler.get_installed_config.return_value = {
        "state": "ENABLED",
        "last_attempt_time": "2026-07-01T00:00:00Z",
    }
    mock_scheduler.get_last_execution_status.return_value = None
    monkeypatch.setattr(cloud_scheduler, "get_scheduler", lambda root: mock_scheduler)

    cloud_jobs = [
        {"id": "job-1", "script": "task.lm", "cron": "0 * * * *", "project_root": str(tmp_path)}
    ]

    results = cloud_scheduler.fetch_cloud_statuses(cloud_jobs)

    assert results["job-1"] == {
        "timestamp": "2026-07-01T00:00:00Z",
        "success": None,
    }


@pytest.mark.integration
def test_fetch_cloud_statuses_mixed_jobs(monkeypatch, tmp_path):
    pytest.importorskip("lamia_cloud", reason="lamia[cloud] extra not installed")

    mock_scheduler = mock.MagicMock()

    def config_for_job(cloud_job):
        if cloud_job.schedule_id == "with-exec":
            return {"state": "ENABLED", "last_attempt_time": "2026-07-01T00:00:00Z"}
        return {"state": "ENABLED", "last_attempt_time": "2026-07-02T00:00:00Z"}

    def exec_status_for_job(cloud_job):
        if cloud_job.schedule_id == "with-exec":
            return {
                "timestamp": "2026-07-01T01:00:00Z",
                "success": True,
                "exit_code": 0,
            }
        return None

    mock_scheduler.get_installed_config.side_effect = config_for_job
    mock_scheduler.get_last_execution_status.side_effect = exec_status_for_job
    monkeypatch.setattr(cloud_scheduler, "get_scheduler", lambda root: mock_scheduler)

    cloud_jobs = [
        {
            "id": "with-exec",
            "script": "a.lm",
            "cron": "0 * * * *",
            "project_root": str(tmp_path),
        },
        {
            "id": "no-exec",
            "script": "b.lm",
            "cron": "0 * * * *",
            "project_root": str(tmp_path),
        },
    ]

    results = cloud_scheduler.fetch_cloud_statuses(cloud_jobs)

    assert results["with-exec"] == {
        "timestamp": "2026-07-01T01:00:00Z",
        "success": True,
    }
    assert results["no-exec"] == {
        "timestamp": "2026-07-02T00:00:00Z",
        "success": None,
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
