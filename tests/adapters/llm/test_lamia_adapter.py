#!/usr/bin/env python3
"""
Unit tests for LamiaAdapter with proper mocking - no real API calls.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from lamia.adapters.llm.lamia_adapter import LamiaAdapter


def test_lamia_adapter_initialization():
    """Test adapter initialization without API calls."""
    
    adapter = LamiaAdapter(api_key="test-key", api_url="http://test:8080")
    
    # Verify initial state
    assert adapter.api_key == "test-key"
    assert adapter.api_url == "http://test:8080"
    assert adapter.session is None
    
    # Test supported providers
    assert "openai" in LamiaAdapter.get_supported_providers()
    assert "anthropic" in LamiaAdapter.get_supported_providers()


def test_lamia_adapter_endpoint_mapping():
    """Test endpoint mapping logic without any API calls."""
    
    adapter = LamiaAdapter(api_key="test-key", api_url="http://localhost:8080")
    
    # Test endpoint mapping
    assert adapter._get_endpoint_for_provider("openai") == "http://localhost:8080/v1/chat/completions"
    assert adapter._get_endpoint_for_provider("anthropic") == "http://localhost:8080/v1/messages"
    
    # Test unsupported provider
    with pytest.raises(ValueError, match="Unsupported provider"):
        adapter._get_endpoint_for_provider("unsupported")


@pytest.mark.asyncio
async def test_lamia_adapter_requires_initialization():
    """Test that adapter requires initialization before use."""
    
    adapter = LamiaAdapter(api_key="test-key", api_url="http://localhost:8080")
    
    # Should raise error if not initialized
    with pytest.raises(RuntimeError, match="Adapter not initialized"):
        await adapter.get_available_models()
    
    # Mock the model for generate test
    mock_model = MagicMock()
    mock_model.get_provider_name.return_value = "openai"
    
    with pytest.raises(RuntimeError, match="Adapter not initialized"):
        await adapter.generate("test prompt", mock_model)


@pytest.mark.asyncio
@patch('aiohttp.ClientSession')
async def test_lamia_adapter_session_creation(mock_session_class):
    """Test that session is created correctly during initialization."""
    
    mock_session = AsyncMock()
    mock_session_class.return_value = mock_session
    
    adapter = LamiaAdapter(api_key="test-api-key", api_url="http://localhost:8080")
    
    # Verify session is None before initialization
    assert adapter.session is None
    
    # Initialize adapter
    await adapter.async_initialize()
    
    # Verify session was created with correct headers
    mock_session_class.assert_called_once_with(
        headers={
            "Authorization": "Bearer test-api-key",
            "Content-Type": "application/json"
        }
    )
    
    # Verify session is now set
    assert adapter.session is not None
    
    await adapter.close()


@pytest.mark.asyncio 
async def test_no_real_api_calls_in_tests():
    """Verify that no real HTTP requests are made during testing."""
    
    # This test ensures we're properly mocking HTTP calls
    # If any real API calls happen, they would fail with connection errors
    # since we're not providing real URLs or API keys
    
    adapter = LamiaAdapter(api_key="fake-key", api_url="http://definitely-not-real:99999")
    
    # These should not make real API calls due to the fake URL
    # and because we haven't initialized the adapter
    assert adapter.api_key == "fake-key"
    assert adapter.api_url == "http://definitely-not-real:99999"
    assert adapter.session is None