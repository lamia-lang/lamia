"""Comprehensive tests for Web Selector Resolution: progressive and semantic strategies."""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
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
from lamia.engine.managers.web.selector_resolution.semantic.semantic_analyzer import (
    SemanticAnalyzer,
    SemanticIntent,
    SemanticSelectorGenerator
)
from lamia.engine.managers.web.selector_resolution.semantic.semantic_strategy_resolver import SemanticSelectorResolver
from lamia.validation.base import ValidationResult


# ============================================================================
# TEST FIXTURES
# ============================================================================

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


class TestProgressiveSelectorStrategyInitialization:
    """Test ProgressiveSelectorStrategy initialization."""

    def test_init(self, mock_llm_executor):
        """Test basic initialization."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        assert strategy.llm_manager == mock_llm_executor
        assert strategy.progressive_selector_json_validator is not None


class TestProgressiveSelectorStrategyEnums:
    """Test enum types for progressive selector strategy."""

    def test_element_count_enum_values(self):
        """Test ElementCount enum has correct values."""
        assert ElementCount.SINGLE.value == "single"
        assert ElementCount.MULTIPLE.value == "multiple"

    def test_relationship_enum_values(self):
        """Test Relationship enum has correct values."""
        assert Relationship.NONE.value == "none"
        assert Relationship.GROUPED.value == "grouped"
        assert Relationship.SIBLINGS.value == "siblings"

    def test_strictness_enum_values(self):
        """Test Strictness enum has correct values."""
        assert Strictness.STRICT.value == "strict"
        assert Strictness.RELAXED.value == "relaxed"


class TestProgressiveSelectorStrategyModel:
    """Test the Pydantic models for progressive selector strategy."""

    def test_intent_model_creation(self):
        """Test creating an intent model with enums."""
        intent = ProgressiveSelectorStrategyIntent(
            element_count=ElementCount.SINGLE,
            relationship=Relationship.NONE,
            strictness=Strictness.STRICT
        )
        assert intent.element_count == ElementCount.SINGLE
        assert intent.relationship == Relationship.NONE
        assert intent.strictness == Strictness.STRICT

    def test_intent_model_from_string_values(self):
        """Test creating an intent model from string values (Pydantic coercion)."""
        intent = ProgressiveSelectorStrategyIntent(
            element_count="single",
            relationship="grouped",
            strictness="relaxed"
        )
        assert intent.element_count == ElementCount.SINGLE
        assert intent.relationship == Relationship.GROUPED
        assert intent.strictness == Strictness.RELAXED

    def test_full_model_creation(self):
        """Test creating the full strategy model."""
        intent = ProgressiveSelectorStrategyIntent(
            element_count=ElementCount.MULTIPLE,
            relationship=Relationship.SIBLINGS,
            strictness=Strictness.RELAXED
        )
        model = ProgressiveSelectorStrategyModel(
            intent=intent,
            selectors=["button.login", "#login-btn", "button[type='submit']"]
        )
        assert model.intent.element_count == ElementCount.MULTIPLE
        assert len(model.selectors) == 3


class TestProgressiveSelectorStrategyGeneration:
    """Test generate_strategies method."""

    @pytest.mark.asyncio
    async def test_generate_strategies_returns_tuple(self, mock_llm_executor):
        """Test that generate_strategies returns a tuple of (intent, selectors)."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        intent, selectors = await strategy.generate_strategies("login button")

        assert isinstance(intent, ProgressiveSelectorStrategyIntent)
        assert isinstance(selectors, list)
        assert intent.element_count == ElementCount.SINGLE
        assert intent.relationship == Relationship.NONE
        assert intent.strictness == Strictness.STRICT
        assert "button.login" in selectors

    @pytest.mark.asyncio
    async def test_generate_strategies_with_failed_selectors(self, mock_llm_executor):
        """Test generating strategies with previously failed selectors."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        failed_selectors = ["button.old", "#old-btn"]
        intent, selectors = await strategy.generate_strategies("login button", failed_selectors)

        assert isinstance(intent, ProgressiveSelectorStrategyIntent)
        assert isinstance(selectors, list)

    @pytest.mark.asyncio
    async def test_generate_strategies_raises_on_invalid_response(self, mock_llm_executor):
        """Test that generate_strategies raises ValueError on invalid LLM response."""
        mock_llm_executor.execute = AsyncMock(return_value=ValidationResult(
            is_valid=False,
            error_message="Invalid JSON"
        ))

        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        with pytest.raises(ValueError, match="Failed to generate progressive strategies"):
            await strategy.generate_strategies("login button")


class TestProgressiveSelectorStrategyPrompt:
    """Test prompt creation method."""

    def test_create_strategy_prompt_basic(self, mock_llm_executor):
        """Test basic prompt creation without failed selectors."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        prompt = strategy._create_strategy_prompt("the login button")

        assert "login button" in prompt
        assert "element_count" in prompt
        assert "relationship" in prompt
        assert "strictness" in prompt
        assert "FAILED" not in prompt

    def test_create_strategy_prompt_with_failed_selectors(self, mock_llm_executor):
        """Test prompt creation with failed selectors."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        failed_selectors = ["button.old", "#old-btn"]
        prompt = strategy._create_strategy_prompt("the login button", failed_selectors)

        assert "login button" in prompt
        assert "FAILED" in prompt
        assert "button.old" in prompt or "#old-btn" in prompt


# ============================================================================
# RELATIONSHIP VALIDATOR TESTS
# ============================================================================

class TestRelationshipValidatorInitialization:
    """Test ElementRelationshipValidator initialization."""

    def test_init(self, mock_browser_adapter):
        """Test basic initialization."""
        validator = ElementRelationshipValidator(mock_browser_adapter)

        assert validator.browser == mock_browser_adapter


class TestRelationshipValidatorCountValidation:
    """Test count validation."""

    def test_validate_count_exactly(self, mock_browser_adapter):
        """Test exact count validation."""
        validator = ElementRelationshipValidator(mock_browser_adapter)

        elements = [Mock(), Mock()]  # 2 elements

        # Should pass for exactly_2
        is_valid, reason = validator._validate_count(elements, "exactly_2")
        assert is_valid is True

        # Should fail for exactly_1
        is_valid, reason = validator._validate_count(elements, "exactly_1")
        assert is_valid is False
        assert reason is not None
        assert "expected exactly 1" in reason.lower()

    def test_validate_count_at_least(self, mock_browser_adapter):
        """Test at_least count validation."""
        validator = ElementRelationshipValidator(mock_browser_adapter)

        elements = [Mock(), Mock(), Mock()]  # 3 elements

        # Should pass for at_least_2
        is_valid, reason = validator._validate_count(elements, "at_least_2")
        assert is_valid is True

        # Should fail for at_least_5
        is_valid, reason = validator._validate_count(elements, "at_least_5")
        assert is_valid is False

    def test_validate_count_at_most(self, mock_browser_adapter):
        """Test at_most count validation."""
        validator = ElementRelationshipValidator(mock_browser_adapter)

        elements = [Mock(), Mock()]  # 2 elements

        # Should pass for at_most_3
        is_valid, reason = validator._validate_count(elements, "at_most_3")
        assert is_valid is True

        # Should fail for at_most_1
        is_valid, reason = validator._validate_count(elements, "at_most_1")
        assert is_valid is False

    def test_validate_count_any(self, mock_browser_adapter):
        """Test 'any' count validation."""
        validator = ElementRelationshipValidator(mock_browser_adapter)

        # Should pass for any count
        is_valid, _ = validator._validate_count([], "any")
        assert is_valid is True

        is_valid, _ = validator._validate_count([Mock()] * 10, "any")
        assert is_valid is True


@pytest.mark.asyncio
class TestRelationshipValidatorRelationships:
    """Test relationship validation."""

    async def test_are_siblings_true(self, mock_browser_adapter):
        """Test sibling validation when elements are siblings."""
        mock_browser_adapter.execute_script.return_value = True

        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]

        result = await validator._are_siblings(elements)

        assert result is True

    async def test_are_siblings_false(self, mock_browser_adapter):
        """Test sibling validation when elements are not siblings."""
        mock_browser_adapter.execute_script.return_value = False

        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]

        result = await validator._are_siblings(elements)

        assert result is False

    async def test_find_common_ancestor_found(self, mock_browser_adapter):
        """Test finding common ancestor."""
        mock_ancestor = Mock()
        mock_browser_adapter.execute_script.return_value = mock_ancestor

        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]

        ancestor = await validator._find_common_ancestor(elements, max_levels=5)

        assert ancestor == mock_ancestor

    async def test_find_common_ancestor_not_found(self, mock_browser_adapter):
        """Test when no common ancestor found."""
        mock_browser_adapter.execute_script.return_value = None

        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]

        ancestor = await validator._find_common_ancestor(elements, max_levels=5)

        assert ancestor is None

    async def test_validate_strategy_match_siblings(self, mock_browser_adapter):
        """Test validating sibling relationship."""
        mock_browser_adapter.execute_script.return_value = True

        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        strategy = {
            "validation": {
                "count": "exactly_2",
                "relationship": "siblings"
            }
        }

        is_valid, reason = await validator.validate_strategy_match(elements, strategy)

        assert is_valid is True


# ============================================================================
# AMBIGUITY RESOLVER TESTS
# ============================================================================

class TestAmbiguityResolverInitialization:
    """Test AmbiguityResolver initialization."""

    def test_init(self, mock_browser_adapter, mock_cache):
        """Test basic initialization."""
        resolver = AmbiguityResolver(mock_browser_adapter, mock_cache)

        assert resolver.browser == mock_browser_adapter
        assert resolver.cache == mock_cache


@pytest.mark.asyncio
class TestAmbiguityResolverElementInfo:
    """Test element information extraction."""

    async def test_get_outer_html(self, mock_browser_adapter, mock_cache):
        """Test getting element outer HTML."""
        mock_browser_adapter.execute_script.return_value = "<button>Click me</button>"

        resolver = AmbiguityResolver(mock_browser_adapter, mock_cache)
        element = Mock()

        html = await resolver._get_outer_html(element)

        assert html == "<button>Click me</button>"

    async def test_get_xpath(self, mock_browser_adapter, mock_cache):
        """Test generating XPath for element."""
        mock_browser_adapter.execute_script.return_value = "//div[@id='content']/button[1]"

        resolver = AmbiguityResolver(mock_browser_adapter, mock_cache)
        element = Mock()

        xpath = await resolver._get_xpath(element)

        assert xpath.startswith("//")

    async def test_get_visual_location(self, mock_browser_adapter, mock_cache):
        """Test getting visual location of element."""
        mock_browser_adapter.execute_script.return_value = "top left"

        resolver = AmbiguityResolver(mock_browser_adapter, mock_cache)
        element = Mock()

        location = await resolver._get_visual_location(element)

        assert location in ["top left", "top center", "top right",
                           "middle left", "middle center", "middle right",
                           "bottom left", "bottom center", "bottom right"]

    def test_truncate_html(self, mock_browser_adapter, mock_cache):
        """Test HTML truncation."""
        resolver = AmbiguityResolver(mock_browser_adapter, mock_cache)

        long_html = "a" * 200
        truncated = resolver._truncate_html(long_html, max_length=50)

        assert len(truncated) <= 53  # 50 + "..."
        assert truncated.endswith("...")


# ============================================================================
# SEMANTIC ANALYZER TESTS
# ============================================================================

class TestSemanticIntentDataclass:
    """Test SemanticIntent dataclass."""

    def test_create_semantic_intent(self):
        """Test creating SemanticIntent."""
        intent = SemanticIntent(
            element_types=["button"],
            element_purpose="navigation",
            relationship="independent",
            count_intent="single",
            interaction_type="trigger",
            semantic_roles=["submit"],
            keywords=["login", "button"]
        )

        assert intent.element_types == ["button"]
        assert intent.count_intent == "single"
        assert "login" in intent.keywords


class TestSemanticAnalyzerInitialization:
    """Test SemanticAnalyzer initialization."""

    def test_init(self, mock_llm_executor):
        """Test basic initialization."""
        analyzer = SemanticAnalyzer(mock_llm_executor)

        assert analyzer.llm_executor == mock_llm_executor


@pytest.mark.asyncio
class TestSemanticAnalyzerIntentParsing:
    """Test semantic intent analysis."""

    async def test_parse_understanding_button(self, mock_llm_executor):
        """Test parsing understanding for button."""
        analyzer = SemanticAnalyzer(mock_llm_executor)

        understanding = "A clickable button element for form submission"
        intent = analyzer._parse_understanding(understanding, "submit button")

        assert "button" in intent.element_types
        assert intent.interaction_type == "trigger"

    async def test_parse_understanding_input(self, mock_llm_executor):
        """Test parsing understanding for input field."""
        analyzer = SemanticAnalyzer(mock_llm_executor)

        understanding = "An editable text input field for entering email address"
        intent = analyzer._parse_understanding(understanding, "email input")

        assert "input" in intent.element_types
        assert intent.interaction_type == "input"
        assert intent.element_purpose == "form_field"

    async def test_parse_understanding_grouped(self, mock_llm_executor):
        """Test parsing understanding for grouped elements."""
        analyzer = SemanticAnalyzer(mock_llm_executor)

        understanding = "Multiple related form fields grouped together in a container"
        intent = analyzer._parse_understanding(understanding, "grouped fields")

        assert intent.relationship == "grouped"
        assert intent.count_intent == "multiple"

    async def test_parse_understanding_question_answer(self, mock_llm_executor):
        """Test parsing question/answer semantic roles."""
        analyzer = SemanticAnalyzer(mock_llm_executor)

        understanding = "A label asking for user information paired with an input field"
        intent = analyzer._parse_understanding(understanding, "question and answer fields")

        assert "question" in intent.semantic_roles or "answer" in intent.semantic_roles


class TestSemanticSelectorGeneratorInitialization:
    """Test SemanticSelectorGenerator initialization."""

    def test_init(self, mock_llm_executor):
        """Test basic initialization."""
        generator = SemanticSelectorGenerator(mock_llm_executor)

        assert generator.llm_executor == mock_llm_executor


@pytest.mark.asyncio
class TestSemanticSelectorGeneratorGeneration:
    """Test semantic selector generation."""

    async def test_generate_selectors(self, mock_llm_executor):
        """Test generating selectors from semantic intent."""
        mock_llm_executor.execute.return_value = Mock(
            result_type="1. button[type='submit']\n2. input[type='submit']\n3. button.submit"
        )

        generator = SemanticSelectorGenerator(mock_llm_executor)
        intent = SemanticIntent(
            element_types=["button"],
            element_purpose="form_field",
            relationship="independent",
            count_intent="single",
            interaction_type="trigger",
            semantic_roles=["submit"],
            keywords=["submit"]
        )

        selectors = await generator.generate_selectors(intent)

        assert len(selectors) > 0
        assert any("button" in sel for sel in selectors)

    async def test_parse_selector_list(self, mock_llm_executor):
        """Test parsing numbered selector list."""
        generator = SemanticSelectorGenerator(mock_llm_executor)

        response = """
        1. button.submit
        2. input[type='submit']
        3. [role='button']
        """

        selectors = generator._parse_selector_list(response)

        assert len(selectors) == 3
        assert "button.submit" in selectors

    async def test_generate_fallback_selectors(self, mock_llm_executor):
        """Test generating fallback selectors."""
        generator = SemanticSelectorGenerator(mock_llm_executor)

        intent = SemanticIntent(
            element_types=["input"],
            element_purpose="form_field",
            relationship="independent",
            count_intent="single",
            interaction_type="input",
            semantic_roles=[],
            keywords=[]
        )

        fallbacks = generator._generate_fallback_selectors(intent)

        assert len(fallbacks) > 0
        assert any("input" in fb for fb in fallbacks)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

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
        intent, selectors = await strategy_gen.generate_strategies("login button")

        assert intent.element_count == ElementCount.SINGLE
        assert len(selectors) > 0

    async def test_semantic_resolution_flow(self, mock_llm_executor, mock_browser_adapter):
        """Test full semantic resolution flow."""
        # Setup mock LLM responses
        mock_llm_executor.execute.side_effect = [
            Mock(result_type="A clickable button for authentication"),
            Mock(result_type="1. button.login\n2. button[type='submit']")
        ]

        # Setup mock browser
        mock_elements = [Mock()]
        mock_browser_adapter.get_elements.return_value = mock_elements

        analyzer = SemanticAnalyzer(mock_llm_executor)
        generator = SemanticSelectorGenerator(mock_llm_executor)

        # Analyze intent
        intent = await analyzer.analyze_description("login button")

        assert intent is not None
        assert len(intent.element_types) > 0

        # Generate selectors
        selectors = await generator.generate_selectors(intent)

        assert len(selectors) > 0
