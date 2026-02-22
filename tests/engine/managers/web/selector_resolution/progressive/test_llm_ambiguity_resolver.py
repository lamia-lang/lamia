"""Tests for LLMAmbiguityResolver."""

import pytest
from unittest.mock import Mock, AsyncMock

from lamia.engine.managers.web.selector_resolution.progressive.llm_ambiguity_resolver import (
    LLMAmbiguityResolver,
    AmbiguitySelectionModel,
    MAX_ATTRIBUTE_VALUE_LENGTH,
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
class TestLLMAmbiguityResolverResolveAmbiguity:
    """Test LLMAmbiguityResolver resolve_ambiguity method."""

    async def test_returns_elements_when_single_or_empty(
        self, mock_browser_adapter, mock_llm_manager, single_element_intent
    ):
        """Test that resolve_ambiguity returns elements as-is when 0 or 1 element."""
        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)

        # Test empty list
        result = await resolver.resolve_ambiguity(
            description="button",
            elements=[],
            intent=single_element_intent,
            page_url="http://example.com"
        )
        assert result == []

        # Test single element
        element = Mock()
        result = await resolver.resolve_ambiguity(
            description="button",
            elements=[element],
            intent=single_element_intent,
            page_url="http://example.com"
        )
        assert result == [element]

    async def test_single_element_selection_with_json(
        self, mock_browser_adapter, mock_llm_manager, single_element_intent
    ):
        """Test LLM selecting single element using JSON summaries."""
        # JSON summary returns all attributes
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "Login", "attributes": {"id": "btn-login", "class": "btn primary", "data-testid": "login-btn"}},
            {"tag": "button", "text": "Sign up", "attributes": {"id": "btn-signup", "class": "btn", "data-testid": "signup-btn"}},
        ]

        selection = AmbiguitySelectionModel(selected_indices=[0], reason="First button matches login")
        mock_llm_manager.execute.return_value = ValidationResult(
            is_valid=True,
            typed_result=selection
        )

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        element1 = Mock()
        element2 = Mock()
        elements = [element1, element2]

        result = await resolver.resolve_ambiguity(
            description="login button",
            elements=elements,
            intent=single_element_intent,
            page_url="http://example.com"
        )

        assert result == [element1]
        mock_llm_manager.execute.assert_called_once()

    async def test_multiple_element_selection(
        self, mock_browser_adapter, mock_llm_manager, multiple_element_intent
    ):
        """Test LLM selecting multiple elements."""
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "Option 1", "attributes": {"class": "option"}},
            {"tag": "button", "text": "Option 2", "attributes": {"class": "option"}},
            {"tag": "button", "text": "Option 3", "attributes": {"class": "option"}},
        ]

        selection = AmbiguitySelectionModel(selected_indices=[0, 2], reason="Options 1 and 3 match")
        mock_llm_manager.execute.return_value = ValidationResult(
            is_valid=True,
            typed_result=selection
        )

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        element1 = Mock()
        element2 = Mock()
        element3 = Mock()
        elements = [element1, element2, element3]

        result = await resolver.resolve_ambiguity(
            description="option buttons",
            elements=elements,
            intent=multiple_element_intent,
            page_url="http://example.com"
        )

        assert result == [element1, element3]

    async def test_fallback_to_outer_html_when_json_fails(
        self, mock_browser_adapter, mock_llm_manager, single_element_intent
    ):
        """Test fallback to outerHTML when JSON summary resolution fails."""
        # First call: JSON summaries
        # Second call: outerHTML snippets (after JSON fails)
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "Submit", "attributes": {}},
            {"tag": "button", "text": "Cancel", "attributes": {}},
            "<button class='btn'>Submit</button>",  # outerHTML fallback
            "<button class='btn'>Cancel</button>",
        ]

        # First LLM call fails (JSON), second succeeds (outerHTML)
        selection = AmbiguitySelectionModel(selected_indices=[0], reason="Submit button")
        mock_llm_manager.execute.side_effect = [
            ValidationResult(is_valid=False, error_message="Failed"),
            ValidationResult(is_valid=True, typed_result=selection),
        ]

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        element1 = Mock()
        element2 = Mock()
        elements = [element1, element2]

        result = await resolver.resolve_ambiguity(
            description="submit button",
            elements=elements,
            intent=single_element_intent,
            page_url="http://example.com"
        )

        assert result == [element1]
        assert mock_llm_manager.execute.call_count == 2

    async def test_returns_none_when_both_phases_fail(
        self, mock_browser_adapter, mock_llm_manager, single_element_intent
    ):
        """Test returns None when both JSON and outerHTML resolution fail."""
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "A", "attributes": {}},
            {"tag": "button", "text": "B", "attributes": {}},
            "<button>A</button>",
            "<button>B</button>",
        ]

        # Both LLM calls fail
        mock_llm_manager.execute.return_value = ValidationResult(
            is_valid=False,
            error_message="Failed to parse"
        )

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        elements = [Mock(), Mock()]

        result = await resolver.resolve_ambiguity(
            description="button",
            elements=elements,
            intent=single_element_intent,
            page_url="http://example.com"
        )

        assert result is None
        assert mock_llm_manager.execute.call_count == 2

    async def test_returns_none_on_empty_selection(
        self, mock_browser_adapter, mock_llm_manager, single_element_intent
    ):
        """Test returns None when LLM selects no indices in both phases."""
        # JSON summaries for phase 1, outerHTML for phase 2
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "Submit", "attributes": {}},
            {"tag": "button", "text": "Cancel", "attributes": {}},
            "<button>Submit</button>",  # outerHTML fallback
            "<button>Cancel</button>",
        ]

        # Both phases return empty selection
        selection = AmbiguitySelectionModel(selected_indices=[], reason="None match")
        mock_llm_manager.execute.return_value = ValidationResult(
            is_valid=True,
            typed_result=selection
        )

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        elements = [Mock(), Mock()]

        result = await resolver.resolve_ambiguity(
            description="login button",
            elements=elements,
            intent=single_element_intent,
            page_url="http://example.com"
        )

        assert result is None
        # Both JSON and outerHTML phases were tried
        assert mock_llm_manager.execute.call_count == 2

    async def test_filters_out_of_range_indices(
        self, mock_browser_adapter, mock_llm_manager, single_element_intent
    ):
        """Test that out-of-range indices are filtered."""
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "OK", "attributes": {}},
            {"tag": "button", "text": "Cancel", "attributes": {}},
        ]

        # LLM returns invalid indices (5, 10) and one valid (0)
        selection = AmbiguitySelectionModel(selected_indices=[5, 0, 10], reason="Mixed indices")
        mock_llm_manager.execute.return_value = ValidationResult(
            is_valid=True,
            typed_result=selection
        )

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        element1 = Mock()
        element2 = Mock()
        elements = [element1, element2]

        result = await resolver.resolve_ambiguity(
            description="button",
            elements=elements,
            intent=single_element_intent,
            page_url="http://example.com"
        )

        assert result == [element1]

    async def test_limits_elements_to_max(
        self, mock_browser_adapter, mock_llm_manager, single_element_intent
    ):
        """Test that only max_elements_to_analyze elements are processed."""
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "1", "attributes": {}},
            {"tag": "button", "text": "2", "attributes": {}},
            {"tag": "button", "text": "3", "attributes": {}},
        ]

        selection = AmbiguitySelectionModel(selected_indices=[1], reason="Second button")
        mock_llm_manager.execute.return_value = ValidationResult(
            is_valid=True,
            typed_result=selection
        )

        resolver = LLMAmbiguityResolver(
            mock_browser_adapter, mock_llm_manager, max_elements_to_analyze=3
        )

        # Pass 5 elements but only 3 should be summarized
        elements = [Mock() for _ in range(5)]

        result = await resolver.resolve_ambiguity(
            description="button",
            elements=elements,
            intent=single_element_intent,
            page_url="http://example.com"
        )

        # Should have called execute_script only 3 times (for first 3 elements)
        assert mock_browser_adapter.execute_script.call_count == 3
        assert result == [elements[1]]


@pytest.mark.asyncio
class TestLLMAmbiguityResolverJsonSummary:
    """Test JSON summary functionality."""

    async def test_summarize_captures_all_attributes(self, mock_browser_adapter, mock_llm_manager):
        """Test that JSON summary captures ALL attributes including data-* and custom ones."""
        mock_browser_adapter.execute_script.return_value = {
            "tag": "button",
            "text": "Login",
            "attributes": {
                "id": "login-btn",
                "class": "btn primary",
                "data-testid": "login-button",
                "data-cy": "submit",
                "aria-label": "Log in to your account",
                "ng-click": "doLogin()",
                "custom-attr": "value"
            }
        }

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        summaries = await resolver._summarize_elements_json([Mock()])

        assert len(summaries) == 1
        attrs = summaries[0]["attributes"]
        assert attrs["data-testid"] == "login-button"
        assert attrs["data-cy"] == "submit"
        assert attrs["ng-click"] == "doLogin()"
        assert attrs["custom-attr"] == "value"

    async def test_summarize_handles_none_response(self, mock_browser_adapter, mock_llm_manager):
        """Test that JSON summary handles None responses gracefully."""
        mock_browser_adapter.execute_script.side_effect = [
            {"tag": "button", "text": "OK", "attributes": {"id": "ok"}},
            None,  # Script returns None for second element
        ]

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        summaries = await resolver._summarize_elements_json([Mock(), Mock()])

        assert len(summaries) == 2
        assert summaries[0]["tag"] == "button"
        assert summaries[1] == {"tag": None, "text": None, "attributes": {}}


@pytest.mark.asyncio
class TestLLMAmbiguityResolverOuterHtml:
    """Test outerHTML fallback functionality."""

    async def test_get_outer_html_snippets(self, mock_browser_adapter, mock_llm_manager):
        """Test getting truncated outerHTML snippets."""
        mock_browser_adapter.execute_script.side_effect = [
            "<button id='btn1' class='primary'>Click Me</button>",
            "<input type='text' name='email' placeholder='Enter email'>",
        ]

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        snippets = await resolver._get_outer_html_snippets([Mock(), Mock()])

        assert len(snippets) == 2
        assert "<button" in snippets[0]
        assert "<input" in snippets[1]

    async def test_outer_html_handles_none(self, mock_browser_adapter, mock_llm_manager):
        """Test that outerHTML handles None gracefully."""
        mock_browser_adapter.execute_script.side_effect = [
            "<button>OK</button>",
            None,
        ]

        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)
        snippets = await resolver._get_outer_html_snippets([Mock(), Mock()])

        assert snippets[0] == "<button>OK</button>"
        assert snippets[1] == "<unknown>"


class TestLLMAmbiguityResolverPromptBuilding:
    """Test prompt building methods."""

    def test_build_json_prompt_includes_all_attributes(self, mock_browser_adapter, mock_llm_manager):
        """Test that JSON prompt includes all attributes."""
        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)

        summaries = [
            {"tag": "button", "text": "Login", "attributes": {"id": "btn", "data-testid": "login"}},
            {"tag": "button", "text": "Signup", "attributes": {"class": "secondary"}},
        ]
        intent = ProgressiveSelectorStrategyIntent(
            element_count=ElementCount.SINGLE,
            relationship=Relationship.NONE,
            strictness=Strictness.STRICT
        )

        prompt = resolver._build_json_prompt("login button", summaries, intent)

        assert "data-testid=login" in prompt
        assert "id=btn" in prompt
        assert "class=secondary" in prompt
        assert "Return exactly 1 index" in prompt

    def test_build_outer_html_prompt(self, mock_browser_adapter, mock_llm_manager):
        """Test that outerHTML prompt is built correctly."""
        resolver = LLMAmbiguityResolver(mock_browser_adapter, mock_llm_manager)

        snippets = [
            "<button id='login'>Login</button>",
            "<button id='signup'>Signup</button>",
        ]
        intent = ProgressiveSelectorStrategyIntent(
            element_count=ElementCount.MULTIPLE,
            relationship=Relationship.NONE,
            strictness=Strictness.RELAXED
        )

        prompt = resolver._build_outer_html_prompt("buttons", snippets, intent)

        assert "<button id='login'>Login</button>" in prompt
        assert "HTML" in prompt
        assert "Return all matching indices" in prompt
