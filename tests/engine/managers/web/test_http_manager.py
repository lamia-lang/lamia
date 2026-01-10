"""Tests for HttpManager."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import requests
from lamia.engine.managers.web.http_manager import HttpManager
from lamia.engine.config_provider import ConfigProvider
from lamia.validation.base import ValidationResult, BaseValidator
from lamia.interpreter.commands import WebCommand, WebActionType


class TestHttpManagerInitialization:
    """Test HttpManager initialization."""
    
    def test_initialization_with_config_provider(self):
        """Test initialization with config provider."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        
        manager = HttpManager(config_provider)
        
        assert manager.config_provider == config_provider
        assert manager._http_client == "requests"  # default
        assert manager._http_options["timeout"] == 30.0  # default
        assert manager._http_options["user_agent"] == "Lamia/1.0"  # default
    
    def test_initialization_with_http_config(self):
        """Test initialization with HTTP configuration."""
        http_config = {
            "http_client": "custom_client",
            "http_options": {
                "timeout": 60.0,
                "user_agent": "CustomAgent/1.0",
                "custom_option": "test_value"
            }
        }
        config_dict = {"web_config": http_config}
        config_provider = ConfigProvider(config_dict)
        
        manager = HttpManager(config_provider)
        
        assert manager._http_client == "custom_client"
        assert manager._http_options["timeout"] == 60.0
        assert manager._http_options["user_agent"] == "CustomAgent/1.0"
        assert manager._http_options["custom_option"] == "test_value"
    
    def test_initialization_with_partial_http_options(self):
        """Test initialization with partial HTTP options preserves defaults."""
        http_config = {
            "http_options": {
                "timeout": 45.0
                # user_agent missing, should use default
            }
        }
        config_dict = {"web_config": http_config}
        config_provider = ConfigProvider(config_dict)
        
        manager = HttpManager(config_provider)
        
        assert manager._http_options["timeout"] == 45.0  # from config
        assert manager._http_options["user_agent"] == "Lamia/1.0"  # default


class TestHttpManagerCommandValidation:
    """Test HTTP command validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        self.manager = HttpManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_execute_with_non_http_action_raises_error(self):
        """Test that non-HTTP actions raise ValueError."""
        command = WebCommand(action=WebActionType.CLICK, selector="#button")
        
        with pytest.raises(ValueError, match="Not an HTTP action: WebActionType.CLICK"):
            await self.manager.execute(command)
    
    @pytest.mark.asyncio
    async def test_execute_with_missing_url_raises_error(self):
        """Test that missing URL raises ValueError."""
        command = WebCommand(action=WebActionType.HTTP_REQUEST, method="GET")
        
        with pytest.raises(ValueError, match="HTTP request requires a URL"):
            await self.manager.execute(command)
    
    @pytest.mark.asyncio
    async def test_execute_with_empty_url_raises_error(self):
        """Test that empty URL raises ValueError."""
        command = WebCommand(action=WebActionType.HTTP_REQUEST, method="GET", url="")
        
        with pytest.raises(ValueError, match="HTTP request requires a URL"):
            await self.manager.execute(command)


class TestHttpManagerRequestExecution:
    """Test HTTP request execution."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        self.manager = HttpManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_execute_get_request(self):
        """Test executing GET request."""
        command = WebCommand(action=WebActionType.HTTP_REQUEST, url="https://example.com")
        
        with patch.object(self.manager, '_do_request') as mock_request:
            mock_request.return_value = "<html>Test response</html>"
            
            with patch('asyncio.to_thread') as mock_to_thread:
                mock_to_thread.return_value = "<html>Test response</html>"
                
                result = await self.manager.execute(command)
                
                assert result == "<html>Test response</html>"
                mock_to_thread.assert_called_once_with(
                    self.manager._do_request,
                    "GET",  # default method
                    "https://example.com",
                    {},  # empty headers
                    None,  # no data
                    30.0  # default timeout
                )
    
    @pytest.mark.asyncio
    async def test_execute_post_request_with_data(self):
        """Test executing POST request with data."""
        command = WebCommand(
            action=WebActionType.HTTP_REQUEST,
            method="POST",
            url="https://api.example.com/data",
            headers={"Content-Type": "application/json"},
            data={"key": "value"}
        )
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = '{"success": true}'
            
            result = await self.manager.execute(command)
            
            assert result == '{"success": true}'
            mock_to_thread.assert_called_once_with(
                self.manager._do_request,
                "POST",
                "https://api.example.com/data",
                {"Content-Type": "application/json"},
                {"key": "value"},
                30.0
            )
    
    @pytest.mark.asyncio
    async def test_execute_put_request(self):
        """Test executing PUT request."""
        command = WebCommand(
            action=WebActionType.HTTP_REQUEST,
            method="put",  # lowercase should be converted
            url="https://api.example.com/update",
            data="update data"
        )
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = "Updated successfully"
            
            result = await self.manager.execute(command)
            
            assert result == "Updated successfully"
            # Verify method was converted to uppercase
            args = mock_to_thread.call_args[0]
            assert args[1] == "PUT"  # method argument
    
    @pytest.mark.asyncio
    async def test_execute_delete_request(self):
        """Test executing DELETE request."""
        command = WebCommand(
            action=WebActionType.HTTP_REQUEST,
            method="DELETE",
            url="https://api.example.com/delete/123"
        )
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = "Deleted successfully"
            
            result = await self.manager.execute(command)
            
            assert result == "Deleted successfully"
            args = mock_to_thread.call_args[0]
            assert args[1] == "DELETE"
    
    @pytest.mark.asyncio
    async def test_execute_with_custom_timeout(self):
        """Test executing request with custom timeout from config."""
        http_config = {
            "http_options": {
                "timeout": 60.0
            }
        }
        config_dict = {"web_config": http_config}
        config_provider = ConfigProvider(config_dict)
        manager = HttpManager(config_provider)
        
        command = WebCommand(action=WebActionType.HTTP_REQUEST, url="https://example.com")
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = "Response"
            
            await manager.execute(command)
            
            # Verify custom timeout was used
            args = mock_to_thread.call_args[0]
            assert args[5] == 60.0  # timeout argument


class TestHttpManagerRequestImplementation:
    """Test the underlying request implementation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        self.manager = HttpManager(self.config_provider)
    
    @patch('requests.request')
    def test_do_request_get_success(self, mock_request):
        """Test _do_request with successful GET."""
        mock_response = Mock()
        mock_response.text = "<html>Success</html>"
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        result = self.manager._do_request(
            "GET", 
            "https://example.com", 
            {"User-Agent": "test"}, 
            None, 
            30.0
        )
        
        assert result == "<html>Success</html>"
        mock_request.assert_called_once_with(
            method="GET",
            url="https://example.com",
            headers={"User-Agent": "test"},
            data=None,
            timeout=30.0
        )
        mock_response.raise_for_status.assert_called_once()
    
    @patch('requests.request')
    def test_do_request_post_with_data(self, mock_request):
        """Test _do_request with POST and data."""
        mock_response = Mock()
        mock_response.text = '{"created": true}'
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        result = self.manager._do_request(
            "POST",
            "https://api.example.com/create",
            {"Content-Type": "application/json"},
            '{"name": "test"}',
            15.0
        )
        
        assert result == '{"created": true}'
        mock_request.assert_called_once_with(
            method="POST",
            url="https://api.example.com/create",
            headers={"Content-Type": "application/json"},
            data='{"name": "test"}',
            timeout=15.0
        )
    
    @patch('requests.request')
    def test_do_request_http_error_raises_exception(self, mock_request):
        """Test _do_request raises exception on HTTP error."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_request.return_value = mock_response
        
        with pytest.raises(requests.HTTPError, match="404 Not Found"):
            self.manager._do_request("GET", "https://example.com/notfound", {}, None, 30.0)
        
        mock_response.raise_for_status.assert_called_once()
    
    @patch('requests.request')
    def test_do_request_connection_error_raises_exception(self, mock_request):
        """Test _do_request raises exception on connection error."""
        mock_request.side_effect = requests.ConnectionError("Connection failed")
        
        with pytest.raises(requests.ConnectionError, match="Connection failed"):
            self.manager._do_request("GET", "https://unreachable.com", {}, None, 30.0)
    
    @patch('requests.request')
    def test_do_request_timeout_error_raises_exception(self, mock_request):
        """Test _do_request raises exception on timeout."""
        mock_request.side_effect = requests.Timeout("Request timeout")
        
        with pytest.raises(requests.Timeout, match="Request timeout"):
            self.manager._do_request("GET", "https://slow.com", {}, None, 1.0)


class TestHttpManagerConfiguration:
    """Test HTTP manager configuration handling."""
    
    def test_default_http_client(self):
        """Test default HTTP client selection."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        
        manager = HttpManager(config_provider)
        
        assert manager._http_client == "requests"
    
    def test_custom_http_client(self):
        """Test custom HTTP client selection."""
        http_config = {"http_client": "httpx"}
        config_dict = {"web_config": http_config}
        config_provider = ConfigProvider(config_dict)
        
        manager = HttpManager(config_provider)
        
        assert manager._http_client == "httpx"
    
    def test_http_options_override_defaults(self):
        """Test that HTTP options override defaults."""
        http_config = {
            "http_options": {
                "timeout": 120.0,
                "user_agent": "CustomBot/2.0"
            }
        }
        config_dict = {"web_config": http_config}
        config_provider = ConfigProvider(config_dict)
        
        manager = HttpManager(config_provider)
        
        assert manager._http_options["timeout"] == 120.0
        assert manager._http_options["user_agent"] == "CustomBot/2.0"
    
    def test_http_options_preserve_additional_settings(self):
        """Test that additional HTTP options are preserved."""
        http_config = {
            "http_options": {
                "verify_ssl": True,
                "max_redirects": 5,
                "proxy": "http://proxy.example.com:8080"
            }
        }
        config_dict = {"web_config": http_config}
        config_provider = ConfigProvider(config_dict)
        
        manager = HttpManager(config_provider)
        
        assert manager._http_options["verify_ssl"] is True
        assert manager._http_options["max_redirects"] == 5
        assert manager._http_options["proxy"] == "http://proxy.example.com:8080"
        # Defaults should still be set
        assert manager._http_options["timeout"] == 30.0
        assert manager._http_options["user_agent"] == "Lamia/1.0"


class TestHttpManagerEdgeCases:
    """Test edge cases and error conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        self.manager = HttpManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_execute_with_none_method_defaults_to_get(self):
        """Test that None method defaults to GET."""
        command = WebCommand(action=WebActionType.HTTP_REQUEST, url="https://example.com", method=None)
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = "Response"
            
            await self.manager.execute(command)
            
            args = mock_to_thread.call_args[0]
            assert args[1] == "GET"  # method argument
    
    @pytest.mark.asyncio
    async def test_execute_with_none_headers_uses_empty_dict(self):
        """Test that None headers uses empty dict."""
        command = WebCommand(action=WebActionType.HTTP_REQUEST, url="https://example.com", headers=None)
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = "Response"
            
            await self.manager.execute(command)
            
            args = mock_to_thread.call_args[0]
            assert args[3] == {}  # headers argument
    
    @pytest.mark.asyncio
    async def test_execute_with_validator_parameter(self):
        """Test execute with validator parameter (should work but not be used)."""
        command = WebCommand(action=WebActionType.HTTP_REQUEST, url="https://example.com")
        validator = Mock(spec=BaseValidator)
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = "Response"
            
            result = await self.manager.execute(command, validator=validator)
            
            assert result == "Response"
            # Validator should not be called - HttpManager doesn't use it currently
    
    @patch('requests.request')
    def test_do_request_with_complex_headers(self, mock_request):
        """Test _do_request with complex headers."""
        mock_response = Mock()
        mock_response.text = "Success"
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        complex_headers = {
            "User-Agent": "Lamia/1.0",
            "Authorization": "Bearer token123",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Custom-Header": "custom-value"
        }
        
        result = self.manager._do_request("POST", "https://example.com", complex_headers, None, 30.0)
        
        assert result == "Success"
        mock_request.assert_called_once_with(
            method="POST",
            url="https://example.com",
            headers=complex_headers,
            data=None,
            timeout=30.0
        )


class TestHttpManagerCleanup:
    """Test HTTP manager cleanup functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        self.manager = HttpManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_close_does_not_error(self):
        """Test that close method doesn't error."""
        # Should not raise any exception
        await self.manager.close()
        
        # HttpManager doesn't have persistent connections to close
        # This test just verifies the method exists and can be called


class TestHttpManagerIntegration:
    """Test integration scenarios."""
    
    def test_realistic_http_manager_configuration(self):
        """Test realistic HTTP manager configuration."""
        config_dict = {
            "web_config": {
                "http_client": "requests",
                "http_options": {
                    "timeout": 45.0,
                    "user_agent": "Lamia-WebBot/1.0",
                    "verify_ssl": True
                }
            }
        }
        config_provider = ConfigProvider(config_dict)
        manager = HttpManager(config_provider)
        
        assert manager.config_provider == config_provider
        assert manager._http_client == "requests"
        assert manager._http_options["timeout"] == 45.0
        assert manager._http_options["user_agent"] == "Lamia-WebBot/1.0"
        assert manager._http_options["verify_ssl"] is True
    
    @pytest.mark.asyncio
    async def test_realistic_api_request_sequence(self):
        """Test realistic sequence of API requests."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        manager = HttpManager(config_provider)
        
        commands = [
            WebCommand(action=WebActionType.HTTP_REQUEST, method="GET", url="https://api.example.com/users"),
            WebCommand(action=WebActionType.HTTP_REQUEST, method="POST", url="https://api.example.com/users", 
                      data='{"name": "John"}', headers={"Content-Type": "application/json"}),
            WebCommand(action=WebActionType.HTTP_REQUEST, method="PUT", url="https://api.example.com/users/123",
                      data='{"name": "John Updated"}', headers={"Content-Type": "application/json"}),
            WebCommand(action=WebActionType.HTTP_REQUEST, method="DELETE", url="https://api.example.com/users/123")
        ]
        
        expected_responses = [
            '{"users": []}',
            '{"id": 123, "name": "John"}',
            '{"id": 123, "name": "John Updated"}',
            '{"success": true}'
        ]
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.side_effect = expected_responses
            
            results = []
            for command in commands:
                result = await manager.execute(command)
                results.append(result)
            
            assert results == expected_responses
            assert mock_to_thread.call_count == 4
            
            # Verify first call (GET)
            first_call_args = mock_to_thread.call_args_list[0][0]
            assert first_call_args[1] == "GET"
            assert first_call_args[2] == "https://api.example.com/users"
            
            # Verify second call (POST)
            second_call_args = mock_to_thread.call_args_list[1][0]
            assert second_call_args[1] == "POST"
            assert second_call_args[4] == '{"name": "John"}'