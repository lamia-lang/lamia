"""Comprehensive tests for RequestsAdapter HTTP implementation."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import requests
import json
from requests.exceptions import RequestException, HTTPError, ConnectionError, Timeout
from lamia.adapters.web.http.http_adapter import RequestsAdapter
from lamia.internal_types import HttpActionParams


class TestRequestsAdapterInitialization:
    """Test RequestsAdapter initialization and configuration."""
    
    def test_initialization_with_defaults(self):
        """Test initialization with default parameters."""
        adapter = RequestsAdapter()
        
        assert adapter.session is None
        assert adapter.default_timeout == 30.0
        assert adapter.user_agent == "Lamia/1.0"
        assert not adapter.initialized
    
    def test_initialization_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        adapter = RequestsAdapter(timeout=60.0, user_agent="Custom/2.0")
        
        assert adapter.default_timeout == 60.0
        assert adapter.user_agent == "Custom/2.0"
        assert not adapter.initialized
    
    def test_initialization_state(self):
        """Test initial state of adapter."""
        adapter = RequestsAdapter()
        
        assert adapter.session is None
        assert not adapter.initialized


class TestRequestsAdapterLifecycle:
    """Test RequestsAdapter lifecycle management."""
    
    @pytest.mark.asyncio
    @patch('requests.Session')
    async def test_initialize_creates_session(self, mock_session_class):
        """Test that initialize creates requests session."""
        mock_session = Mock()
        mock_session.headers = Mock()
        mock_session_class.return_value = mock_session
        
        adapter = RequestsAdapter(user_agent="Test/1.0")
        await adapter.initialize()
        
        # Session should be created
        assert adapter.session is mock_session
        assert adapter.initialized
        
        # Headers should be set
        mock_session.headers.update.assert_called_once_with({
            'User-Agent': 'Test/1.0'
        })
    
    @pytest.mark.asyncio
    @patch('requests.Session')
    async def test_close_cleanup(self, mock_session_class):
        """Test that close properly cleans up resources."""
        mock_session = Mock()
        mock_session.headers = Mock()
        mock_session_class.return_value = mock_session
        
        adapter = RequestsAdapter()
        await adapter.initialize()
        
        # Verify initialized
        assert adapter.initialized
        assert adapter.session is mock_session
        
        # Close
        await adapter.close()
        
        # Should clean up
        mock_session.close.assert_called_once()
        assert adapter.session is None
        assert not adapter.initialized
    
    @pytest.mark.asyncio
    async def test_close_without_session(self):
        """Test close when no session exists."""
        adapter = RequestsAdapter()
        
        # Should not raise error
        await adapter.close()
        
        assert adapter.session is None
        assert not adapter.initialized


class TestRequestsAdapterRequestPreparation:
    """Test RequestsAdapter request preparation logic."""
    
    def test_prepare_request_kwargs_basic(self):
        """Test basic request kwargs preparation."""
        adapter = RequestsAdapter(timeout=45.0)
        
        params = HttpActionParams(
            url="https://example.com",
            headers={"Custom": "Header"},
            params={"q": "search"}
        )
        
        kwargs = adapter._prepare_request_kwargs(params)
        
        assert kwargs['timeout'] == 45.0
        assert kwargs['headers'] == {"Custom": "Header"}
        assert kwargs['params'] == {"q": "search"}
    
    def test_prepare_request_kwargs_with_dict_data(self):
        """Test request preparation with dict data (JSON)."""
        adapter = RequestsAdapter()
        
        params = HttpActionParams(
            url="https://api.example.com",
            data={"name": "test", "value": 123}
        )
        
        kwargs = adapter._prepare_request_kwargs(params)
        
        assert 'json' in kwargs
        assert kwargs['json'] == {"name": "test", "value": 123}
        assert kwargs['headers']['Content-Type'] == 'application/json'
    
    def test_prepare_request_kwargs_with_string_data(self):
        """Test request preparation with string data."""
        adapter = RequestsAdapter()
        
        params = HttpActionParams(
            url="https://api.example.com",
            data="raw string data"
        )
        
        kwargs = adapter._prepare_request_kwargs(params)
        
        assert 'data' in kwargs
        assert kwargs['data'] == "raw string data"
        assert 'json' not in kwargs
    
    def test_prepare_request_kwargs_no_data(self):
        """Test request preparation with no data."""
        adapter = RequestsAdapter()
        
        params = HttpActionParams(url="https://example.com")
        
        kwargs = adapter._prepare_request_kwargs(params)
        
        assert 'data' not in kwargs
        assert 'json' not in kwargs
    
    def test_prepare_request_kwargs_headers_merging(self):
        """Test that headers are properly handled."""
        adapter = RequestsAdapter()
        
        # With existing Content-Type
        params = HttpActionParams(
            url="https://api.example.com",
            headers={"Content-Type": "application/xml"},
            data={"key": "value"}
        )
        
        kwargs = adapter._prepare_request_kwargs(params)
        
        # Should not override existing Content-Type
        assert kwargs['headers']['Content-Type'] == 'application/xml'


class TestRequestsAdapterResponseHandling:
    """Test RequestsAdapter response handling logic."""
    
    def test_handle_response_json(self):
        """Test handling JSON response."""
        adapter = RequestsAdapter()
        
        mock_response = Mock()
        mock_response.json.return_value = {"success": True, "data": [1, 2, 3]}
        
        result = adapter._handle_response(mock_response)
        
        assert result == {"success": True, "data": [1, 2, 3]}
        mock_response.json.assert_called_once()
    
    def test_handle_response_text_fallback(self):
        """Test handling non-JSON response."""
        adapter = RequestsAdapter()
        
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        mock_response.text = "Plain text response"
        
        result = adapter._handle_response(mock_response)
        
        assert result == "Plain text response"
        mock_response.json.assert_called_once()
    
    def test_handle_response_empty_text(self):
        """Test handling empty text response."""
        adapter = RequestsAdapter()
        
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        mock_response.text = ""
        
        result = adapter._handle_response(mock_response)
        
        assert result == ""


class TestRequestsAdapterHTTPMethods:
    """Test RequestsAdapter HTTP method implementations."""
    
    @pytest.fixture
    def adapter(self):
        """Create initialized adapter for testing."""
        adapter = RequestsAdapter()
        adapter.session = Mock()
        adapter.initialized = True
        return adapter
    
    @pytest.mark.asyncio
    async def test_get_method(self, adapter):
        """Test GET request implementation."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {"data": "response"}
        adapter.session.get.return_value = mock_response
        
        params = HttpActionParams(
            url="https://api.example.com/data",
            headers={"Authorization": "Bearer token"},
            params={"page": 1}
        )
        
        result = await adapter.get(params)
        
        assert result == {"data": "response"}
        
        # Verify call
        adapter.session.get.assert_called_once_with(
            "https://api.example.com/data",
            timeout=30.0,
            headers={"Authorization": "Bearer token"},
            params={"page": 1}
        )
        mock_response.raise_for_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_post_method_with_json(self, adapter):
        """Test POST request with JSON data."""
        mock_response = Mock()
        mock_response.json.return_value = {"created": True}
        adapter.session.post.return_value = mock_response
        
        params = HttpActionParams(
            url="https://api.example.com/create",
            data={"name": "test", "value": 123}
        )
        
        result = await adapter.post(params)
        
        assert result == {"created": True}
        
        # Verify call - should use json parameter
        call_args = adapter.session.post.call_args
        assert call_args[0][0] == "https://api.example.com/create"
        assert 'json' in call_args[1]
        assert call_args[1]['json'] == {"name": "test", "value": 123}
        mock_response.raise_for_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_post_method_with_form_data(self, adapter):
        """Test POST request with form data."""
        mock_response = Mock()
        mock_response.text = "Form submitted"
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        adapter.session.post.return_value = mock_response
        
        params = HttpActionParams(
            url="https://example.com/form",
            data="name=test&value=123"
        )
        
        result = await adapter.post(params)
        
        assert result == "Form submitted"
        
        # Verify call - should use data parameter
        call_args = adapter.session.post.call_args
        assert 'data' in call_args[1]
        assert call_args[1]['data'] == "name=test&value=123"
    
    @pytest.mark.asyncio
    async def test_put_method(self, adapter):
        """Test PUT request implementation."""
        mock_response = Mock()
        mock_response.json.return_value = {"updated": True}
        adapter.session.put.return_value = mock_response
        
        params = HttpActionParams(
            url="https://api.example.com/update/123",
            data={"status": "active"}
        )
        
        result = await adapter.put(params)
        
        assert result == {"updated": True}
        adapter.session.put.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_patch_method(self, adapter):
        """Test PATCH request implementation."""
        mock_response = Mock()
        mock_response.json.return_value = {"patched": True}
        adapter.session.patch.return_value = mock_response
        
        params = HttpActionParams(
            url="https://api.example.com/patch/123",
            data={"field": "new_value"}
        )
        
        result = await adapter.patch(params)
        
        assert result == {"patched": True}
        adapter.session.patch.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_method(self, adapter):
        """Test DELETE request implementation."""
        mock_response = Mock()
        mock_response.json.return_value = {"deleted": True}
        adapter.session.delete.return_value = mock_response
        
        params = HttpActionParams(url="https://api.example.com/delete/123")
        
        result = await adapter.delete(params)
        
        assert result == {"deleted": True}
        
        # DELETE should not include data
        call_args = adapter.session.delete.call_args
        assert 'json' not in call_args[1]
        assert 'data' not in call_args[1]
        mock_response.raise_for_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_head_method(self, adapter):
        """Test HEAD request implementation."""
        mock_response = Mock()
        mock_response.headers = {"Content-Length": "1234", "Content-Type": "application/json"}
        adapter.session.head.return_value = mock_response
        
        params = HttpActionParams(url="https://api.example.com/resource")
        
        result = await adapter.head(params)
        
        assert result == {"Content-Length": "1234", "Content-Type": "application/json"}
        
        # HEAD should not include data
        call_args = adapter.session.head.call_args
        assert 'json' not in call_args[1]
        assert 'data' not in call_args[1]
        mock_response.raise_for_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_options_method(self, adapter):
        """Test OPTIONS request implementation."""
        mock_response = Mock()
        mock_response.headers = {"Allow": "GET, POST, PUT, DELETE"}
        adapter.session.options.return_value = mock_response
        
        params = HttpActionParams(url="https://api.example.com/resource")
        
        result = await adapter.options(params)
        
        assert result == {"Allow": "GET, POST, PUT, DELETE"}
        
        # OPTIONS should not include data
        call_args = adapter.session.options.call_args
        assert 'json' not in call_args[1]
        assert 'data' not in call_args[1]
        mock_response.raise_for_status.assert_called_once()


class TestRequestsAdapterErrorHandling:
    """Test RequestsAdapter error handling."""
    
    @pytest.fixture
    def adapter(self):
        """Create initialized adapter for testing."""
        adapter = RequestsAdapter()
        adapter.session = Mock()
        adapter.initialized = True
        return adapter
    
    @pytest.mark.asyncio
    async def test_not_initialized_error(self):
        """Test error when adapter not initialized."""
        adapter = RequestsAdapter()
        params = HttpActionParams(url="https://example.com")
        
        with pytest.raises(RuntimeError, match="RequestsAdapter not initialized"):
            await adapter.get(params)
    
    @pytest.mark.asyncio
    async def test_http_error_propagation(self, adapter):
        """Test HTTP error propagation."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
        adapter.session.get.return_value = mock_response
        
        params = HttpActionParams(url="https://api.example.com/notfound")
        
        with pytest.raises(HTTPError, match="404 Not Found"):
            await adapter.get(params)
    
    @pytest.mark.asyncio
    async def test_connection_error_propagation(self, adapter):
        """Test connection error propagation."""
        adapter.session.get.side_effect = ConnectionError("Connection failed")
        
        params = HttpActionParams(url="https://unreachable.example.com")
        
        with pytest.raises(ConnectionError, match="Connection failed"):
            await adapter.get(params)
    
    @pytest.mark.asyncio
    async def test_timeout_error_propagation(self, adapter):
        """Test timeout error propagation."""
        adapter.session.post.side_effect = Timeout("Request timed out")
        
        params = HttpActionParams(url="https://slow.example.com")
        
        with pytest.raises(Timeout, match="Request timed out"):
            await adapter.post(params)
    
    @pytest.mark.asyncio
    async def test_general_request_exception(self, adapter):
        """Test general request exception propagation."""
        adapter.session.put.side_effect = RequestException("Generic error")
        
        params = HttpActionParams(url="https://error.example.com")
        
        with pytest.raises(RequestException, match="Generic error"):
            await adapter.put(params)


class TestRequestsAdapterIntegration:
    """Test RequestsAdapter integration scenarios."""
    
    @pytest.mark.asyncio
    @patch('requests.Session')
    async def test_full_lifecycle_integration(self, mock_session_class):
        """Test complete adapter lifecycle."""
        mock_session = Mock()
        mock_session.headers = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {"success": True}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        adapter = RequestsAdapter(timeout=15.0, user_agent="Integration/1.0")
        
        # Initialize
        await adapter.initialize()
        assert adapter.initialized
        
        # Make request
        params = HttpActionParams(url="https://api.example.com/test")
        result = await adapter.get(params)
        assert result == {"success": True}
        
        # Cleanup
        await adapter.close()
        assert not adapter.initialized
        
        # Verify session lifecycle
        mock_session_class.assert_called_once()
        mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_multiple_requests_same_session(self):
        """Test multiple requests using same session."""
        adapter = RequestsAdapter()
        adapter.session = Mock()
        adapter.initialized = True
        
        # Mock different responses
        get_response = Mock()
        get_response.json.return_value = {"method": "GET"}
        post_response = Mock()
        post_response.json.return_value = {"method": "POST"}
        
        adapter.session.get.return_value = get_response
        adapter.session.post.return_value = post_response
        
        # Multiple requests
        get_params = HttpActionParams(url="https://api.example.com/get")
        post_params = HttpActionParams(url="https://api.example.com/post", data={"test": "data"})
        
        get_result = await adapter.get(get_params)
        post_result = await adapter.post(post_params)
        
        assert get_result == {"method": "GET"}
        assert post_result == {"method": "POST"}
        
        # Should use same session
        assert adapter.session.get.call_count == 1
        assert adapter.session.post.call_count == 1
    
    def test_adapter_inheritance(self):
        """Test RequestsAdapter inheritance from BaseHttpAdapter."""
        from lamia.adapters.web.http.base import BaseHttpAdapter
        
        adapter = RequestsAdapter()
        assert isinstance(adapter, BaseHttpAdapter)
    
    @pytest.mark.asyncio
    async def test_complex_request_scenario(self):
        """Test complex request with all parameters."""
        adapter = RequestsAdapter()
        adapter.session = Mock()
        adapter.initialized = True
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success", 
            "data": {"processed": True}
        }
        adapter.session.post.return_value = mock_response
        
        params = HttpActionParams(
            url="https://api.example.com/complex",
            headers={
                "Authorization": "Bearer token123",
                "Content-Type": "application/json",
                "X-Custom-Header": "value"
            },
            params={"version": "v1", "format": "json"},
            data={
                "user_id": 12345,
                "action": "update",
                "metadata": {"source": "test", "priority": "high"}
            }
        )
        
        result = await adapter.post(params)
        
        assert result == {"status": "success", "data": {"processed": True}}
        
        # Verify call structure
        call_args = adapter.session.post.call_args
        assert call_args[0][0] == "https://api.example.com/complex"
        assert call_args[1]['json'] == params.data
        assert call_args[1]['headers']['Authorization'] == "Bearer token123"
        assert call_args[1]['params'] == {"version": "v1", "format": "json"}


class TestRequestsAdapterConfiguration:
    """Test RequestsAdapter configuration options."""
    
    def test_custom_timeout_configuration(self):
        """Test custom timeout configuration."""
        adapter = RequestsAdapter(timeout=120.0)
        
        params = HttpActionParams(url="https://example.com")
        kwargs = adapter._prepare_request_kwargs(params)
        
        assert kwargs['timeout'] == 120.0
    
    def test_custom_user_agent_configuration(self):
        """Test custom user agent configuration."""
        adapter = RequestsAdapter(user_agent="MyApp/2.0 (Custom)")
        assert adapter.user_agent == "MyApp/2.0 (Custom)"
    
    @pytest.mark.asyncio
    @patch('requests.Session')
    async def test_user_agent_header_setting(self, mock_session_class):
        """Test that user agent is properly set in session headers."""
        mock_session = Mock()
        mock_session.headers = Mock()
        mock_session_class.return_value = mock_session
        
        adapter = RequestsAdapter(user_agent="TestAgent/1.0")
        await adapter.initialize()
        
        mock_session.headers.update.assert_called_once_with({
            'User-Agent': 'TestAgent/1.0'
        })
    
    def test_default_configuration_values(self):
        """Test default configuration values are sensible."""
        adapter = RequestsAdapter()
        
        # Default timeout should be reasonable
        assert adapter.default_timeout == 30.0
        
        # Default user agent should identify Lamia
        assert "Lamia" in adapter.user_agent
        assert "1.0" in adapter.user_agent