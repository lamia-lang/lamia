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
    GENERIC_HTML_TAGS,
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
        typed_result=mock_model
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
        """Test that generate returns a selector plan with generic tag appended."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        intent, selectors = await strategy.generate("login button")

        assert "login button" in mock_llm_executor.execute.call_args[0][0].prompt
        assert isinstance(intent, ProgressiveSelectorStrategyIntent)
        assert isinstance(selectors, list)
        assert intent.element_count == ElementCount.SINGLE
        assert intent.relationship == Relationship.NONE
        assert intent.strictness == Strictness.STRICT
        # Generic tag "button" is appended since "button.login" is not generic
        assert len(selectors) == 2
        assert selectors[0] == "button.login"
        assert selectors[-1] == "button"

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
        # Generic tag "button" is appended since "button.login" is not generic
        assert len(selectors) == 2
        assert selectors[0] == "button.login"
        assert selectors[-1] == "button"

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

    @pytest.mark.asyncio
    async def test_generate_appends_generic_tag_if_missing(self, mock_llm_executor):
        """Test that generate appends a generic tag if the last selector is not generic."""
        mock_intent = ProgressiveSelectorStrategyIntent(
            element_count=ElementCount.SINGLE,
            relationship=Relationship.NONE,
            strictness=Strictness.STRICT
        )
        mock_model = ProgressiveSelectorStrategyModel(
            intent=mock_intent,
            selectors=["button.login", "button[type='submit']"]
        )
        mock_llm_executor.execute = AsyncMock(return_value=ValidationResult(
            is_valid=True,
            typed_result=mock_model
        ))

        strategy = ProgressiveSelectorStrategy(mock_llm_executor)
        intent, selectors = await strategy.generate("login button")

        assert selectors[-1] == "button"
        assert len(selectors) == 3

    @pytest.mark.asyncio
    async def test_generate_does_not_duplicate_generic_tag(self, mock_llm_executor):
        """Test that generate doesn't add tag if last selector is already generic."""
        mock_intent = ProgressiveSelectorStrategyIntent(
            element_count=ElementCount.SINGLE,
            relationship=Relationship.NONE,
            strictness=Strictness.STRICT
        )
        mock_model = ProgressiveSelectorStrategyModel(
            intent=mock_intent,
            selectors=["button.login", "button"]
        )
        mock_llm_executor.execute = AsyncMock(return_value=ValidationResult(
            is_valid=True,
            typed_result=mock_model
        ))

        strategy = ProgressiveSelectorStrategy(mock_llm_executor)
        intent, selectors = await strategy.generate("login button")

        assert selectors == ["button.login", "button"]
        assert len(selectors) == 2


class TestGenericTagValidation:
    """Tests for generic tag selector validation methods."""

    @pytest.fixture
    def strategy(self, mock_llm_executor):
        return ProgressiveSelectorStrategy(mock_llm_executor)

    @pytest.fixture
    def mock_llm_executor(self):
        return Mock()

    class TestIsGenericTagSelector:
        """Tests for _is_generic_tag_selector method."""

        @pytest.fixture
        def strategy(self):
            return ProgressiveSelectorStrategy(Mock())

        @pytest.mark.parametrize("selector", [
            "button",
            "div",
            "a",
            "input",
            "span",
            "table",
            "li",
            "h1",
            "p",
        ])
        def test_css_generic_tags_are_recognized(self, strategy, selector):
            """Test that plain CSS tag selectors are recognized as generic."""
            assert strategy._is_generic_tag_selector(selector) is True

        @pytest.mark.parametrize("selector", [
            "//button",
            "//div",
            "//a",
            "//input",
        ])
        def test_xpath_generic_tags_are_recognized(self, strategy, selector):
            """Test that XPath tag selectors are recognized as generic."""
            assert strategy._is_generic_tag_selector(selector) is True

        @pytest.mark.parametrize("selector", [
            "button.class",
            "div#id",
            "a[href]",
            "input[type='text']",
            ".class",
            "#id",
            "[data-test]",
            "button:hover",
            "div > span",
            "//button[@class='login']",
            "//div[contains(text(), 'hello')]",
        ])
        def test_non_generic_selectors_are_rejected(self, strategy, selector):
            """Test that selectors with classes, IDs, attributes etc. are not generic."""
            assert strategy._is_generic_tag_selector(selector) is False

        @pytest.mark.parametrize("selector", [
            "customtag",
            "mycomponent",
            "//unknowntag",
        ])
        def test_unknown_tags_are_rejected(self, strategy, selector):
            """Test that unknown/custom tags are not considered generic."""
            assert strategy._is_generic_tag_selector(selector) is False

    class TestExtractTagFromSelector:
        """Tests for _extract_tag_from_selector method."""

        @pytest.fixture
        def strategy(self):
            return ProgressiveSelectorStrategy(Mock())

        @pytest.mark.parametrize("selector,expected", [
            ("button.login", "button"),
            ("div#container", "div"),
            ("a[href='#']", "a"),
            ("input[type='text']", "input"),
            ("span.highlight.bold", "span"),
            ("table.data-table", "table"),
        ])
        def test_extract_from_css_selectors(self, strategy, selector, expected):
            """Test tag extraction from CSS selectors."""
            assert strategy._extract_tag_from_selector(selector) == expected

        @pytest.mark.parametrize("selector,expected", [
            ("div.container > input[type='text']", "input"),
            ("div.container > div.item > input[type='text'][name*='q'] + input", "input"),
            ("ul > li > a.link", "a"),
            ("form div.field > label + input", "input"),
            ("section article > p", "p"),
        ])
        def test_extract_target_tag_from_compound_css(self, strategy, selector, expected):
            """Rightmost tag (the target) should be extracted, not the container."""
            assert strategy._extract_tag_from_selector(selector) == expected

        @pytest.mark.parametrize("selector,expected", [
            ("//button[@class='login']", "button"),
            ("//div[contains(text(), 'hello')]", "div"),
            ("//a[@href]", "a"),
            ("//input[@type='submit']", "input"),
        ])
        def test_extract_from_xpath_selectors(self, strategy, selector, expected):
            """Test tag extraction from XPath selectors."""
            assert strategy._extract_tag_from_selector(selector) == expected

        @pytest.mark.parametrize("selector", [
            ".class-only",
            "#id-only",
            "[data-attribute]",
            "*",
        ])
        def test_returns_none_for_tagless_selectors(self, strategy, selector):
            """Test that selectors without tags return None."""
            assert strategy._extract_tag_from_selector(selector) is None

    class TestEnsureGenericTagSuffix:
        """Tests for _ensure_generic_tag_suffix method."""

        @pytest.fixture
        def strategy(self):
            return ProgressiveSelectorStrategy(Mock())

        def test_empty_list_returns_empty(self, strategy):
            """Test that empty list is returned unchanged."""
            assert strategy._ensure_generic_tag_suffix([]) == []

        def test_already_generic_returns_unchanged(self, strategy):
            """Test that list ending with generic tag is unchanged."""
            selectors = ["button.login", "button"]
            result = strategy._ensure_generic_tag_suffix(selectors)
            assert result == selectors

        def test_appends_extracted_tag(self, strategy):
            """Test that tag is extracted and appended when last is not generic."""
            selectors = ["button.login", "button[type='submit']"]
            result = strategy._ensure_generic_tag_suffix(selectors)
            assert result == ["button.login", "button[type='submit']", "button"]

        def test_appends_tag_from_xpath(self, strategy):
            """Test that tag is extracted from XPath and appended."""
            selectors = ["//div[@class='container']"]
            result = strategy._ensure_generic_tag_suffix(selectors)
            assert result == ["//div[@class='container']", "div"]

        def test_non_extractable_selector_returns_unchanged(self, strategy):
            """Test that non-extractable selector list is returned with warning."""
            selectors = [".some-class", "#some-id"]
            result = strategy._ensure_generic_tag_suffix(selectors)
            assert result == selectors


class TestEnumCoercion:
    """Test that empty/blank enum values are coerced to sensible defaults."""

    def test_empty_strictness_defaults_to_relaxed(self):
        intent = ProgressiveSelectorStrategyIntent(
            element_count="multiple", relationship="siblings", strictness=""
        )
        assert intent.strictness == Strictness.RELAXED

    def test_empty_relationship_defaults_to_none(self):
        intent = ProgressiveSelectorStrategyIntent(
            element_count="single", relationship="", strictness="strict"
        )
        assert intent.relationship == Relationship.NONE

    def test_empty_element_count_defaults_to_single(self):
        intent = ProgressiveSelectorStrategyIntent(
            element_count="", relationship="grouped", strictness="relaxed"
        )
        assert intent.element_count == ElementCount.SINGLE

    def test_whitespace_only_treated_as_empty(self):
        intent = ProgressiveSelectorStrategyIntent(
            element_count="  ", relationship="  ", strictness="  "
        )
        assert intent.element_count == ElementCount.SINGLE
        assert intent.relationship == Relationship.NONE
        assert intent.strictness == Strictness.RELAXED

    def test_valid_values_still_work(self):
        intent = ProgressiveSelectorStrategyIntent(
            element_count="multiple", relationship="grouped", strictness="strict"
        )
        assert intent.element_count == ElementCount.MULTIPLE
        assert intent.relationship == Relationship.GROUPED
        assert intent.strictness == Strictness.STRICT

