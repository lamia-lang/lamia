"""Tests for AIResolvedSelectorValidator."""

import pytest
from unittest.mock import AsyncMock, Mock

from lamia.engine.managers.web.selector_resolution.validators.ai_resolved_selector_validator import (
    AIResolvedSelectorValidator
)
from lamia.validation.base import ValidationResult
from lamia.internal_types import BrowserActionParams


@pytest.fixture
def mock_browser_adapter():
    """Create a mock browser adapter."""
    adapter = Mock()
    adapter.is_visible = AsyncMock()
    return adapter


class TestAIResolvedSelectorValidator:
    """Tests for AIResolvedSelectorValidator."""

    def test_name_property(self, mock_browser_adapter):
        """Test that name property returns correct value."""
        validator = AIResolvedSelectorValidator(mock_browser_adapter)
        assert validator.name == "ai_resolved_selector"

    def test_initial_hint_property(self, mock_browser_adapter):
        """Test that initial_hint property returns correct value."""
        validator = AIResolvedSelectorValidator(mock_browser_adapter)
        assert validator.initial_hint == "Return only a valid CSS selector that matches existing elements on the page."

    @pytest.mark.asyncio
    async def test_validate_empty_selector(self, mock_browser_adapter):
        """Test validate_strict with empty selector returns invalid."""
        validator = AIResolvedSelectorValidator(mock_browser_adapter)
        
        result = await validator.validate("")
        
        assert result.is_valid is False
        assert "Empty AI-resolved selector" in result.error_message
        assert result.validated_text is None
        mock_browser_adapter.is_visible.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_blank_selector(self, mock_browser_adapter):
        """Test validate_strict with blank selector returns invalid."""
        validator = AIResolvedSelectorValidator(mock_browser_adapter)
        
        result = await validator.validate("   ")
        
        assert result.is_valid is False
        assert "Empty AI-resolved selector" in result.error_message
        assert result.validated_text is None
        mock_browser_adapter.is_visible.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_valid_selector_found(self, mock_browser_adapter):
        """Test validate_strict with valid selector that finds element."""
        validator = AIResolvedSelectorValidator(mock_browser_adapter)
        selector = "#my-button"
        mock_browser_adapter.is_visible = AsyncMock(return_value=True)
        
        result = await validator.validate(selector)
        
        assert result.is_valid is True
        assert result.validated_text == selector
        assert result.error_message is None
        mock_browser_adapter.is_visible.assert_called_once()
        call_args = mock_browser_adapter.is_visible.call_args[0][0]
        assert isinstance(call_args, BrowserActionParams)
        assert call_args.selector == selector
        assert call_args.timeout == 2.0

    @pytest.mark.asyncio
    async def test_validate_permissive_valid_selector_found(self, mock_browser_adapter):
        """Test validate_permissive with valid selector that finds element."""
        validator = AIResolvedSelectorValidator(mock_browser_adapter)
        selector = ".my-class"
        mock_browser_adapter.is_visible = AsyncMock(return_value=True)
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is True
        assert result.validated_text == selector
        assert result.error_message is None
        mock_browser_adapter.is_visible.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_strict_selector_not_found(self, mock_browser_adapter):
        """Test validate_strict with selector that doesn't find element."""
        validator = AIResolvedSelectorValidator(mock_browser_adapter)
        selector = "#nonexistent"
        mock_browser_adapter.is_visible = AsyncMock(return_value=False)
        
        result = await validator.validate_strict(selector)
        
        assert result.is_valid is False
        assert "found no elements" in result.error_message
        assert selector in result.error_message
        assert result.validated_text is None
        assert result.hint is not None

    @pytest.mark.asyncio
    async def test_validate_permissive_selector_not_found(self, mock_browser_adapter):
        """Test validate_permissive with selector that doesn't find element."""
        validator = AIResolvedSelectorValidator(mock_browser_adapter)
        selector = ".missing"
        mock_browser_adapter.is_visible = AsyncMock(return_value=False)
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is False
        assert "found no elements" in result.error_message
        assert selector in result.error_message
        assert result.validated_text is None

    @pytest.mark.asyncio
    async def test_validate_strict_browser_adapter_exception(self, mock_browser_adapter):
        """Test validate_strict when browser adapter throws exception."""
        validator = AIResolvedSelectorValidator(mock_browser_adapter)
        selector = "#test"
        mock_browser_adapter.is_visible = AsyncMock(side_effect=Exception("Browser error"))
        
        result = await validator.validate_strict(selector)
        
        assert result.is_valid is False
        assert "validation failed" in result.error_message.lower()
        assert result.validated_text is None
        assert result.hint is not None

    @pytest.mark.asyncio
    async def test_validate_permissive_browser_adapter_exception(self, mock_browser_adapter):
        """Test validate_permissive when browser adapter throws exception."""
        validator = AIResolvedSelectorValidator(mock_browser_adapter)
        selector = "div > p"
        mock_browser_adapter.is_visible = AsyncMock(side_effect=ValueError("Invalid selector"))
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is False
        assert "validation failed" in result.error_message.lower()
        assert result.validated_text is None

    @pytest.mark.asyncio
    async def test_validate_strict_selector_with_whitespace(self, mock_browser_adapter):
        """Test validate_strict trims whitespace from selector."""
        validator = AIResolvedSelectorValidator(mock_browser_adapter)
        selector = "  #trimmed  "
        mock_browser_adapter.is_visible = AsyncMock(return_value=True)
        
        result = await validator.validate_strict(selector)
        
        assert result.is_valid is True
        assert result.validated_text == "#trimmed"
        call_args = mock_browser_adapter.is_visible.call_args[0][0]
        assert call_args.selector == "#trimmed"

    @pytest.mark.asyncio
    async def test_validate_permissive_selector_with_whitespace(self, mock_browser_adapter):
        """Test validate_permissive trims whitespace from selector."""
        validator = AIResolvedSelectorValidator(mock_browser_adapter)
        selector = "\t\n.whitespace\n\t"
        mock_browser_adapter.is_visible = AsyncMock(return_value=True)
        
        result = await validator.validate_permissive(selector)
        
        assert result.is_valid is True
        assert result.validated_text == ".whitespace"
        call_args = mock_browser_adapter.is_visible.call_args[0][0]
        assert call_args.selector == ".whitespace"
