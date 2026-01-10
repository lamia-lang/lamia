"""Tests for SelectorResolutionService with mocked AI calls."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from lamia.engine.managers.web.selector_resolution.selector_resolution_service import SelectorResolutionService
from lamia.engine.managers.web.selector_resolution.response_parser import AmbiguousFormatResponseParser
from lamia.engine.managers.web.selector_resolution.selector_parser import SelectorType


class MockLLMResult:
    """Mock LLM result."""
    def __init__(self, text: str):
        self.validated_text = text


@pytest.fixture
def mock_llm_manager():
    """Create a mock LLM manager."""
    manager = AsyncMock()
    return manager


@pytest.fixture
def mock_get_page_html():
    """Create a mock get_page_html function."""
    async def get_html():
        return """
        <html>
            <body>
                <button class="btn__primary--large">Sign in</button>
                <button class="google-signin">Sign in with Google</button>
                <button class="apple-signin">Sign in with Apple</button>
            </body>
        </html>
        """
    return get_html


@pytest.fixture
def mock_browser_adapter():
    """Create a mock browser adapter."""
    return AsyncMock()


@pytest.fixture
def mock_get_browser_adapter(mock_browser_adapter):
    """Create a mock get_browser_adapter function."""
    async def get_adapter():
        return mock_browser_adapter
    return get_adapter


@pytest.fixture
def service(mock_llm_manager, mock_get_page_html, mock_get_browser_adapter):
    """Create a SelectorResolutionService with mocked dependencies."""
    service = SelectorResolutionService(
        llm_manager=mock_llm_manager,
        get_page_html_func=mock_get_page_html,
        get_browser_adapter_func=mock_get_browser_adapter,
        cache_enabled=True
    )
    # Clear cache before each test to ensure isolation
    service.cache.clear()
    return service


@pytest.mark.asyncio
async def test_resolve_valid_css_selector_no_ai_call(service, mock_llm_manager):
    """Test that valid CSS selectors don't trigger AI calls."""
    # Valid CSS selector should return as-is without AI call
    result = await service.resolve_selector(
        selector="button.btn__primary",
        page_url="https://example.com"
    )
    
    assert result == "button.btn__primary"
    # Verify no AI calls were made
    mock_llm_manager.execute.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_natural_language_single_result(service, mock_llm_manager, mock_browser_adapter):
    """Test natural language selector with single AI result."""
    # Mock AI response for single match
    mock_llm_manager.execute.return_value = MockLLMResult("button.btn__primary--large")
    
    # Mock validation
    mock_validation_result = Mock()
    mock_validation_result.is_valid = True
    
    with patch('lamia.engine.managers.web.selector_resolution.validators.ai_resolved_selector_validator.AIResolvedSelectorValidator') as MockValidator:
        mock_validator = MockValidator.return_value
        mock_validator.validate_strict = AsyncMock(return_value=mock_validation_result)
        
        result = await service.resolve_selector(
            selector="sign in button",
            page_url="https://example.com",
            operation_type="click"
        )
    
    assert result == "button.btn__primary--large"
    # Verify AI was called once
    mock_llm_manager.execute.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_natural_language_ambiguous_result(service, mock_llm_manager):
    """Test natural language selector with ambiguous AI result."""
    # Mock AI response for ambiguous match
    ambiguous_response = """AMBIGUOUS
OPTION1: "Sign in main" -> button.btn__primary--large
OPTION2: "Sign in with Google" -> button.google-signin
OPTION3: "Sign in with Apple" -> button.apple-signin"""
    
    # Mock the validation responses to be unique (not ambiguous)
    mock_llm_manager.execute.side_effect = [
        MockLLMResult(ambiguous_response),  # Initial ambiguous response
        MockLLMResult("button.btn__primary--large"),  # Validation for "Sign in main" - unique
        MockLLMResult("button.google-signin"),  # Validation for "Sign in with Google" - unique
        MockLLMResult("button.apple-signin"),  # Validation for "Sign in with Apple" - unique
    ]
    
    # Should raise ValueError with ambiguity message
    with pytest.raises(ValueError) as excinfo:
        await service.resolve_selector(
            selector="sign in different",  # Different from options to avoid filtering
            page_url="https://example.com",
            operation_type="click"
        )
    
    assert "🚨 AMBIGUOUS SELECTOR:" in str(excinfo.value)
    assert "Sign in main" in str(excinfo.value)
    assert "Sign in with Google" in str(excinfo.value)
    assert "Sign in with Apple" in str(excinfo.value)


@pytest.mark.asyncio
async def test_cache_hit_no_ai_call(service, mock_llm_manager):
    """Test that cache hits don't trigger AI calls."""
    # First, populate cache by mocking a successful resolution
    mock_llm_manager.execute.return_value = MockLLMResult("button.btn__primary--large")
    
    with patch('lamia.engine.managers.web.selector_resolution.validators.ai_resolved_selector_validator.AIResolvedSelectorValidator') as MockValidator:
        mock_validation_result = Mock()
        mock_validation_result.is_valid = True
        mock_validator = MockValidator.return_value
        mock_validator.validate_strict = AsyncMock(return_value=mock_validation_result)
        
        # First call - should hit AI and cache result
        result1 = await service.resolve_selector(
            selector="sign in button",
            page_url="https://example.com",
            operation_type="click"
        )
        
        # Reset mock to verify second call doesn't hit AI
        mock_llm_manager.reset_mock()
        
        # Second call - should hit cache, no AI call
        result2 = await service.resolve_selector(
            selector="sign in button",
            page_url="https://example.com",
            operation_type="click"
        )
    
    assert result1 == result2 == "button.btn__primary--large"
    # Verify second call didn't trigger AI
    mock_llm_manager.execute.assert_not_called()


@pytest.mark.asyncio
async def test_exclusionary_description_bypass_validation(service, mock_llm_manager):
    """Test that exclusionary descriptions bypass validation and return main element."""
    # Mock AI response for exclusionary description
    ambiguous_response = """AMBIGUOUS
OPTION1: "Sign in" -> button.btn__primary--large
OPTION2: "Sign in with Google" -> button.google-signin"""
    
    mock_llm_manager.execute.return_value = MockLLMResult(ambiguous_response)
    
    # Test exclusionary description
    result = await service.resolve_selector(
        selector="Sign in but not the with Google options",
        page_url="https://example.com",
        operation_type="click"
    )
    
    # Should return the main element (shortest option)
    assert result == "button.btn__primary--large"
    # Should only call AI once (no validation calls)
    assert mock_llm_manager.execute.call_count == 1


@pytest.mark.asyncio
async def test_deduction_logic_creates_exclusionary_description(service):
    """Test that deduction logic creates proper exclusionary descriptions."""
    options = [
        ("Sign in", "button.btn__primary--large"),
        ("Sign in with Google", "button.google-signin"),
        ("Sign in with Apple", "button.apple-signin")
    ]
    
    result = service._deduce_main_element(options, "sign in")
    
    assert result is not None
    exclusionary_text, css_selector = result
    
    # Should create exclusionary description
    assert "but not the" in exclusionary_text
    assert "Google" in exclusionary_text
    assert "Apple" in exclusionary_text
    assert css_selector == "button.btn__primary--large"  # Shortest option


@pytest.mark.asyncio
async def test_filter_duplicate_suggestions(service, mock_llm_manager):
    """Test that AI suggestions identical to original selector are filtered out."""
    # Mock AI response that includes the original failing selector
    ambiguous_response = """AMBIGUOUS
OPTION1: "sign in" -> button.btn__primary--large
OPTION2: "Sign in with Google" -> button.google-signin"""
    
    # Mock validation responses - Google option is unique
    mock_llm_manager.execute.side_effect = [
        MockLLMResult(ambiguous_response),  # Initial ambiguous response
        MockLLMResult("button.google-signin"),  # Validation for Google - unique
    ]
    
    with pytest.raises(ValueError) as excinfo:
        await service.resolve_selector(
            selector="sign in",  # Same as OPTION1
            page_url="https://example.com",
            operation_type="click"
        )
    
    error_message = str(excinfo.value)
    # Should show Google option since duplicate "sign in" is filtered out
    # but only one option remains, so should get "not enough alternatives" error
    assert "Could not find unique alternatives" in error_message or "🚨 AMBIGUOUS SELECTOR:" in error_message


@pytest.mark.asyncio
async def test_operation_specific_instructions(service):
    """Test that different operation types get appropriate instructions."""
    # Test click operation
    click_instructions = service._get_operation_instructions("click")
    assert "CLICKABLE element" in click_instructions
    assert "button" in click_instructions.lower()
    
    # Test type operation
    type_instructions = service._get_operation_instructions("type_text")
    assert "INPUT element" in type_instructions
    assert "input" in type_instructions.lower()
    
    # Test validation flag
    click_validation = service._get_operation_instructions("click", for_validation=True)
    assert "VALIDATION:" in click_validation
    assert "MULTIPLE clickable elements" in click_validation


@pytest.mark.asyncio
async def test_response_parser_interface(service):
    """Test that service uses response parser interface correctly."""
    parser = service.response_parser
    assert isinstance(parser, AmbiguousFormatResponseParser)
    
    # Test parser methods
    html = "<button>Test</button>"
    operation_instructions = "OPERATION: Find button"
    
    full_prompt = parser.get_full_prompt_template(operation_instructions, html, "test")
    validation_prompt = parser.get_validation_prompt_template(operation_instructions, html, "test")
    
    assert "AMBIGUOUS" in full_prompt
    assert "FORMAT 1" in full_prompt
    assert "FORMAT 2" in full_prompt
    assert full_prompt == validation_prompt  # Should be identical for this parser


@pytest.mark.asyncio
async def test_empty_selector_error(service):
    """Test that empty selectors raise appropriate error."""
    with pytest.raises(ValueError, match="Selector cannot be empty"):
        await service.resolve_selector("", "https://example.com")
    
    with pytest.raises(ValueError, match="Selector cannot be empty"):
        await service.resolve_selector("   ", "https://example.com")


@pytest.mark.asyncio
async def test_llm_empty_response_error(service, mock_llm_manager):
    """Test that empty LLM responses raise appropriate error."""
    mock_llm_manager.execute.return_value = MockLLMResult("")
    
    with pytest.raises(ValueError, match="LLM returned empty response"):
        await service.resolve_selector(
            selector="sign in",
            page_url="https://example.com",
            operation_type="click"
        )


@pytest.mark.asyncio
async def test_cache_operations(service):
    """Test cache size and clear operations."""
    # Initially empty
    assert service.get_cache_size() == 0
    
    # Mock a resolution to populate cache
    await service.cache.set("test selector", "https://example.com", "button.test")
    assert service.get_cache_size() == 1
    
    # Clear cache
    await service.clear_cache()
    assert service.get_cache_size() == 0


@pytest.mark.asyncio 
async def test_custom_response_parser_injection():
    """Test that custom response parsers can be injected."""
    mock_parser = Mock()
    mock_llm_manager = AsyncMock()
    
    service = SelectorResolutionService(
        llm_manager=mock_llm_manager,
        response_parser=mock_parser
    )
    
    assert service.response_parser is mock_parser


# Integration test to ensure no real AI calls
@pytest.mark.asyncio
async def test_no_real_ai_calls_in_test_suite(service, mock_llm_manager):
    """Integration test to ensure all AI calls are properly mocked."""
    # Run through multiple scenarios
    test_cases = [
        # Valid CSS - no AI call
        ("button.test", False),
        # Natural language - mocked AI call  
        ("sign in button", True),
    ]
    
    for selector, should_call_ai in test_cases:
        mock_llm_manager.reset_mock()
        
        if should_call_ai:
            mock_llm_manager.execute.return_value = MockLLMResult("button.resolved")
            
            with patch('lamia.engine.managers.web.selector_resolution.validators.ai_resolved_selector_validator.AIResolvedSelectorValidator') as MockValidator:
                mock_validation_result = Mock()
                mock_validation_result.is_valid = True
                mock_validator = MockValidator.return_value
                mock_validator.validate_strict = AsyncMock(return_value=mock_validation_result)
                
                await service.resolve_selector(selector, "https://example.com", operation_type="click")
        else:
            await service.resolve_selector(selector, "https://example.com")
        
        # Verify AI call expectations
        if should_call_ai:
            mock_llm_manager.execute.assert_called_once()
        else:
            mock_llm_manager.execute.assert_not_called()
