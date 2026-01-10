import pytest
from lamia.validation import validator_loader

def test_import_validator_loader():
    """Test that validator_loader module can be imported."""
    assert validator_loader is not None
    assert hasattr(validator_loader, 'ValidatorLoader') 