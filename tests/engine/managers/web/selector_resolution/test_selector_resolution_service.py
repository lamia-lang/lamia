"""Tests for SelectorResolutionService with mocked interfaces."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from lamia.engine.managers.web.selector_resolution.selector_resolution_service import SelectorResolutionService
from lamia.engine.managers.web.selector_resolution.response_parser import AmbiguousFormatResponseParser
from lamia.engine.config_provider import ConfigProvider


class MockLLMResult:
    """Mock LLM result."""
    def __init__(self, text: str):
        self.validated_text = text


@pytest.fixture
def config_provider():
    """Create a config provider with human-in-loop disabled."""
    return ConfigProvider({
        "web_config": {
            "cache": {
                "enabled": True,
            },
            "human_in_loop": False,
        }
    })


@pytest.fixture
def human_in_loop_config_provider():
    """Create a config provider with human-in-loop enabled."""
    return ConfigProvider({
        "web_config": {
            "cache": {
                "enabled": True,
            },
            "human_in_loop": True,
        }
    })


@pytest.fixture
def mock_llm_manager():
    """Create a mock LLM manager."""
    manager = AsyncMock()
    return manager


@pytest.fixture
def mock_get_page_html():
    """Create a mock get_page_html function."""
    return AsyncMock(return_value="""
        <html>
            <body>
                <button class="btn__primary--large">Sign in</button>
                <button class="google-signin">Sign in with Google</button>
                <button class="apple-signin">Sign in with Apple</button>
            </body>
        </html>
        """)


@pytest.fixture
def mock_browser_adapter():
    """Create a mock browser adapter."""
    return AsyncMock()


@pytest.fixture
def mock_get_browser_adapter(mock_browser_adapter):
    """Create a mock get_browser_adapter function."""
    return AsyncMock(return_value=mock_browser_adapter)


@pytest.fixture
def service(mock_llm_manager, mock_get_page_html, mock_get_browser_adapter, config_provider):
    """Create a SelectorResolutionService with mocked dependencies."""
    service = SelectorResolutionService(
        llm_manager=mock_llm_manager,
        get_page_html_func=mock_get_page_html,
        get_browser_adapter_func=mock_get_browser_adapter,
        config_provider=config_provider,
    )
    service.cache.clear()
    return service


@pytest.fixture
def human_in_loop_service(mock_llm_manager, mock_get_page_html, mock_get_browser_adapter, human_in_loop_config_provider):
    """Create a SelectorResolutionService with human-in-loop enabled."""
    service = SelectorResolutionService(
        llm_manager=mock_llm_manager,
        get_page_html_func=mock_get_page_html,
        get_browser_adapter_func=mock_get_browser_adapter,
        config_provider=human_in_loop_config_provider,
    )
    service.cache.clear()
    return service


@pytest.mark.asyncio
async def test_resolve_valid_css_selector_no_ai_call(service, mock_llm_manager, mock_get_page_html, mock_get_browser_adapter):
    """Test that valid CSS selectors don't trigger AI calls."""
    result = await service.resolve_selector(
        selector="button.btn__primary",
        page_url="https://example.com"
    )
    
    assert result == "button.btn__primary"
    mock_llm_manager.execute.assert_not_called()
    mock_get_page_html.assert_not_awaited()
    mock_get_browser_adapter.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_natural_language_uses_progressive_resolver_and_caches(service, mock_llm_manager, mock_browser_adapter, mock_get_browser_adapter, config_provider):
    """Test natural language selector uses progressive resolver and caches results."""
    with patch("lamia.engine.managers.web.selector_resolution.selector_resolution_service.ProgressiveSelectorResolver") as MockResolver:
        mock_resolver = MockResolver.return_value
        mock_resolver.resolve = AsyncMock(return_value=("button.btn__primary--large", ["el"]))
        
        result = await service.resolve_selector(
            selector="sign in button",
            page_url="https://example.com",
            operation_type="click"
        )
    
    assert result == "button.btn__primary--large"
    mock_get_browser_adapter.assert_awaited_once()
    MockResolver.assert_called_once_with(mock_browser_adapter, mock_llm_manager, service.cache, config_provider)
    mock_resolver.resolve.assert_awaited_once_with("sign in button", "https://example.com", scope_element_handle=None)
    
    cached = await service.cache.get("sign in button", "https://example.com", None)
    assert cached == "button.btn__primary--large"


@pytest.mark.asyncio
async def test_resolve_natural_language_cache_hit_skips_progressive(service, mock_llm_manager, mock_browser_adapter, mock_get_browser_adapter, config_provider):
    """Test that cache hits skip progressive resolution."""
    with patch("lamia.engine.managers.web.selector_resolution.selector_resolution_service.ProgressiveSelectorResolver") as MockResolver:
        mock_resolver = MockResolver.return_value
        mock_resolver.resolve = AsyncMock(return_value=("button.cached", ["el"]))
        
        result1 = await service.resolve_selector(
            selector="sign in button",
            page_url="https://example.com"
        )
        result2 = await service.resolve_selector(
            selector="sign in button",
            page_url="https://example.com"
        )
    
    assert result1 == result2 == "button.cached"
    mock_resolver.resolve.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_natural_language_fallback_to_visual_picker_when_progressive_fails_and_human_in_loop_enabled(human_in_loop_service, mock_llm_manager, mock_browser_adapter, mock_get_browser_adapter, human_in_loop_config_provider):
    """Test visual picker fallback when progressive resolution fails."""
    with patch("lamia.engine.managers.web.selector_resolution.selector_resolution_service.ProgressiveSelectorResolver") as MockResolver, \
        patch("lamia.engine.managers.web.selector_resolution.visual_picker.VisualElementPicker") as MockPicker:
        mock_resolver = MockResolver.return_value
        mock_resolver.resolve = AsyncMock(side_effect=RuntimeError("progressive failed"))
        
        mock_picker = MockPicker.return_value
        mock_picker.pick_element_for_method = AsyncMock(return_value=("button.visual", ["el"]))
        
        result = await human_in_loop_service.resolve_selector(
            selector="sign in button",
            page_url="https://example.com",
            operation_type="click"
        )
    
    assert result == "button.visual"
    mock_get_browser_adapter.assert_awaited()
    MockResolver.assert_called_once_with(mock_browser_adapter, mock_llm_manager, human_in_loop_service.cache, human_in_loop_config_provider)
    mock_picker.pick_element_for_method.assert_awaited_once_with(method_name="click", description="sign in button", page_url="https://example.com")
    
    cached = await human_in_loop_service.cache.get("sign in button", "https://example.com", None)
    assert cached == "button.visual"


@pytest.mark.asyncio
async def test_resolve_natural_language_no_human_in_loop_raises(service, mock_llm_manager, mock_browser_adapter, mock_get_browser_adapter, config_provider):
    """Test natural language resolution fails without human-in-loop."""
    with patch("lamia.engine.managers.web.selector_resolution.selector_resolution_service.ProgressiveSelectorResolver") as MockResolver:
        mock_resolver = MockResolver.return_value
        mock_resolver.resolve = AsyncMock(side_effect=RuntimeError("progressive failed"))
        
        with pytest.raises(ValueError, match="Failed to resolve selector"):
            await service.resolve_selector(
                selector="sign in button",
                page_url="https://example.com"
            )


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
    
    assert "but not the" in exclusionary_text
    assert "Google" in exclusionary_text
    assert "Apple" in exclusionary_text
    assert css_selector == "button.btn__primary--large"


@pytest.mark.asyncio
async def test_operation_specific_instructions(service):
    """Test that different operation types get appropriate instructions."""
    click_instructions = service._get_operation_instructions("click")
    assert "CLICKABLE element" in click_instructions
    assert "button" in click_instructions.lower()
    
    type_instructions = service._get_operation_instructions("type_text")
    assert "INPUT element" in type_instructions
    assert "input" in type_instructions.lower()
    
    click_validation = service._get_operation_instructions("click", for_validation=True)
    assert "VALIDATION:" in click_validation
    assert "MULTIPLE clickable elements" in click_validation


@pytest.mark.asyncio
async def test_response_parser_interface(service):
    """Test that service uses response parser interface correctly."""
    parser = service.response_parser
    assert isinstance(parser, AmbiguousFormatResponseParser)
    
    html = "<button>Test</button>"
    operation_instructions = "OPERATION: Find button"
    
    full_prompt = parser.get_full_prompt_template(operation_instructions, html, "test")
    validation_prompt = parser.get_validation_prompt_template(operation_instructions, html, "test")
    
    assert "AMBIGUOUS" in full_prompt
    assert "FORMAT 1" in full_prompt
    assert "FORMAT 2" in full_prompt
    assert full_prompt == validation_prompt


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
            selector="button[",
            page_url="https://example.com",
            operation_type="click"
        )


@pytest.mark.asyncio
async def test_legacy_resolution_uses_parser_and_validator(mock_llm_manager, mock_get_page_html, mock_get_browser_adapter, mock_browser_adapter, config_provider):
    """Test legacy resolution path wires parser and validator."""
    mock_parser = Mock()
    mock_parser.get_full_prompt_template.return_value = "prompt"
    parse_result = Mock()
    parse_result.is_ambiguous = False
    parse_result.selector = "button.fixed"
    mock_parser.parse_response.return_value = parse_result
    
    service = SelectorResolutionService(
        llm_manager=mock_llm_manager,
        get_page_html_func=mock_get_page_html,
        get_browser_adapter_func=mock_get_browser_adapter,
        config_provider=config_provider,
        response_parser=mock_parser,
    )
    service.cache.clear()
    
    mock_llm_manager.execute.return_value = MockLLMResult("resolved")
    mock_validation_result = Mock()
    mock_validation_result.is_valid = True
    
    with patch('lamia.engine.managers.web.selector_resolution.validators.ai_resolved_selector_validator.AIResolvedSelectorValidator') as MockValidator:
        mock_validator = MockValidator.return_value
        mock_validator.validate_strict = AsyncMock(return_value=mock_validation_result)
        
        result = await service.resolve_selector(
            selector="button[",
            page_url="https://example.com",
            operation_type="click"
        )
    
    assert result == "button.fixed"
    mock_parser.get_full_prompt_template.assert_called_once()
    mock_parser.parse_response.assert_called_once_with("resolved", "button[")
    mock_validator.validate_strict.assert_awaited_once_with("button.fixed")


@pytest.mark.asyncio
async def test_cache_operations(service):
    """Test cache size and clear operations."""
    assert service.get_cache_size() == 0
    
    await service.cache.set("test selector", "https://example.com", "button.test")
    assert service.get_cache_size() == 1
    
    await service.clear_cache()
    assert service.get_cache_size() == 0


@pytest.mark.asyncio 
async def test_custom_response_parser_injection(config_provider):
    """Test that custom response parsers can be injected."""
    mock_parser = Mock()
    mock_llm_manager = AsyncMock()
    service = SelectorResolutionService(
        llm_manager=mock_llm_manager,
        config_provider=config_provider,
        response_parser=mock_parser
    )
    
    assert service.response_parser is mock_parser
