"""Tests for _internal_types module."""

import pytest
from dataclasses import FrozenInstanceError
from lamia._internal_types.model_retry import ModelWithRetries
from lamia import LLMModel


class TestModelWithRetries:
    """Test ModelWithRetries dataclass."""

    def test_creation_with_defaults(self):
        """Test creating ModelWithRetries with default retries."""
        model = LLMModel(name="test-model")
        mwr = ModelWithRetries(model=model)
        assert mwr.model == model
        assert mwr.retries == 1

    def test_creation_with_custom_retries(self):
        """Test creating ModelWithRetries with custom retries."""
        model = LLMModel(name="test-model")
        mwr = ModelWithRetries(model=model, retries=5)
        assert mwr.model == model
        assert mwr.retries == 5

    def test_is_frozen(self):
        """Test that ModelWithRetries is immutable."""
        model = LLMModel(name="test-model")
        mwr = ModelWithRetries(model=model)
        with pytest.raises(FrozenInstanceError):
            mwr.retries = 10

    def test_equality(self):
        """Test equality comparison between instances."""
        model = LLMModel(name="test-model")
        mwr1 = ModelWithRetries(model=model, retries=3)
        mwr2 = ModelWithRetries(model=model, retries=3)
        assert mwr1 == mwr2

    def test_inequality_different_retries(self):
        """Test inequality with different retries."""
        model = LLMModel(name="test-model")
        mwr1 = ModelWithRetries(model=model, retries=1)
        mwr2 = ModelWithRetries(model=model, retries=5)
        assert mwr1 != mwr2

    def test_has_slots(self):
        """Test that ModelWithRetries uses slots for memory efficiency."""
        assert '__slots__' in dir(ModelWithRetries)

    def test_zero_retries(self):
        """Test ModelWithRetries with zero retries."""
        model = LLMModel(name="test-model")
        mwr = ModelWithRetries(model=model, retries=0)
        assert mwr.retries == 0