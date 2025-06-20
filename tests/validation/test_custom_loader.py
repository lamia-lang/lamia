import pytest
from lamia.validation import custom_loader

def test_import_custom_loader():
    assert custom_loader is not None 