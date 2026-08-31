"""Tests for resolving which .env values a cloud deploy may carry."""

import pytest

from lamia import deploy_secrets


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A project directory with no global .env in reach."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setattr(
        deploy_secrets, "get_global_env_path", lambda: tmp_path / "global" / ".env"
    )
    monkeypatch.delenv("THIRD_PARTY_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return project_dir


def write_env(directory, **values):
    directory.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in values.items()]
    (directory / ".env").write_text("\n".join(lines) + "\n")


class TestProjectScopeId:
    def test_is_stable_for_the_same_directory(self, tmp_path):
        assert deploy_secrets.project_scope_id(tmp_path) == (
            deploy_secrets.project_scope_id(tmp_path)
        )

    def test_differs_between_projects(self, tmp_path):
        one = tmp_path / "one"
        two = tmp_path / "two"
        one.mkdir()
        two.mkdir()
        assert deploy_secrets.project_scope_id(one) != deploy_secrets.project_scope_id(two)


class TestReadEnvFile:
    def test_missing_file_is_empty(self, tmp_path):
        assert deploy_secrets.read_env_file(tmp_path / "nope.env") == {}

    def test_skips_comments_and_blank_lines(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("# comment\n\nKEY=value\n")
        assert deploy_secrets.read_env_file(env) == {"KEY": "value"}

    def test_keeps_equals_signs_inside_the_value(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("KEY=a=b=c\n")
        assert deploy_secrets.read_env_file(env) == {"KEY": "a=b=c"}


class TestResolveDeploySecrets:
    """Only keys declared under cloud.secrets are eligible for cloud sync."""

    def test_provider_key_does_not_travel_by_default(self, project):
        write_env(project, OPENAI_API_KEY="sk-should-not-leave")
        assert deploy_secrets.resolve_deploy_secrets(project) == {}

    def test_provider_key_travels_when_declared(self, project):
        write_env(project, OPENAI_API_KEY="sk-declared")
        resolved = deploy_secrets.resolve_deploy_secrets(project, ["OPENAI_API_KEY"])
        assert resolved == {"OPENAI_API_KEY": "sk-declared"}

    def test_non_model_key_travels_when_declared(self, project):
        write_env(
            project,
            THIRD_PARTY_API_KEY="tp-declared",
        )
        resolved = deploy_secrets.resolve_deploy_secrets(project, ["THIRD_PARTY_API_KEY"])
        assert resolved == {"THIRD_PARTY_API_KEY": "tp-declared"}

    def test_no_key_travels_without_declaration(self, project):
        write_env(
            project,
            THIRD_PARTY_API_KEY="tp-should-not-leave",
            ANTHROPIC_API_KEY="sk-should-not-leave",
        )
        assert deploy_secrets.resolve_deploy_secrets(project) == {}

    def test_no_env_file_resolves_empty(self, project):
        assert deploy_secrets.resolve_deploy_secrets(project) == {}

    def test_declared_key_with_no_value_is_skipped(self, project):
        assert deploy_secrets.resolve_deploy_secrets(project, ["MISSING_KEY"]) == {}

    def test_project_env_wins_over_global_env(self, project, tmp_path):
        write_env(project, THIRD_PARTY_API_KEY="from-project")
        write_env(tmp_path / "global", THIRD_PARTY_API_KEY="from-global")
        assert deploy_secrets.resolve_deploy_secrets(project, ["THIRD_PARTY_API_KEY"]) == {
            "THIRD_PARTY_API_KEY": "from-project"
        }

    def test_global_env_does_not_make_a_key_eligible(self, project, tmp_path):
        write_env(tmp_path / "global", THIRD_PARTY_API_KEY="tok-1")
        assert deploy_secrets.resolve_deploy_secrets(project) == {}

    def test_global_env_supplies_a_value_for_a_declared_key(self, project, tmp_path):
        write_env(tmp_path / "global", OPENAI_API_KEY="sk-global")
        resolved = deploy_secrets.resolve_deploy_secrets(project, ["OPENAI_API_KEY"])
        assert resolved == {"OPENAI_API_KEY": "sk-global"}

    def test_shell_env_supplies_a_value_for_a_declared_key(self, project, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-shell")
        resolved = deploy_secrets.resolve_deploy_secrets(project, ["OPENAI_API_KEY"])
        assert resolved == {"OPENAI_API_KEY": "sk-shell"}
