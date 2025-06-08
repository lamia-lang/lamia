import pytest
from lamia.engine import config_manager

def test_import_config_manager():
    assert config_manager is not None 