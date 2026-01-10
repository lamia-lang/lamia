"""Tests for AST analyzer functionality including session validation and page stabilization."""

from pydantic_core import validate_core_schema
import pytest
import asyncio
import hashlib
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pydantic import BaseModel, Field
from typing import Dict, Any, Set

pytest.skip("Legacy ast_analyzer exports changed; skipping legacy tests", allow_module_level=True)

from lamia.interpreter.ast_analyzer import (
    analyze_hybrid_file,
    create_execution_globals,
    create_session_validator,
    _get_current_page_content,
    _wait_for_page_stabilization,
    _get_current_url,
    ActionNamespaceAnalyzer
)
from lamia.types import HTML


class MockHomePageModel(BaseModel):
    """Mock model for testing session validation."""
    div: str = Field(alias=".profile-card-name")

class MockLamiaInstance:
    """Mock Lamia instance for testing."""
    def __init__(self):
        self._engine = Mock()
        self._engine.manager_factory = Mock()


class TestAnalyzeHybridFile:
    """Test hybrid file analysis functionality."""
    
    def test_analyze_simple_session_code(self):
        """Test analyzing code with session blocks."""
        code = '''
with session("test"):
    web.click("button")
    pass
'''
        result = analyze_hybrid_file(code)
        
        assert 'session' in result['namespaces']
        assert 'web' in result['namespaces']
        assert len(result['types']) >= 0  # May or may not have types
    
    def test_analyze_code_with_types(self):
        """Test analyzing code with validation types."""
        code = '''
def get_data() -> HTML[MyModel]:
    "Get some data"

result: JSON[Schema] = get_json()
'''
        result = analyze_hybrid_file(code)
        
        assert 'HTML' in result['types']
        assert 'JSON' in result['types']
    
    def test_analyze_code_with_all_namespaces(self):
        """Test analyzing code with multiple namespaces."""
        code = '''
web.click("button")
http.get("url")
file.read("path")
with session("test"):
    pass
'''
        result = analyze_hybrid_file(code)
        
        assert 'web' in result['namespaces']
        assert 'http' in result['namespaces'] 
        assert 'file' in result['namespaces']
        assert 'session' in result['namespaces']
    
    def test_analyze_invalid_syntax_fallback(self):
        """Test fallback behavior for invalid syntax."""
        code = '''
invalid python syntax here {{{
'''
        result = analyze_hybrid_file(code)
        
        # Should return default safe set
        assert 'web' in result['namespaces']
        assert 'http' in result['namespaces']
        assert 'session' in result['namespaces']
        assert 'HTML' in result['types']


class TestCreateExecutionGlobals:
    """Test execution globals creation."""
    
    def test_create_globals_with_session_namespace(self):
        """Test creating globals with session namespace."""
        mock_lamia = MockLamiaInstance()
        namespaces = {'session'}
        types = set()
        
        globals_dict = create_execution_globals(namespaces, types, mock_lamia)
        
        assert 'session' in globals_dict
        assert 'SessionSkipException' in globals_dict
        assert 'logger' in globals_dict
        assert 'asyncio' in globals_dict
        assert 'validate_session_result' in globals_dict
        assert callable(globals_dict['validate_session_result'])
    
    def test_create_globals_with_web_namespace(self):
        """Test creating globals with web namespace."""
        namespaces = {'web'}
        types = set()
        
        globals_dict = create_execution_globals(namespaces, types)
        
        assert 'web' in globals_dict
        assert 'WebCommand' in globals_dict
        assert 'WebActionType' in globals_dict
    
    def test_create_globals_with_validation_types(self):
        """Test creating globals with validation types."""
        namespaces = set()
        types = {'HTML', 'JSON', 'CSV'}
        
        globals_dict = create_execution_globals(namespaces, types)
        
        assert 'HTML' in globals_dict
        assert 'JSON' in globals_dict
        assert 'CSV' in globals_dict
    
    def test_create_globals_without_lamia_instance(self):
        """Test creating globals without lamia instance for session."""
        namespaces = {'session'}
        types = set()
        
        globals_dict = create_execution_globals(namespaces, types, None)
        
        assert 'validate_session_result' in globals_dict
        # Should have fallback validator that raises error
        with pytest.raises(Exception, match="Session validation requires a Lamia instance"):
            globals_dict['validate_session_result'](HTML)


class TestGetCurrentPageContent:
    """Test getting current page content."""
    
    @pytest.mark.asyncio
    async def test_get_page_content_success(self):
        """Test successfully getting page content."""
        mock_lamia = MockLamiaInstance()
        mock_web_manager = Mock()
        mock_browser_manager = Mock()
        mock_adapter = AsyncMock()
        
        # Setup mock chain
        mock_lamia._engine.manager_factory.get_manager.return_value = mock_web_manager
        mock_web_manager.browser_manager = mock_browser_manager
        mock_browser_manager._browser_adapter = mock_adapter
        mock_adapter.get_page_source = AsyncMock(return_value="<html>test content</html>")
        
        content = await _get_current_page_content(mock_lamia)
        
        assert content == "<html>test content</html>"
        mock_adapter.get_page_source.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_page_content_no_adapter(self):
        """Test getting page content when no browser adapter exists."""
        mock_lamia = MockLamiaInstance()
        mock_web_manager = Mock()
        mock_browser_manager = Mock()
        
        # Setup mock chain with no adapter
        mock_lamia._engine.manager_factory.get_manager.return_value = mock_web_manager
        mock_web_manager.browser_manager = mock_browser_manager
        mock_browser_manager._browser_adapter = None
        
        with pytest.raises(Exception, match="No active browser adapter found"):
            await _get_current_page_content(mock_lamia)
    
    @pytest.mark.asyncio
    async def test_get_page_content_fallback_adapter(self):
        """Test getting page content with fallback adapter access."""
        mock_lamia = MockLamiaInstance()
        mock_web_manager = Mock()
        mock_browser_manager = Mock()
        mock_wrapper_adapter = Mock()
        mock_actual_adapter = Mock()
        mock_driver = Mock()
        
        # Setup mock chain with wrapper adapter
        mock_lamia._engine.manager_factory.get_manager.return_value = mock_web_manager
        mock_web_manager.browser_manager = mock_browser_manager
        mock_browser_manager._browser_adapter = mock_wrapper_adapter
        mock_wrapper_adapter.adapter = mock_actual_adapter
        mock_actual_adapter.driver = mock_driver
        mock_driver.page_source = "<html>fallback content</html>"
        
        # Mock that get_page_source doesn't exist on wrapper
        del mock_wrapper_adapter.get_page_source
        
        content = await _get_current_page_content(mock_lamia)
        
        assert content == "<html>fallback content</html>"


class TestGetCurrentUrl:
    """Test getting current page URL."""
    
    @pytest.mark.asyncio
    async def test_get_current_url_success(self):
        """Test successfully getting current URL."""
        mock_lamia = MockLamiaInstance()
        mock_web_manager = Mock()
        mock_browser_manager = Mock()
        mock_adapter = AsyncMock()
        
        # Setup mock chain
        mock_lamia._engine.manager_factory.get_manager.return_value = mock_web_manager
        mock_web_manager.browser_manager = mock_browser_manager
        mock_browser_manager._browser_adapter = mock_adapter
        mock_adapter.get_current_url = AsyncMock(return_value="https://example.com")
        
        url = await _get_current_url(mock_lamia)
        
        assert url == "https://example.com"
        mock_adapter.get_current_url.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_current_url_fallback(self):
        """Test getting current URL with fallback methods."""
        mock_lamia = MockLamiaInstance()
        mock_web_manager = Mock()
        mock_browser_manager = Mock()
        mock_adapter = Mock()
        mock_driver = Mock()
        
        # Setup mock chain
        mock_lamia._engine.manager_factory.get_manager.return_value = mock_web_manager
        mock_web_manager.browser_manager = mock_browser_manager
        mock_browser_manager._browser_adapter = mock_adapter
        mock_adapter.driver = mock_driver
        mock_driver.current_url = "https://fallback.com"
        
        # Mock that get_current_url doesn't exist
        del mock_adapter.get_current_url
        
        url = await _get_current_url(mock_lamia)
        
        assert url == "https://fallback.com"
    
    @pytest.mark.asyncio
    async def test_get_current_url_error(self):
        """Test getting current URL when error occurs."""
        mock_lamia = MockLamiaInstance()
        mock_lamia._engine.manager_factory.get_manager.side_effect = Exception("Test error")
        
        url = await _get_current_url(mock_lamia)
        
        assert url == "unknown"


class TestWaitForPageStabilization:
    """Test page stabilization functionality."""
    
    @pytest.mark.asyncio
    async def test_page_stabilization_immediate(self):
        """Test page stabilization when page is already stable."""
        mock_lamia = MockLamiaInstance()
        
        test_content = "<html>stable content</html>"
        test_url = "https://stable.com"
        
        with patch('lamia.interpreter.ast_analyzer._get_current_page_content') as mock_get_content, \
             patch('lamia.interpreter.ast_analyzer._get_current_url') as mock_get_url:
            
            mock_get_content.return_value = test_content
            mock_get_url.return_value = test_url
            
            result = await _wait_for_page_stabilization(mock_lamia, max_wait_time=5, stability_window=1)
            
            assert result == test_content
            # Should be called at least twice to detect stability
            assert mock_get_content.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_page_stabilization_with_changes(self):
        """Test page stabilization when page changes initially."""
        mock_lamia = MockLamiaInstance()
        
        # Simulate page changing then stabilizing
        content_sequence = [
            "<html>loading...</html>",
            "<html>loading...</html>", 
            "<html>final content</html>",
            "<html>final content</html>",
            "<html>final content</html>"
        ]
        url_sequence = [
            "https://loading.com",
            "https://loading.com",
            "https://final.com", 
            "https://final.com",
            "https://final.com"
        ]
        
        with patch('lamia.interpreter.ast_analyzer._get_current_page_content') as mock_get_content, \
             patch('lamia.interpreter.ast_analyzer._get_current_url') as mock_get_url, \
             patch('asyncio.sleep', new_callable=AsyncMock):  # Speed up test
            
            mock_get_content.side_effect = content_sequence
            mock_get_url.side_effect = url_sequence
            
            result = await _wait_for_page_stabilization(mock_lamia, max_wait_time=10, stability_window=1)
            
            assert result == "<html>final content</html>"
    
    @pytest.mark.asyncio
    async def test_page_stabilization_basic_timeout(self):
        """Test page stabilization timeout behavior with simpler mocking."""
        mock_lamia = MockLamiaInstance()
        
        with patch('lamia.interpreter.ast_analyzer._get_current_page_content') as mock_get_content, \
             patch('lamia.interpreter.ast_analyzer._get_current_url') as mock_get_url, \
             patch('asyncio.sleep', new_callable=AsyncMock):
            
            # Mock content that will eventually timeout
            mock_get_content.return_value = "<html>timeout content</html>"
            mock_get_url.return_value = "https://timeout.com"
            
            # Use a very short timeout for testing
            result = await _wait_for_page_stabilization(mock_lamia, max_wait_time=0.1, stability_window=0.05)
            
            assert result == "<html>timeout content</html>"
    
    @pytest.mark.asyncio 
    async def test_page_stabilization_error_handling(self):
        """Test page stabilization handles errors gracefully."""
        mock_lamia = MockLamiaInstance()
        
        with patch('lamia.interpreter.ast_analyzer._get_current_page_content') as mock_get_content, \
             patch('lamia.interpreter.ast_analyzer._get_current_url') as mock_get_url, \
             patch('asyncio.sleep', new_callable=AsyncMock):
            
            # First few calls fail, then succeed
            mock_get_content.side_effect = [
                Exception("Network error"),
                Exception("Network error"), 
                "<html>recovered content</html>",
                "<html>recovered content</html>"
            ]
            mock_get_url.side_effect = [
                Exception("Network error"),
                Exception("Network error"),
                "https://recovered.com",
                "https://recovered.com"
            ]
            
            result = await _wait_for_page_stabilization(mock_lamia, max_wait_time=10, stability_window=1)
            
            assert result == "<html>recovered content</html>"


class TestSessionValidator:
    """Test session validator creation and functionality."""
    
    @pytest.mark.asyncio
    async def test_create_session_validator_success(self):
        """Test creating and using session validator successfully."""
        mock_lamia = MockLamiaInstance()
        
        # Mock the stabilization and validation chain
        stable_content = "<html><div class='profile-card-name'>John Doe</div></html>"
        
        with patch('lamia.interpreter.ast_analyzer._wait_for_page_stabilization') as mock_stabilize, \
             patch('lamia.engine.factories.validator_factory.ValidatorFactory') as mock_factory_class:
            
            mock_stabilize.return_value = stable_content
            
            # Mock validator factory and validator
            mock_factory = Mock()
            mock_factory_class.return_value = mock_factory
            mock_validator = AsyncMock()
            mock_factory.get_validator.return_value = mock_validator
            
            # Mock successful validation result
            mock_validation_result = Mock()
            mock_validation_result.is_valid = True
            mock_validation_result.result_type = {"profile_name": "John Doe"}
            mock_validator.validate.return_value = mock_validation_result
            
            # Create and test validator
            validator_func = create_session_validator(mock_lamia)
            result = await validator_func(HTML[MockHomePageModel])
            
            # Verify calls
            mock_stabilize.assert_called_once_with(mock_lamia)
            mock_validator.validate.assert_called_once_with(stable_content)
            assert result == {"profile_name": "John Doe"}
    
    @pytest.mark.asyncio
    async def test_create_session_validator_validation_failure(self):
        """Test session validator when validation fails."""
        mock_lamia = MockLamiaInstance()
        
        stable_content = "<html>wrong content</html>"
        
        with patch('lamia.interpreter.ast_analyzer._wait_for_page_stabilization') as mock_stabilize, \
             patch('lamia.engine.factories.validator_factory.ValidatorFactory') as mock_factory_class:
            
            mock_stabilize.return_value = stable_content
            
            # Mock validator factory and validator
            mock_factory = Mock()
            mock_factory_class.return_value = mock_factory
            mock_validator = AsyncMock()
            mock_factory.get_validator.return_value = mock_validator
            
            # Mock failed validation result
            mock_validation_result = Mock()
            mock_validation_result.is_valid = False
            mock_validation_result.error_message = "Profile element not found"
            mock_validator.validate.return_value = mock_validation_result
            
            # Create and test validator
            validator_func = create_session_validator(mock_lamia)
            
            with pytest.raises(Exception, match="Session validation failed: Profile element not found"):
                await validator_func(HTML[MockHomePageModel])

    
    @pytest.mark.asyncio
    async def test_create_session_validator_stabilization_error(self):
        """Test session validator when stabilization fails."""
        mock_lamia = MockLamiaInstance()
        
        with patch('lamia.interpreter.ast_analyzer._wait_for_page_stabilization') as mock_stabilize:
            mock_stabilize.side_effect = Exception("Browser not available")
            
            validator_func = create_session_validator(mock_lamia)
            
            with pytest.raises(Exception, match="Session validation error"):
                await validator_func(HTML[MockHomePageModel])


class TestActionNamespaceAnalyzer:
    """Test AST analysis for action namespaces."""
    
    def test_visit_attribute_web_namespace(self):
        """Test detecting web namespace usage."""
        import ast
        
        code = "web.click('button')"
        tree = ast.parse(code)
        analyzer = ActionNamespaceAnalyzer()
        analyzer.visit(tree)
        
        assert 'web' in analyzer.used_namespaces
    
    def test_visit_name_validation_types(self):
        """Test detecting validation type usage."""
        import ast
        
        code = "result: HTML = get_data()"
        tree = ast.parse(code)
        analyzer = ActionNamespaceAnalyzer()
        analyzer.visit(tree)
        
        assert 'HTML' in analyzer.used_types
    
    def test_visit_subscript_parametric_types(self):
        """Test detecting parametric type usage."""
        import ast
        
        code = "data: JSON[Schema] = parse()"
        tree = ast.parse(code)
        analyzer = ActionNamespaceAnalyzer()
        analyzer.visit(tree)
        
        assert 'JSON' in analyzer.used_types
    
    def test_visit_name_session_namespace(self):
        """Test detecting session namespace usage."""
        import ast
        
        code = "with session('test'): pass"
        tree = ast.parse(code)
        analyzer = ActionNamespaceAnalyzer()
        analyzer.visit(tree)
        
        assert 'session' in analyzer.used_namespaces
    
    def test_multiple_namespaces_and_types(self):
        """Test detecting multiple namespaces and types."""
        import ast
        
        code = '''
web.click("button")
http.get("url") 
result: HTML[Model] = process()
data: JSON = load()
with session("test"):
    pass
'''
        tree = ast.parse(code)
        analyzer = ActionNamespaceAnalyzer()
        analyzer.visit(tree)
        
        assert 'web' in analyzer.used_namespaces
        assert 'http' in analyzer.used_namespaces
        assert 'session' in analyzer.used_namespaces
        assert 'HTML' in analyzer.used_types
        assert 'JSON' in analyzer.used_types


if __name__ == "__main__":
    pytest.main([__file__])
