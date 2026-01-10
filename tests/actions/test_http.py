"""Tests for HTTP actions module."""

import pytest
from lamia.actions.http import HttpActions
from lamia.internal_types import HttpAction, HttpActionType, HttpActionParams


class TestHttpActions:
    """Test HttpActions class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.http_actions = HttpActions()
    
    def test_get(self):
        """Test GET request action creation."""
        # Basic GET request
        result = self.http_actions.get("https://api.example.com/users")
        assert isinstance(result, HttpAction)
        assert result.action == HttpActionType.GET
        assert result.params.url == "https://api.example.com/users"
        assert result.params.headers is None
        assert result.params.params is None
        
        # GET with headers
        headers = {"Authorization": "Bearer token123"}
        result = self.http_actions.get("https://api.example.com/users", headers=headers)
        assert result.params.headers == headers
        
        # GET with query parameters
        params = {"page": 1, "limit": 10}
        result = self.http_actions.get("https://api.example.com/users", params=params)
        assert result.params.params == params
        
        # GET with both headers and params
        result = self.http_actions.get("https://api.example.com/users", headers=headers, params=params)
        assert result.params.headers == headers
        assert result.params.params == params
    
    def test_post(self):
        """Test POST request action creation."""
        # Basic POST request
        result = self.http_actions.post("https://api.example.com/users")
        assert isinstance(result, HttpAction)
        assert result.action == HttpActionType.POST
        assert result.params.url == "https://api.example.com/users"
        assert result.params.data is None
        assert result.params.headers is None
        
        # POST with JSON data
        data = {"name": "John Doe", "email": "john@example.com"}
        result = self.http_actions.post("https://api.example.com/users", data=data)
        assert result.params.data == data
        
        # POST with string data
        data = "form=data&key=value"
        result = self.http_actions.post("https://api.example.com/users", data=data)
        assert result.params.data == data
        
        # POST with headers
        headers = {"Content-Type": "application/json"}
        result = self.http_actions.post("https://api.example.com/users", headers=headers)
        assert result.params.headers == headers
    
    def test_put(self):
        """Test PUT request action creation."""
        # Basic PUT request
        result = self.http_actions.put("https://api.example.com/users/123")
        assert isinstance(result, HttpAction)
        assert result.action == HttpActionType.PUT
        assert result.params.url == "https://api.example.com/users/123"
        
        # PUT with data
        data = {"name": "Jane Doe"}
        result = self.http_actions.put("https://api.example.com/users/123", data=data)
        assert result.params.data == data
        
        # PUT with headers
        headers = {"Content-Type": "application/json"}
        result = self.http_actions.put("https://api.example.com/users/123", headers=headers)
        assert result.params.headers == headers
    
    def test_patch(self):
        """Test PATCH request action creation."""
        # Basic PATCH request
        result = self.http_actions.patch("https://api.example.com/users/123")
        assert isinstance(result, HttpAction)
        assert result.action == HttpActionType.PATCH
        assert result.params.url == "https://api.example.com/users/123"
        
        # PATCH with partial data
        data = {"email": "newemail@example.com"}
        result = self.http_actions.patch("https://api.example.com/users/123", data=data)
        assert result.params.data == data
        
        # PATCH with headers
        headers = {"Content-Type": "application/json"}
        result = self.http_actions.patch("https://api.example.com/users/123", headers=headers)
        assert result.params.headers == headers
    
    def test_delete(self):
        """Test DELETE request action creation."""
        # Basic DELETE request
        result = self.http_actions.delete("https://api.example.com/users/123")
        assert isinstance(result, HttpAction)
        assert result.action == HttpActionType.DELETE
        assert result.params.url == "https://api.example.com/users/123"
        assert result.params.headers is None
        
        # DELETE with headers
        headers = {"Authorization": "Bearer token123"}
        result = self.http_actions.delete("https://api.example.com/users/123", headers=headers)
        assert result.params.headers == headers
    
    def test_head(self):
        """Test HEAD request action creation."""
        # Basic HEAD request
        result = self.http_actions.head("https://api.example.com/users/123")
        assert isinstance(result, HttpAction)
        assert result.action == HttpActionType.HEAD
        assert result.params.url == "https://api.example.com/users/123"
        assert result.params.headers is None
        
        # HEAD with headers
        headers = {"Authorization": "Bearer token123"}
        result = self.http_actions.head("https://api.example.com/users/123", headers=headers)
        assert result.params.headers == headers
    
    def test_options(self):
        """Test OPTIONS request action creation."""
        # Basic OPTIONS request
        result = self.http_actions.options("https://api.example.com/users")
        assert isinstance(result, HttpAction)
        assert result.action == HttpActionType.OPTIONS
        assert result.params.url == "https://api.example.com/users"
        assert result.params.headers is None
        
        # OPTIONS with headers
        headers = {"Access-Control-Request-Method": "POST"}
        result = self.http_actions.options("https://api.example.com/users", headers=headers)
        assert result.params.headers == headers
    
    def test_url_validation(self):
        """Test that URLs are properly stored."""
        urls = [
            "http://example.com",
            "https://api.example.com/v1/users",
            "https://localhost:8080/api/test",
            "https://sub.domain.com/path/to/resource?param=value"
        ]
        
        for url in urls:
            result = self.http_actions.get(url)
            assert result.params.url == url
    
    def test_headers_handling(self):
        """Test various header configurations."""
        headers_configs = [
            {"Content-Type": "application/json"},
            {"Authorization": "Bearer token", "User-Agent": "Test Agent"},
            {"X-Custom-Header": "value", "Accept": "application/json"},
            {}  # Empty headers
        ]
        
        for headers in headers_configs:
            if headers:
                result = self.http_actions.post("https://example.com", headers=headers)
                assert result.params.headers == headers
            else:
                result = self.http_actions.post("https://example.com", headers=None)
                assert result.params.headers is None
    
    def test_data_types(self):
        """Test different data types for POST/PUT/PATCH."""
        data_configs = [
            {"key": "value", "nested": {"inner": "data"}},  # Dict
            "string_data",  # String
            42,  # Number
            ["list", "data"],  # List
            None  # None
        ]
        
        for data in data_configs:
            result = self.http_actions.post("https://example.com", data=data)
            assert result.params.data == data


class TestHttpActionTypes:
    """Test that all HTTP action types are used correctly."""
    
    def test_all_action_types_covered(self):
        """Test that all HttpActionType enum values have corresponding methods."""
        http_actions = HttpActions()
        
        # Map of method names to their expected action types
        method_action_map = {
            'get': HttpActionType.GET,
            'post': HttpActionType.POST,
            'put': HttpActionType.PUT,
            'patch': HttpActionType.PATCH,
            'delete': HttpActionType.DELETE,
            'head': HttpActionType.HEAD,
            'options': HttpActionType.OPTIONS,
        }
        
        for method_name, expected_action in method_action_map.items():
            method = getattr(http_actions, method_name)
            result = method("https://example.com")
            assert result.action == expected_action
    
    def test_action_params_structure(self):
        """Test that HttpActionParams are properly structured."""
        http_actions = HttpActions()
        
        result = http_actions.get("https://example.com")
        assert hasattr(result.params, 'url')
        assert hasattr(result.params, 'headers')
        assert hasattr(result.params, 'params')
        
        # For methods that support data
        result = http_actions.post("https://example.com")
        assert hasattr(result.params, 'data')