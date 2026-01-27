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