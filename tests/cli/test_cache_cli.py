import os

from lamia.cli.cache_cli import CacheCLI


def test_list_cache_empty(capsys, tmp_path):
    cli = CacheCLI(cache_dir=str(tmp_path))

    cli.list_cache()

    captured = capsys.readouterr()
    assert "Cache is empty" in captured.out


def test_add_selector_and_load_cache(tmp_path):
    cli = CacheCLI(cache_dir=str(tmp_path))

    cli.add_selector("button.submit", ".submit-btn", "https://example.com")

    cache_data = cli._load_cache()
    assert "button.submit|https://example.com" in cache_data
    assert cache_data["button.submit|https://example.com"] == ".submit-btn"
    assert os.path.exists(cli.cache_file)


def test_clear_cache_all_entries(capsys, tmp_path):
    cli = CacheCLI(cache_dir=str(tmp_path))

    cli.add_selector("button.submit", ".submit-btn", "https://example.com")

    cli.clear_cache(all_entries=True)

    captured = capsys.readouterr()
    assert "Cleared entire cache" in captured.out
    assert cli._load_cache() == {}
