import os
import tempfile
import yaml
import pytest
from unittest import mock
from lamia.cli import interactive_mode
from lamia.engine.engine import LamiaEngine
import subprocess
import sys
import shutil
import lamia.cli as cli_mod

@pytest.mark.parametrize("cli_args", [
    ["sum.py"],
    ["--file", "sum.py"]
])
def test_cli_file_modes(tmp_path, cli_args):
    # Copy sum.py and config.yaml to tmp_path
    test_dir = tmp_path
    shutil.copy("sum.py", test_dir / "sum.py")
    shutil.copy("config.yaml", test_dir / "config.yaml")
    # Run the CLI with the given arguments
    cmd = [sys.executable, "-m", "lamia.cli"] + cli_args + ["--config", str(test_dir / "config.yaml")]
    result = subprocess.run(cmd, cwd=test_dir, capture_output=True, text=True)
    # Should not error
    assert result.returncode == 0, f"stderr: {result.stderr}"
    # Should print the result of sum(10, 15) = 160 (since multiply(10, 15) = 150 + 15)
    assert "160" in result.stdout 

def test_import_cli():
    assert cli_mod is not None 