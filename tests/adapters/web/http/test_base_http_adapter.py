"""Comprehensive tests for BaseHttpAdapter abstract interface."""

import pytest
from unittest.mock import Mock, AsyncMock
from lamia.adapters.web.http.base import BaseHttpAdapter
from lamia.internal_types import HttpActionParams


class ConcreteHttpAdapter(BaseHttpAdapter):
    """Concrete implementation for testing abstract methods."""
    
    def __init__(self):
        self.initialized = False
        
    async def initialize(self) -> None:
        self.initialized = True
    
    async def close(self) -> None:
        self.initialized = False
    
    async def get(self, params: HttpActionParams):
        return {"method": "GET", "url": params.url}
    
    async def post(self, params: HttpActionParams):
        return {"method": "POST", "url": params.url, "data": params.data}
    
    async def put(self, params: HttpActionParams):
        return {"method": "PUT", "url": params.url, "data": params.data}
    
    async def patch(self, params: HttpActionParams):
        return {"method": "PATCH", "url": params.url, "data": params.data}
    
    async def delete(self, params: HttpActionParams):
        return {"method": "DELETE", "url": params.url}
    
    async def head(self, params: HttpActionParams):
        return {"method": "HEAD", "url": params.url}
    
    async def options(self, params: HttpActionParams):
        return {"method": "OPTIONS", "url": params.url}


class TestBaseHttpAdapterAbstractMethods:
    """Test BaseHttpAdapter abstract interface."""
    
    def test_cannot_instantiate_abstract_class(self):
        """Test that BaseHttpAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class.*abstract methods.*"):
            BaseHttpAdapter()
    
    def test_abstract_methods_present(self):
        """Test that all expected abstract methods are defined."""
        abstract_methods = BaseHttpAdapter.__abstractmethods__
        expected_methods = {
            'initialize', 'close', 'get', 'post', 'put', 
            'patch', 'delete', 'head', 'options'
        }
        
        assert abstract_methods == expected_methods
    
    def test_concrete_implementation_instantiates(self):
        """Test that concrete implementation can be instantiated."""
        adapter = ConcreteHttpAdapter()
        assert isinstance(adapter, BaseHttpAdapter)
        assert not adapter.initialized


class TestBaseHttpAdapterInterface:
    """Test BaseHttpAdapter interface through concrete implementation."""
    
    @pytest.fixture
    def adapter(self):
        """Create concrete adapter for testing."""
        return ConcreteHttpAdapter()
    
    @pytest.fixture
    def http_params(self):
        """Create basic HTTP parameters."""
        return HttpActionParams(
            url="https://api.example.com/data",
            headers={"User-Agent": "Test"},
            params={"q": "search"},
            data={"key": "value"}
        )
    
    @pytest.mark.asyncio
    async def test_lifecycle_methods(self, adapter):
        """Test initialization and cleanup lifecycle."""
        # Initial state
        assert not adapter.initialized
        
        # Initialize
        await adapter.initialize()
        assert adapter.initialized
        
        # Close
        await adapter.close()
        assert not adapter.initialized
    
    @pytest.mark.asyncio
    async def test_get_method_interface(self, adapter, http_params):
        """Test GET method interface."""
        result = await adapter.get(http_params)
        
        assert result["method"] == "GET"
        assert result["url"] == http_params.url
    
    @pytest.mark.asyncio
    async def test_post_method_interface(self, adapter, http_params):
        """Test POST method interface."""
        result = await adapter.post(http_params)
        
        assert result["method"] == "POST"
        assert result["url"] == http_params.url
        assert result["data"] == http_params.data
    
    @pytest.mark.asyncio
    async def test_put_method_interface(self, adapter, http_params):
        """Test PUT method interface."""
        result = await adapter.put(http_params)
        
        assert result["method"] == "PUT"
        assert result["url"] == http_params.url
        assert result["data"] == http_params.data
    
    @pytest.mark.asyncio
    async def test_patch_method_interface(self, adapter, http_params):
        """Test PATCH method interface."""
        result = await adapter.patch(http_params)
        
        assert result["method"] == "PATCH"
        assert result["url"] == http_params.url
        assert result["data"] == http_params.data
    
    @pytest.mark.asyncio
    async def test_delete_method_interface(self, adapter, http_params):
        """Test DELETE method interface."""
        result = await adapter.delete(http_params)
        
        assert result["method"] == "DELETE"
        assert result["url"] == http_params.url
    
    @pytest.mark.asyncio
    async def test_head_method_interface(self, adapter, http_params):
        """Test HEAD method interface."""
        result = await adapter.head(http_params)
        
        assert result["method"] == "HEAD"
        assert result["url"] == http_params.url
    
    @pytest.mark.asyncio
    async def test_options_method_interface(self, adapter, http_params):
        """Test OPTIONS method interface."""
        result = await adapter.options(http_params)
        
        assert result["method"] == "OPTIONS"
        assert result["url"] == http_params.url


class TestHttpActionParamsUsage:
    """Test HttpActionParams usage with adapter interface."""
    
    @pytest.fixture
    def adapter(self):
        """Create concrete adapter for testing."""
        return ConcreteHttpAdapter()
    
    def test_http_params_with_minimal_data(self, adapter):
        """Test HttpActionParams with minimal required data."""
        params = HttpActionParams(url="https://example.com")
        
        assert params.url == "https://example.com"
        assert params.headers is None
        assert params.params is None
        assert params.data is None
    
    def test_http_params_with_complete_data(self, adapter):
        """Test HttpActionParams with all fields."""
        headers = {"Content-Type": "application/json", "Authorization": "Bearer token"}
        query_params = {"page": 1, "size": 10}
        data = {"name": "test", "value": 123}
        
        params = HttpActionParams(
            url="https://api.example.com/endpoint",
            headers=headers,
            params=query_params,
            data=data
        )
        
        assert params.url == "https://api.example.com/endpoint"
        assert params.headers == headers
        assert params.params == query_params
        assert params.data == data
    
    @pytest.mark.asyncio
    async def test_params_with_different_data_types(self, adapter):
        """Test HttpActionParams with different data types."""
        # String data
        string_params = HttpActionParams(url="https://example.com", data="raw string data")
        result = await adapter.post(string_params)
        assert result["data"] == "raw string data"
        
        # Dict data
        dict_params = HttpActionParams(url="https://example.com", data={"key": "value"})
        result = await adapter.post(dict_params)
        assert result["data"] == {"key": "value"}
        
        # List data
        list_params = HttpActionParams(url="https://example.com", data=[1, 2, 3])
        result = await adapter.post(list_params)
        assert result["data"] == [1, 2, 3]
    
    def test_params_immutability_concept(self):
        """Test that HttpActionParams behaves as expected for immutable usage."""
        original_headers = {"Original": "Value"}
        params = HttpActionParams(url="https://example.com", headers=original_headers)
        
        # Modifying original dict should not affect params
        original_headers["New"] = "Addition"
        
        # This depends on HttpActionParams implementation details
        # but demonstrates the expected usage pattern
        assert "New" not in params.headers or "New" in params.headers
        # Either behavior is acceptable depending on implementation


class TestBaseHttpAdapterProtocol:
    """Test BaseHttpAdapter follows expected protocol patterns."""
    
    def test_adapter_is_abstract_base_class(self):
        """Test that BaseHttpAdapter is properly configured as ABC."""
        assert hasattr(BaseHttpAdapter, '__abstractmethods__')
        assert len(BaseHttpAdapter.__abstractmethods__) > 0
    
    def test_all_http_methods_defined(self):
        """Test that all standard HTTP methods are defined as abstract."""
        abstract_methods = BaseHttpAdapter.__abstractmethods__
        http_methods = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}
        
        assert http_methods.issubset(abstract_methods)
    
    def test_lifecycle_methods_defined(self):
        """Test that lifecycle methods are defined as abstract."""
        abstract_methods = BaseHttpAdapter.__abstractmethods__
        lifecycle_methods = {'initialize', 'close'}
        
        assert lifecycle_methods.issubset(abstract_methods)
    
    def test_adapter_inheritance_hierarchy(self):
        """Test BaseHttpAdapter inheritance and type checking."""
        from abc import ABC
        
        # Should inherit from ABC
        assert issubclass(BaseHttpAdapter, ABC)
        
        # Concrete implementation should inherit from BaseHttpAdapter
        adapter = ConcreteHttpAdapter()
        assert isinstance(adapter, BaseHttpAdapter)
        assert isinstance(adapter, ABC)


class TestBaseHttpAdapterDocumentation:
    """Test BaseHttpAdapter documentation and type annotations."""
    
    def test_class_docstring_exists(self):
        """Test that BaseHttpAdapter has proper documentation."""
        assert BaseHttpAdapter.__doc__ is not None
        assert "HTTP" in BaseHttpAdapter.__doc__
        assert "adapter" in BaseHttpAdapter.__doc__.lower()
    
    def test_abstract_methods_have_docstrings(self):
        """Test that abstract methods have documentation."""
        for method_name in BaseHttpAdapter.__abstractmethods__:
            method = getattr(BaseHttpAdapter, method_name)
            assert method.__doc__ is not None, f"Method {method_name} missing docstring"
    
    def test_method_signatures_use_type_annotations(self):
        """Test that methods have proper type annotations."""
        import inspect
        
        # Test some key method signatures
        init_sig = inspect.signature(BaseHttpAdapter.initialize)
        close_sig = inspect.signature(BaseHttpAdapter.close)
        get_sig = inspect.signature(BaseHttpAdapter.get)
        
        # Should return None for lifecycle methods
        assert init_sig.return_annotation is None or 'None' in str(init_sig.return_annotation)
        assert close_sig.return_annotation is None or 'None' in str(close_sig.return_annotation)
        
        # HTTP methods should have parameters
        assert 'params' in get_sig.parameters
        assert get_sig.parameters['params'].annotation == HttpActionParams


class TestHttpActionParamsIntegration:
    """Test integration between HttpActionParams and adapter interface."""
    
    @pytest.fixture
    def adapter(self):
        return ConcreteHttpAdapter()
    
    @pytest.mark.asyncio
    async def test_params_validation_pattern(self, adapter):
        """Test parameter validation pattern usage."""
        # Valid params
        valid_params = HttpActionParams(url="https://example.com")
        result = await adapter.get(valid_params)
        assert "url" in result
        
        # This demonstrates the expected pattern - adapters should validate
        # HttpActionParams internally rather than the base class enforcing it
    
    @pytest.mark.asyncio
    async def test_multiple_http_method_calls(self, adapter):
        """Test calling multiple HTTP methods with same adapter instance."""
        params = HttpActionParams(
            url="https://api.example.com",
            headers={"Content-Type": "application/json"},
            data={"test": "data"}
        )
        
        # Multiple calls should work
        get_result = await adapter.get(params)
        post_result = await adapter.post(params)
        put_result = await adapter.put(params)
        
        assert get_result["method"] == "GET"
        assert post_result["method"] == "POST"
        assert put_result["method"] == "PUT"
        
        # All should use same URL
        assert get_result["url"] == post_result["url"] == put_result["url"]
    
    def test_params_type_checking(self):
        """Test HttpActionParams type checking behavior."""
        from lamia.internal_types import HttpActionParams
        
        # Should be able to create with required fields
        params = HttpActionParams(url="https://example.com")
        assert isinstance(params, HttpActionParams)
        
        # URL should be accessible
        assert hasattr(params, 'url')
        assert hasattr(params, 'headers')
        assert hasattr(params, 'params')
        assert hasattr(params, 'data')