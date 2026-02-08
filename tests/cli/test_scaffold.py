import os

import yaml

from lamia.cli import scaffold


def test_create_minimal_config(tmp_path):
    config_path = tmp_path / "config.yaml"

    created = scaffold.create_minimal_config(str(config_path), with_extensions=True, extensions_folder_name="exts")

    assert created is True
    config = yaml.safe_load(config_path.read_text())
    assert config["extensions_folder"] == "exts"
    assert "model_chain" in config
    assert config["model_chain"][0]["name"] == "ollama"
    assert "providers" in config
    assert config["providers"]["ollama"]["enabled"] is True


def test_create_minimal_config_skips_existing(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("default_model: ollama\n")

    created = scaffold.create_minimal_config(str(config_path))

    assert created is False


def test_update_config_with_extensions(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("default_model: ollama\n")

    updated = scaffold.update_config_with_extensions(str(config_path), extensions_folder_name="extensions")

    assert updated is True
    config = yaml.safe_load(config_path.read_text())
    assert config["extensions_folder"] == "extensions"


def test_update_config_with_extensions_missing_file(tmp_path):
    config_path = tmp_path / "config.yaml"

    updated = scaffold.update_config_with_extensions(str(config_path))

    assert updated is False


def test_create_env_file(tmp_path):
    env_path = tmp_path / ".env"

    created = scaffold.create_env_file(str(env_path))

    assert created is True
    content = env_path.read_text()
    assert "OPENAI_API_KEY" in content
    assert "ANTHROPIC_API_KEY" in content
    assert "LAMIA_API_KEY" in content


def test_ensure_extensions_folder(tmp_path):
    ext_path = scaffold.ensure_extensions_folder(str(tmp_path), extensions_folder_name="extensions")

    assert os.path.isdir(ext_path)
    assert os.path.isdir(os.path.join(ext_path, "adapters"))
    assert os.path.isdir(os.path.join(ext_path, "validators"))


def test_create_full_default_config(tmp_path):
    config_path = tmp_path / "config.yaml"

    created = scaffold.create_full_default_config(str(config_path))

    assert created is True
    content = config_path.read_text()
    assert "model_chain:" in content
    assert "providers:" in content
    assert "openai:" in content
    assert "anthropic:" in content
    assert "ollama:" in content
    assert "gpt-4.1-nano" in content
    assert "claude-haiku-4-5-20251001" in content
    # Advanced params should be commented out, not active
    assert "temperature: 0.7" not in content or "# temperature: 0.7" in content
