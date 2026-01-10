import pytest
from lamia.cli import scaffold

def test_import_scaffold():
    assert scaffold is not None 