"""Integration tests for selector resolution."""

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
from lamia.engine.managers.web.selector_resolution.progressive.relationship_validator import ElementRelationshipValidator
from lamia.engine.managers.web.selector_resolution.progressive.ambiguity_resolver import AmbiguityResolver
from lamia.engine.managers.web.selector_resolution.progressive.strategy_resolver import ProgressiveSelectorResolver
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


@pytest.fixture
def mock_browser_adapter():
    """Create a mock browser adapter."""
    browser = Mock()
    browser.get_elements = AsyncMock(return_value=[])
    browser.execute_script = AsyncMock(return_value=None)
    return browser


@pytest.fixture
def mock_cache():
    """Create a mock cache."""
    cache = Mock()
    cache.get = Mock(return_value=None)
    cache.set = Mock()
    return cache


@pytest.mark.asyncio
class TestSelectorResolutionIntegration:
    """Integration tests for selector resolution."""

    async def test_progressive_resolution_flow(self, mock_llm_executor, mock_browser_adapter, mock_cache):
        """Test full progressive resolution flow."""
        # Setup mock LLM response with typed result
        mock_intent = ProgressiveSelectorStrategyIntent(
            element_count=ElementCount.SINGLE,
            relationship=Relationship.NONE,
            strictness=Strictness.STRICT
        )
        mock_model = ProgressiveSelectorStrategyModel(
            intent=mock_intent,
            selectors=["button.login"]
        )
        mock_llm_executor.execute.return_value = ValidationResult(
            is_valid=True,
            result_type=mock_model
        )

        # Setup mock browser to find elements
        mock_elements = [Mock()]
        mock_browser_adapter.get_elements.return_value = mock_elements
        mock_browser_adapter.execute_script.return_value = True

        strategy_gen = ProgressiveSelectorStrategy(mock_llm_executor)
        validator = ElementRelationshipValidator(mock_browser_adapter)
        resolver = AmbiguityResolver(mock_browser_adapter, mock_cache)

        # Generate strategies
        intent, selectors = await strategy_gen.generate("login button")

        assert intent.element_count == ElementCount.SINGLE
        assert len(selectors) > 0

