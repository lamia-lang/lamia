"""Comprehensive tests for Web Selector Resolution: progressive and semantic strategies."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from lamia.engine.managers.web.selector_resolution.progressive.progressive_selector_strategy import ProgressiveSelectorStrategy
from lamia.engine.managers.web.selector_resolution.progressive.relationship_validator import ElementRelationshipValidator
from lamia.engine.managers.web.selector_resolution.progressive.ambiguity_resolver import AmbiguityResolver
from lamia.engine.managers.web.selector_resolution.progressive.strategy_resolver import ProgressiveSelectorResolver
from lamia.engine.managers.web.selector_resolution.semantic.semantic_analyzer import (
    SemanticAnalyzer,
    SemanticIntent,
    SemanticSelectorGenerator
)
from lamia.engine.managers.web.selector_resolution.semantic.semantic_strategy_resolver import SemanticSelectorResolver


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def mock_llm_executor():
    """Create a mock LLM executor."""
    executor = Mock()
    executor.execute = AsyncMock(return_value=Mock(result_type="LLM response"))
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


@pytest.fixture
def sample_strategies():
    """Sample strategy list."""
    return [
        {
            "selectors": ["button.login", "#login-btn"],
            "strictness": "strict",
            "description": "Login button with exact class or ID",
            "validation": {"count": "exactly_1", "relationship": "none"}
        },
        {
            "selectors": ["button:contains('Login')", "input[type='submit']"],
            "strictness": "relaxed",
            "description": "Login button by text or submit button",
            "validation": {"count": "at_least_1", "relationship": "none"}
        }
    ]


# ============================================================================
# PROGRESSIVE SELECTOR STRATEGY TESTS
# ============================================================================

class TestProgressiveSelectorStrategyInitialization:
    """Test ProgressiveSelectorStrategy initialization."""

    def test_init(self, mock_llm_executor):
        """Test basic initialization."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        assert strategy.llm_executor == mock_llm_executor
        assert strategy.validator is not None


class TestProgressiveSelectorStrategyIntentParsing:
    """Test intent parsing from description."""

    def test_parse_intent_single_element(self, mock_llm_executor):
        """Test parsing intent for single element."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        intent = strategy._parse_web_command_intent("the login button")

        assert intent["element_count"] == "single"
        assert "button" in intent["element_types"]
        assert intent["relationship"] == "none"

    def test_parse_intent_multiple_elements(self, mock_llm_executor):
        """Test parsing intent for multiple elements."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        intent = strategy._parse_web_command_intent("all the product cards")

        assert intent["element_count"] == "multiple"
        assert intent["relationship"] == "none"

    def test_parse_intent_grouped_elements(self, mock_llm_executor):
        """Test parsing intent for grouped elements."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        intent = strategy._parse_web_command_intent("grouped form fields for address")

        assert intent["relationship"] == "grouped"
        assert intent["element_count"] == "multiple"

    def test_parse_intent_sibling_elements(self, mock_llm_executor):
        """Test parsing intent for sibling elements."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        intent = strategy._parse_web_command_intent("adjacent navigation links")

        assert intent["relationship"] in ["siblings", "grouped"]

    def test_parse_intent_element_types(self, mock_llm_executor):
        """Test parsing different element types."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        test_cases = [
            ("fill in the email input", ["input"]),
            ("click the submit button", ["button"]),
            ("find all the links", ["link"]),
            ("select an option from dropdown", ["select"]),
            ("check the checkbox", ["checkbox"])
        ]

        for description, expected_types in test_cases:
            intent = strategy._parse_web_command_intent(description)
            assert any(et in intent["element_types"] for et in expected_types), \
                f"Failed for: {description}"

    def test_parse_intent_keywords_extraction(self, mock_llm_executor):
        """Test keyword extraction from description."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        intent = strategy._parse_web_command_intent("the blue submit button with icon")

        assert "blue" in intent["keywords"]
        assert "submit" in intent["keywords"]
        assert "button" in intent["keywords"]
        # Stop words should be filtered
        assert "the" not in intent["keywords"]
        assert "with" not in intent["keywords"]


class TestProgressiveSelectorStrategyStrictness:
    """Test strictness detection."""

    def test_has_strict_keywords_detected(self, mock_llm_executor):
        """Test detection of strict keywords."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        strict_phrases = [
            "exactly the login button",
            "only the submit button",
            "precisely the form",
            "just the input field",
            "must be the checkbox"
        ]

        for phrase in strict_phrases:
            assert strategy._has_strict_keywords(phrase) is True, \
                f"Failed to detect strictness in: {phrase}"

    def test_has_strict_keywords_not_detected(self, mock_llm_executor):
        """Test non-strict descriptions."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        relaxed_phrases = [
            "the login button",
            "a submit button",
            "some input fields"
        ]

        for phrase in relaxed_phrases:
            assert strategy._has_strict_keywords(phrase) is False


class TestProgressiveSelectorStrategyEnhancement:
    """Test strategy enhancement with intent."""

    def test_enhance_strategies_single_element(self, mock_llm_executor, sample_strategies):
        """Test enhancing strategies for single element intent."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        intent = {"element_count": "single", "relationship": "none"}
        enhanced = strategy._enhance_strategies_with_intent(sample_strategies.copy(), intent)

        # Should set exactly_1 for single elements
        assert enhanced[0]["validation"]["count"] == "exactly_1"

    def test_enhance_strategies_multiple_elements(self, mock_llm_executor, sample_strategies):
        """Test enhancing strategies for multiple elements."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        intent = {"element_count": "multiple", "relationship": "none"}
        enhanced = strategy._enhance_strategies_with_intent(sample_strategies.copy(), intent)

        # Should allow multiple matches
        assert "at_least" in enhanced[0]["validation"]["count"]

    def test_enhance_strategies_grouped_relationship(self, mock_llm_executor, sample_strategies):
        """Test enhancing strategies with grouped relationship."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        intent = {"element_count": "multiple", "relationship": "grouped"}
        enhanced = strategy._enhance_strategies_with_intent(sample_strategies.copy(), intent)

        # Should set common_ancestor relationship
        assert enhanced[0]["validation"]["relationship"] == "common_ancestor"
        assert "max_ancestor_levels" in enhanced[0]["validation"]


class TestProgressiveSelectorStrategyParsing:
    """Test LLM response parsing."""

    def test_parse_valid_json_response(self, mock_llm_executor):
        """Test parsing valid JSON response."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        llm_response = '''
        [
            {
                "selectors": ["button.submit"],
                "strictness": "strict",
                "description": "Submit button"
            }
        ]
        '''

        strategies = strategy._parse_strategies(llm_response, "submit button")

        assert len(strategies) > 0
        assert "selectors" in strategies[0]

    def test_parse_json_with_markdown(self, mock_llm_executor):
        """Test parsing JSON wrapped in markdown code blocks."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        llm_response = '''
        ```json
        [
            {"selectors": ["button"], "strictness": "relaxed"}
        ]
        ```
        '''

        strategies = strategy._parse_strategies(llm_response, "button")

        assert len(strategies) > 0

    def test_parse_malformed_json_fallback(self, mock_llm_executor):
        """Test fallback when JSON is malformed."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        llm_response = "Not valid JSON at all"

        strategies = strategy._parse_strategies(llm_response, "button")

        # Should create fallback strategies
        assert len(strategies) > 0
        assert "selectors" in strategies[0]


class TestProgressiveSelectorStrategyFallbacks:
    """Test fallback strategy generation."""

    def test_create_fallback_strategies_button(self, mock_llm_executor):
        """Test fallback strategies for button."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        fallbacks = strategy._create_fallback_strategies("click the submit button")

        assert len(fallbacks) > 0
        # Should have button-specific selectors
        assert any("button" in str(fb["selectors"]) for fb in fallbacks)

    def test_create_fallback_strategies_grouped(self, mock_llm_executor):
        """Test fallback strategies for grouped elements."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        fallbacks = strategy._create_fallback_strategies("grouped form fields")

        assert len(fallbacks) > 0
        # Should have form-group patterns
        has_form_pattern = any(
            "form" in str(fb["selectors"]).lower() or "group" in str(fb["selectors"]).lower()
            for fb in fallbacks
        )
        assert has_form_pattern

    def test_create_fallback_strategies_input(self, mock_llm_executor):
        """Test fallback strategies for input fields."""
        strategy = ProgressiveSelectorStrategy(mock_llm_executor)

        fallbacks = strategy._create_fallback_strategies("the email input field")

        assert len(fallbacks) > 0
        # Should have input-specific selectors
        assert any("input" in str(fb["selectors"]) for fb in fallbacks)


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
        # Setup mock LLM response
        mock_llm_executor.execute.return_value = Mock(
            result_type='[{"selectors": ["button.login"], "strictness": "strict"}]'
        )

        # Setup mock browser to find elements
        mock_elements = [Mock()]
        mock_browser_adapter.get_elements.return_value = mock_elements
        mock_browser_adapter.execute_script.return_value = True

        strategy_gen = ProgressiveSelectorStrategy(mock_llm_executor)
        validator = ElementRelationshipValidator(mock_browser_adapter)
        resolver = AmbiguityResolver(mock_browser_adapter, mock_cache)

        # Generate strategies
        strategies = await strategy_gen.generate_strategies("login button")

        assert len(strategies) > 0

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
