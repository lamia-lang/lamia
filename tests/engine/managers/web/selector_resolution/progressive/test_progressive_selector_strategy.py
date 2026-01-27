"""Tests for ProgressiveSelectorStrategy."""

import pytest
from unittest.mock import Mock, AsyncMock

from lamia.engine.managers.web.selector_resolution.progressive.progressive_selector_strategy import (
    ProgressiveSelectorStrategy,
    ProgressiveSelectorStrategyIntent,
    ProgressiveSelectorStrategyModel,
    ElementCount,
    Relationship,
    Strictness,
)
from lamia.validation.base import ValidationResult


@pytest.fixture
def mock_llm_executor():
    """Create a mock LLM executor."""
    executor = Mock()
    # Return a ValidationResult with a typed result
    mock_intent = ProgressiveSelectorStrategyIntent(
        element_count=ElementCount.SINGLE,
        relationship=Relationship.NONE,
        strictness=Strictness.STRICT
    )
    mock_model = ProgressiveSelectorStrategyModel(
        intent=mock_intent,
        selectors=["button.login"]
    )
    executor.execute = AsyncMock(return_value=ValidationResult(
        is_valid=True,
        result_type=mock_model
    ))
    return executor


class TestProgressiveSelectorStrategyInitialization:
    """Test ProgressiveSelectorStrategy initialization."""

    def test_init(self, mock_llm_executor):
        """Test basic initialization."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        assert strategy.llm_manager == mock_llm_executor
        assert strategy.progressive_selector_json_validator is not None


class TestProgressiveSelectorStrategyGeneration:
    """Test generate method."""

    @pytest.mark.asyncio
    async def test_generate_returns_plan(self, mock_llm_executor):
        """Test that generate returns a selector plan."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        intent, selectors = await strategy.generate("login button")

        assert "login button" in mock_llm_executor.execute.call_args[0][0].prompt
        assert isinstance(intent, ProgressiveSelectorStrategyIntent)
        assert isinstance(selectors, list)
        assert intent.element_count == ElementCount.SINGLE
        assert intent.relationship == Relationship.NONE
        assert intent.strictness == Strictness.STRICT
        assert len(selectors) == 1
        assert "button.login" in selectors

    @pytest.mark.asyncio
    async def test_generate_with_failed_selectors(self, mock_llm_executor):
        """Test generating plan with previously failed selectors."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        failed_selectors = ["button.old", "#old-btn"]
        intent, selectors = await strategy.generate("login button", failed_selectors)

        prompt = mock_llm_executor.execute.call_args[0][0].prompt
        assert "login button" in prompt
        assert "button.old" in prompt
        assert "#old-btn" in prompt
        assert isinstance(intent, ProgressiveSelectorStrategyIntent)
        assert isinstance(selectors, list)
        assert len(selectors) == 1
        assert "button.login" in selectors

    @pytest.mark.asyncio
    async def test_generate_raises_on_invalid_response(self, mock_llm_executor):
        """Test that generate raises ValueError on invalid LLM response."""
        mock_llm_executor.execute = AsyncMock(return_value=ValidationResult(
            is_valid=False,
            error_message="Invalid JSON"
        ))

        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        with pytest.raises(ValueError, match="Failed to generate selectors with progressive strategy"):
            await strategy.generate("login button")

