"""Tests for LLMAmbiguityResolver."""

import pytest
from unittest.mock import Mock, AsyncMock

from lamia.engine.managers.web.selector_resolution.progressive.llm_ambiguity_resolver import (
    LLMAmbiguityResolver,
    AmbiguitySelectionModel,
)
from lamia.engine.managers.web.selector_resolution.progressive.progressive_selector_strategy import (
    ProgressiveSelectorStrategyIntent,
    ElementCount,
    Relationship,
    Strictness,
)
from lamia.validation.base import ValidationResult


@pytest.fixture
def mock_browser_adapter():
    """Create a mock browser adapter."""
    browser = Mock()
    browser.execute_script = AsyncMock(return_value=None)
    return browser


@pytest.fixture
def mock_llm_manager():
    """Create a mock LLM manager."""
    manager = Mock()
    manager.execute = AsyncMock()
    return manager


@pytest.fixture
def single_element_intent():
    """Create intent for single element selection."""
    return ProgressiveSelectorStrategyIntent(
        element_count=ElementCount.SINGLE,
        relationship=Relationship.NONE,
        strictness=Strictness.STRICT
    )


@pytest.fixture
def multiple_element_intent():
    """Create intent for multiple element selection."""
    return ProgressiveSelectorStrategyIntent(
        element_count=ElementCount.MULTIPLE,
        relationship=Relationship.GROUPED,
        strictness=Strictness.RELAXED
    )


class TestLLMAmbiguityResolverInit:
    """Test LLMAmbiguityResolver initialization."""

    def test_init_with_defaults(self, mock_browser_adapter, mock_llm_manager):
        """Test basic initialization with default max_elements_to_analyze."""
        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)

        assert resolver.browser == mock_browser_adapter
        assert resolver.llm_manager == mock_llm_manager
        assert resolver.max_elements_to_analyze == 100

    def test_init_with_custom_max_elements(self, mock_browser_adapter, mock_llm_manager):
        """Test initialization with custom max_elements_to_analyze."""
        resolver = LLMAmbiguityResolver(
            mock_browser_adapter, mock_llm_manager, max_elements_to_analyze=5
        )

        assert resolver.max_elements_to_analyze == 5


@pytest.mark.asyncio
class TestLLMAmbiguityResolverResolve:
    """Test LLMAmbiguityResolver resolve method."""

    async def test_resolve_returns_elements_when_single_or_empty(
        self, mock_browser_adapter, mock_llm_manager, single_element_intent
    ):
        """Test that resolve returns elements as-is when 0 or 1 element."""
        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)

        # Test empty list
        result = await resolver.resolve(
            description="button",
            elements=[],
            intent=single_element_intent,
            page_url="http://example.com"
        )
        assert result == []

        # Test single element
        element = Mock()
        result = await resolver.resolve(
            description="button",
            elements=[element],
            intent=single_element_intent,
            page_url="http://example.com"
        )
        assert result == [element]

    async def test_resolve_single_element_selection(
        self, mock_browser_adapter, mock_llm_manager, single_element_intent
    ):
        """Test LLM selecting single element from multiple candidates."""
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "Login", "id": "btn-login", "class_name": "btn", "role": "button", "name": None, "aria_label": "Log in"},
            {"tag": "button", "text": "Sign up", "id": "btn-signup", "class_name": "btn", "role": "button", "name": None, "aria_label": "Sign up"},
        ]

        selection = AmbiguitySelectionModel(selected_indices=[0], reason="First button matches login")
        mock_llm_manager.execute.return_value = ValidationResult(
            is_valid=True,
            result_type=selection
        )

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        element1 = Mock()
        element2 = Mock()
        elements = [element1, element2]

        result = await resolver.resolve(
            description="login button",
            elements=elements,
            intent=single_element_intent,
            page_url="http://example.com"
        )

        assert result == [element1]
        mock_llm_manager.execute.assert_called_once()

    async def test_resolve_multiple_element_selection(
        self, mock_browser_adapter, mock_llm_manager, multiple_element_intent
    ):
        """Test LLM selecting multiple elements."""
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "Option 1", "id": None, "class_name": "option", "role": None, "name": None, "aria_label": None},
            {"tag": "button", "text": "Option 2", "id": None, "class_name": "option", "role": None, "name": None, "aria_label": None},
            {"tag": "button", "text": "Option 3", "id": None, "class_name": "option", "role": None, "name": None, "aria_label": None},
        ]

        selection = AmbiguitySelectionModel(selected_indices=[0, 2], reason="Options 1 and 3 match")
        mock_llm_manager.execute.return_value = ValidationResult(
            is_valid=True,
            result_type=selection
        )

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        element1 = Mock()
        element2 = Mock()
        element3 = Mock()
        elements = [element1, element2, element3]

        result = await resolver.resolve(
            description="option buttons",
            elements=elements,
            intent=multiple_element_intent,
            page_url="http://example.com"
        )

        assert result == [element1, element3]

    async def test_resolve_returns_none_on_invalid_llm_response(
        self, mock_browser_adapter, mock_llm_manager, single_element_intent
    ):
        """Test that resolve returns None when LLM response is invalid."""
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "Login", "id": None, "class_name": None, "role": None, "name": None, "aria_label": None},
            {"tag": "button", "text": "Signup", "id": None, "class_name": None, "role": None, "name": None, "aria_label": None},
        ]

        mock_llm_manager.execute.return_value = ValidationResult(
            is_valid=False,
            error_message="Failed to parse response"
        )

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        elements = [Mock(), Mock()]

        result = await resolver.resolve(
            description="login button",
            elements=elements,
            intent=single_element_intent,
            page_url="http://example.com"
        )

        assert result is None

    async def test_resolve_returns_none_on_empty_selection(
        self, mock_browser_adapter, mock_llm_manager, single_element_intent
    ):
        """Test that resolve returns None when LLM selects no indices."""
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "Submit", "id": None, "class_name": None, "role": None, "name": None, "aria_label": None},
            {"tag": "button", "text": "Cancel", "id": None, "class_name": None, "role": None, "name": None, "aria_label": None},
        ]

        selection = AmbiguitySelectionModel(selected_indices=[], reason="None match")
        mock_llm_manager.execute.return_value = ValidationResult(
            is_valid=True,
            result_type=selection
        )

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        elements = [Mock(), Mock()]

        result = await resolver.resolve(
            description="login button",
            elements=elements,
            intent=single_element_intent,
            page_url="http://example.com"
        )

        assert result is None

    async def test_resolve_filters_out_of_range_indices(
        self, mock_browser_adapter, mock_llm_manager, single_element_intent
    ):
        """Test that resolve filters out indices that are out of range."""
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "OK", "id": None, "class_name": None, "role": None, "name": None, "aria_label": None},
            {"tag": "button", "text": "Cancel", "id": None, "class_name": None, "role": None, "name": None, "aria_label": None},
        ]

        # LLM returns invalid indices (5, 10) and one valid (0)
        selection = AmbiguitySelectionModel(selected_indices=[5, 0, 10], reason="Mixed indices")
        mock_llm_manager.execute.return_value = ValidationResult(
            is_valid=True,
            result_type=selection
        )

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        element1 = Mock()
        element2 = Mock()
        elements = [element1, element2]

        result = await resolver.resolve(
            description="button",
            elements=elements,
            intent=single_element_intent,
            page_url="http://example.com"
        )

        assert result == [element1]  # Only index 0 is valid

    async def test_resolve_limits_elements_to_max(
        self, mock_browser_adapter, mock_llm_manager, single_element_intent
    ):
        """Test that resolve only analyzes up to max_elements_to_analyze."""
        # Create summaries for only 3 elements (max)
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "1", "id": None, "class_name": None, "role": None, "name": None, "aria_label": None},
            {"tag": "button", "text": "2", "id": None, "class_name": None, "role": None, "name": None, "aria_label": None},
            {"tag": "button", "text": "3", "id": None, "class_name": None, "role": None, "name": None, "aria_label": None},
        ]

        selection = AmbiguitySelectionModel(selected_indices=[1], reason="Second button")
        mock_llm_manager.execute.return_value = ValidationResult(
            is_valid=True,
            result_type=selection
        )

        resolver = LLMAmbiguityResolver(
            mock_browser_adapter, mock_llm_manager, max_elements_to_analyze=3
        )
        
        # Pass 5 elements but only 3 should be summarized
        elements = [Mock() for _ in range(5)]

        result = await resolver.resolve(
            description="button",
            elements=elements,
            intent=single_element_intent,
            page_url="http://example.com"
        )

        # Should have called execute_script only 3 times (for first 3 elements)
        assert mock_browser_adapter.execute_script.call_count == 3
        assert result == [elements[1]]


@pytest.mark.asyncio
class TestLLMAmbiguityResolverHelpers:
    """Test helper methods."""

    async def test_summarize_elements(self, mock_browser_adapter, mock_llm_manager):
        """Test element summarization."""
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "Login", "id": "login-btn", "class_name": "btn primary", "role": "button", "name": "login", "aria_label": "Log in"},
            {"tag": "input", "text": "", "id": "email", "class_name": "form-control", "role": "textbox", "name": "email", "aria_label": "Email address"},
        ]

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        elements = [Mock(), Mock()]

        summaries = await resolver._summarize_elements(elements)

        assert len(summaries) == 2
        assert summaries[0]["tag"] == "button"
        assert summaries[0]["id"] == "login-btn"
        assert summaries[1]["tag"] == "input"
        assert summaries[1]["name"] == "email"

    async def test_summarize_elements_none_response(
        self, mock_browser_adapter, mock_llm_manager
    ):
        """Test that summarization handles None responses gracefully."""
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "OK", "id": None, "class_name": None, "role": None, "name": None, "aria_label": None},
            None,  # Script returns None for second element
        ]

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        elements = [Mock(), Mock()]

        summaries = await resolver._summarize_elements(elements)

        assert len(summaries) == 2
        assert summaries[0]["tag"] == "button"
        assert summaries[1] == {}  # None response becomes empty dict

