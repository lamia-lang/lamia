import pytest
from lamia.utils import dependencies

def test_import_dependencies():
    assert dependencies is not None 