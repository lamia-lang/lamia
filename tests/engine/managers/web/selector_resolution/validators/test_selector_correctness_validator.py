"""Tests for SelectorCorrectnessValidator."""

import pytest

from lamia.engine.managers.web.selector_resolution.validators.selector_correctness_validator import (
    SelectorCorrectnessValidator
)
from lamia.engine.managers.web.selector_resolution.selector_parser import SelectorType
from lamia.validation.base import ValidationResult


class TestSelectorCorrectnessValidator:
    """Tests for SelectorCorrectnessValidator."""

    def test_name_property(self):
        """Test that name property returns correct value."""
        validator = SelectorCorrectnessValidator()
        assert validator.name == "selector_correctness"

    def test_initial_hint_property(self):
        """Test that initial_hint property returns correct value."""
        validator = SelectorCorrectnessValidator()
        assert validator.initial_hint == "Return only a valid CSS selector or XPath expression, no extra text"

    def test_parser_initialized(self):
        """Test that parser is initialized."""
        validator = SelectorCorrectnessValidator()
        assert validator.parser is not None

    @pytest.mark.asyncio
    async def test_validate_strict_delegates_to_permissive(self):
        """Test that validate_strict delegates to validate_permissive."""
        validator = SelectorCorrectnessValidator()
        selector = "#test-id"
        
        strict_result = await validator.validate_strict(selector)
        permissive_result = await validator.validate_permissive(selector)
        
        assert strict_result.is_valid == permissive_result.is_valid
        assert strict_result.error_message == permissive_result.error_message
        assert strict_result.typed_result == permissive_result.typed_result

    @pytest.mark.asyncio
    async def test_validate_permissive_empty_selector(self):
        """Test validate_permissive with empty selector returns invalid."""
        validator = SelectorCorrectnessValidator()
        
        result = await validator.validate_permissive("")
        
        assert result.is_valid is False
        assert "Empty selector response" in result.error_message
        assert result.typed_result is None

    @pytest.mark.asyncio
    async def test_validate_permissive_blank_selector(self):
        """Test validate_permissive with blank selector returns invalid."""
        validator = SelectorCorrectnessValidator()
        
        result = await validator.validate_permissive("   ")
        
        assert result.is_valid is False
        assert "Empty selector response" in result.error_message
        assert result.typed_result is None

    @pytest.mark.asyncio
    async def test_validate_permissive_valid_css_id_selector(self):
        """Test validate_permissive with valid CSS ID selector."""
        validator = SelectorCorrectnessValidator()
        selector = "#my-id"
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is True
        assert result.typed_result == selector
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_validate_permissive_valid_css_class_selector(self):
        """Test validate_permissive with valid CSS class selector."""
        validator = SelectorCorrectnessValidator()
        selector = ".my-class"
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is True
        assert result.typed_result == selector
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_validate_permissive_valid_css_descendant_selector(self):
        """Test validate_permissive with valid CSS descendant selector."""
        validator = SelectorCorrectnessValidator()
        selector = "div > p"
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is True
        assert result.typed_result == selector
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_validate_permissive_valid_css_complex_selector(self):
        """Test validate_permissive with valid complex CSS selector."""
        validator = SelectorCorrectnessValidator()
        selector = "div.container > p.text:first-child"
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is True
        assert result.typed_result == selector
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_validate_permissive_valid_xpath_absolute(self):
        """Test validate_permissive with valid absolute XPath selector."""
        validator = SelectorCorrectnessValidator()
        selector = "//div"
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is True
        assert result.typed_result == selector
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_validate_permissive_valid_xpath_with_attribute(self):
        """Test validate_permissive with valid XPath selector with attribute."""
        validator = SelectorCorrectnessValidator()
        selector = "//a[@href]"
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is True
        assert result.typed_result == selector
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_validate_permissive_valid_xpath_complex(self):
        """Test validate_permissive with valid complex XPath selector."""
        validator = SelectorCorrectnessValidator()
        selector = "//div[@class='container']//p[contains(text(), 'test')]"
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is True
        assert result.typed_result == selector
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_validate_permissive_invalid_natural_language(self):
        """Test validate_permissive with natural language text returns invalid."""
        validator = SelectorCorrectnessValidator()
        selector = "click the button"
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is False
        assert "Invalid selector" in result.error_message
        assert SelectorType.NATURAL_LANGUAGE.value in result.error_message
        assert result.typed_result is None

    @pytest.mark.asyncio
    async def test_validate_permissive_invalid_css(self):
        """Test validate_permissive with invalid CSS selector returns invalid."""
        validator = SelectorCorrectnessValidator()
        selector = "div..invalid"
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is False
        assert "Invalid selector" in result.error_message
        assert result.typed_result is None

    @pytest.mark.asyncio
    async def test_validate_permissive_invalid_xpath(self):
        """Test validate_permissive with invalid XPath selector returns invalid."""
        validator = SelectorCorrectnessValidator()
        selector = "//div[invalid-syntax"
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is False
        assert "Invalid selector" in result.error_message
        assert result.typed_result is None

    @pytest.mark.asyncio
    async def test_validate_permissive_parser_value_error(self):
        """Test validate_permissive when parser raises ValueError."""
        validator = SelectorCorrectnessValidator()
        selector = ""
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is False
        assert result.error_message is not None
        assert result.typed_result is None

    @pytest.mark.asyncio
    async def test_validate_permissive_selector_with_whitespace(self):
        """Test validate_permissive trims whitespace from selector."""
        validator = SelectorCorrectnessValidator()
        selector = "  #trimmed  "
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is True
        assert result.typed_result == "#trimmed"

    @pytest.mark.asyncio
    async def test_validate_strict_valid_css(self):
        """Test validate_strict with valid CSS selector."""
        validator = SelectorCorrectnessValidator()
        selector = "button.submit"
        
        result = await validator.validate_strict(selector)
        
        assert result.is_valid is True
        assert result.typed_result == selector

    @pytest.mark.asyncio
    async def test_validate_strict_valid_xpath(self):
        """Test validate_strict with valid XPath selector."""
        validator = SelectorCorrectnessValidator()
        selector = "//button[@type='submit']"
        
        result = await validator.validate_strict(selector)
        
        assert result.is_valid is True
        assert result.typed_result == selector

    @pytest.mark.asyncio
    async def test_validate_strict_invalid_selector(self):
        """Test validate_strict with invalid selector."""
        validator = SelectorCorrectnessValidator()
        selector = "find the login button"
        
        result = await validator.validate_strict(selector)
        
        assert result.is_valid is False
        assert "Invalid selector" in result.error_message
