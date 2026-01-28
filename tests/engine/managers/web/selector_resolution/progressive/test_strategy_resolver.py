"""Tests for ProgressiveSelectorResolver."""

import pytest
from unittest.mock import Mock, AsyncMock

from lamia.engine.managers.web.selector_resolution.progressive.progressive_selector_strategy import (
    ProgressiveSelectorStrategyIntent,
    ProgressiveSelectorStrategyModel,
    ElementCount,
    Relationship,
    Strictness,
)
from lamia.engine.managers.web.selector_resolution.progressive.strategy_resolver import (
    ProgressiveSelectorResolver,
    ResolutionOutcome,
)
from lamia.engine.managers.web.selector_resolution.progressive.relationship_validator import ElementRelationshipValidator
from lamia.validation.base import ValidationResult


@pytest.fixture
def mock_llm_manager():
    """Create a mock LLM manager."""
    manager = Mock()
    mock_intent = ProgressiveSelectorStrategyIntent(
        element_count=ElementCount.SINGLE,
        relationship=Relationship.NONE,
        strictness=Strictness.STRICT
    )
    mock_model = ProgressiveSelectorStrategyModel(
        intent=mock_intent,
        selectors=["button.login", "#login-btn", "button[type='submit']"]
    )
    manager.execute = AsyncMock(return_value=ValidationResult(
        is_valid=True,
        result_type=mock_model
    ))
    return manager


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
    cache.set = AsyncMock()
    return cache


@pytest.fixture
def mock_config_provider():
    """Create a mock config provider."""
    config = Mock()
    config.is_human_in_loop_enabled = Mock(return_value=False)
    config.get_web_config = Mock(return_value={})
    return config


class TestProgressiveSelectorResolverInit:
    """Test ProgressiveSelectorResolver initialization."""

    def test_init(self, mock_llm_manager, mock_browser_adapter, mock_cache, mock_config_provider):
        """Test basic initialization."""
        resolver = ProgressiveSelectorResolver(
            mock_browser_adapter,
            mock_llm_manager,
            mock_cache,
            mock_config_provider
        )

        assert resolver.browser == mock_browser_adapter
        assert resolver.llm_manager == mock_llm_manager
        assert resolver.config_provider == mock_config_provider

    def test_init_creates_llm_resolver_only_when_human_disabled(
        self, mock_llm_manager, mock_browser_adapter, mock_cache, mock_config_provider
    ):
        """Test that only LLM resolver is created when human_in_loop is disabled."""
        mock_config_provider.is_human_in_loop_enabled.return_value = False

        resolver = ProgressiveSelectorResolver(
            mock_browser_adapter,
            mock_llm_manager,
            mock_cache,
            mock_config_provider
        )

        assert len(resolver._ambiguity_resolvers) == 1

    def test_init_creates_both_resolvers_when_human_enabled(
        self, mock_llm_manager, mock_browser_adapter, mock_cache, mock_config_provider
    ):
        """Test that both resolvers are created when human_in_loop is enabled."""
        mock_config_provider.is_human_in_loop_enabled.return_value = True

        resolver = ProgressiveSelectorResolver(
            mock_browser_adapter,
            mock_llm_manager,
            mock_cache,
            mock_config_provider
        )

        assert len(resolver._ambiguity_resolvers) == 2


class TestResolutionOutcome:
    """Test ResolutionOutcome dataclass."""

    def test_is_success_true_when_selector_and_elements(self):
        """Test is_success returns True when selector and elements exist."""
        outcome = ResolutionOutcome(
            selector="button.login",
            elements=[Mock()],
            had_matches=True
        )

        assert outcome.is_success is True

    def test_is_success_false_when_no_selector(self):
        """Test is_success returns False when selector is None."""
        outcome = ResolutionOutcome(
            selector=None,
            elements=[Mock()],
            had_matches=True
        )

        assert outcome.is_success is False

    def test_is_success_false_when_no_elements(self):
        """Test is_success returns False when elements list is empty."""
        outcome = ResolutionOutcome(
            selector="button.login",
            elements=[],
            had_matches=False
        )

        assert outcome.is_success is False


@pytest.mark.asyncio
class TestProgressiveSelectorResolverResolve:
    """Test ProgressiveSelectorResolver resolve method."""

    async def test_resolve_success_on_first_selector(
        self, mock_llm_manager, mock_browser_adapter, mock_cache, mock_config_provider
    ):
        """Test successful resolution with first selector finding element."""
        mock_element = Mock()
        mock_browser_adapter.get_elements.return_value = [mock_element]

        resolver = ProgressiveSelectorResolver(
            mock_browser_adapter,
            mock_llm_manager,
            mock_cache,
            mock_config_provider
        )

        selector, elements = await resolver.resolve("login button", "http://example.com")

        assert selector == "button.login"
        assert elements == [mock_element]

    async def test_resolve_tries_multiple_selectors(
        self, mock_llm_manager, mock_browser_adapter, mock_cache, mock_config_provider
    ):
        """Test that resolver tries multiple selectors until one works."""
        mock_element = Mock()
        # First selector fails, second selector works
        mock_browser_adapter.get_elements.side_effect = [
            [],  # button.login fails
            [mock_element],  # #login-btn succeeds
        ]

        resolver = ProgressiveSelectorResolver(
            mock_browser_adapter,
            mock_llm_manager,
            mock_cache,
            mock_config_provider
        )

        selector, elements = await resolver.resolve("login button", "http://example.com")

        assert selector == "#login-btn"
        assert elements == [mock_element]
        assert mock_browser_adapter.get_elements.call_count == 2

    async def test_resolve_raises_when_no_selectors(
        self, mock_llm_manager, mock_browser_adapter, mock_cache, mock_config_provider
    ):
        """Test that resolve raises ValueError when no selectors are generated."""
        mock_intent = ProgressiveSelectorStrategyIntent(
            element_count=ElementCount.SINGLE,
            relationship=Relationship.NONE,
            strictness=Strictness.STRICT
        )
        mock_model = ProgressiveSelectorStrategyModel(
            intent=mock_intent,
            selectors=[]  # Empty selectors
        )
        mock_llm_manager.execute.return_value = ValidationResult(
            is_valid=True,
            result_type=mock_model
        )

        resolver = ProgressiveSelectorResolver(
            mock_browser_adapter,
            mock_llm_manager,
            mock_cache,
            mock_config_provider
        )

        with pytest.raises(ValueError, match="Failed to get selectors"):
            await resolver.resolve("login button", "http://example.com")

    async def test_resolve_raises_after_max_retries(
        self, mock_llm_manager, mock_browser_adapter, mock_cache, mock_config_provider
    ):
        """Test that resolve raises ValueError after max retries."""
        # All selectors fail to find elements
        mock_browser_adapter.get_elements.return_value = []

        resolver = ProgressiveSelectorResolver(
            mock_browser_adapter,
            mock_llm_manager,
            mock_cache,
            mock_config_provider
        )

        with pytest.raises(ValueError, match="Could not resolve"):
            await resolver.resolve("login button", "http://example.com")


@pytest.mark.asyncio
class TestProgressiveSelectorResolverAmbiguity:
    """Test ambiguity detection and resolution."""

    async def test_is_ambiguous_single_intent_multiple_elements(
        self, mock_llm_manager, mock_browser_adapter, mock_cache, mock_config_provider
    ):
        """Test ambiguity detection for single element intent with multiple matches."""
        resolver = ProgressiveSelectorResolver(
            mock_browser_adapter,
            mock_llm_manager,
            mock_cache,
            mock_config_provider
        )

        intent = ProgressiveSelectorStrategyIntent(
            element_count=ElementCount.SINGLE,
            relationship=Relationship.NONE,
            strictness=Strictness.STRICT
        )

        # Multiple elements when expecting single = ambiguous
        assert resolver._is_ambiguous([Mock(), Mock()], intent) is True

        # Single element when expecting single = not ambiguous
        assert resolver._is_ambiguous([Mock()], intent) is False

@pytest.mark.asyncio
class TestProgressiveSelectorResolverValidation:
    """Test validation integration."""

    async def test_resolve_validates_element_relationships(
        self, mock_llm_manager, mock_browser_adapter, mock_cache, mock_config_provider
    ):
        """Test that resolver validates element relationships."""
        # Setup: multiple element intent with grouped relationship
        mock_intent = ProgressiveSelectorStrategyIntent(
            element_count=ElementCount.MULTIPLE,
            relationship=Relationship.GROUPED,
            strictness=Strictness.STRICT
        )
        mock_model = ProgressiveSelectorStrategyModel(
            intent=mock_intent,
            selectors=["button.option"]
        )
        mock_llm_manager.execute.return_value = ValidationResult(
            is_valid=True,
            result_type=mock_model
        )

        # Elements found but validation will fail (no common ancestor set up)
        mock_browser_adapter.get_elements.return_value = [Mock(), Mock()]
        mock_browser_adapter.execute_script.return_value = None  # No parent = validation fails

        resolver = ProgressiveSelectorResolver(
            mock_browser_adapter,
            mock_llm_manager,
            mock_cache,
            mock_config_provider
        )

        # Should raise because validation fails and no more selectors/retries
        with pytest.raises(ValueError, match="Could not resolve"):
            await resolver.resolve("grouped buttons", "http://example.com")
