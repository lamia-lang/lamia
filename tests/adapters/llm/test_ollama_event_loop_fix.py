"""Test for Ollama adapter event loop closed bug fix."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from lamia.adapters.llm.local.ollama_adapter import OllamaAdapter
from lamia import LLMModel


@pytest.fixture
def mock_ollama_running():
    """Mock Ollama service as running."""
    with patch.object(OllamaAdapter, '_is_ollama_running', return_value=True):
        with patch.object(OllamaAdapter, '_start_ollama_service', return_value=True):
            yield


@pytest.fixture
def ollama_adapter(mock_ollama_running):
    """Create OllamaAdapter instance with mocked service."""
    adapter = OllamaAdapter()
    return adapter


@pytest.fixture
def test_model():
    """Create a test LLM model."""
    return LLMModel(
        name="ollama:llama3.2",
        temperature=0.2,
        max_tokens=1000,
        top_p=0.9,
        top_k=40,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        seed=None
    )


@pytest.mark.asyncio
async def test_event_loop_closed_error_converted_to_connection_error(ollama_adapter, test_model):
    """Test that 'Event loop is closed' RuntimeError is converted to ConnectionError."""
    
    # Mock model pulling
    with patch.object(ollama_adapter, '_ensure_ollama_model_pulled', return_value=True):
        # Create a mock session
        mock_session = AsyncMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        
        # Mock post() to raise "Event loop is closed" error
        async def raise_event_loop_error(*args, **kwargs):
            raise RuntimeError("Event loop is closed")
        
        mock_session.post = Mock(side_effect=raise_event_loop_error)
        
        ollama_adapter.session = mock_session
        
        # Should raise ConnectionError (not RuntimeError)
        with pytest.raises(ConnectionError) as exc_info:
            await ollama_adapter.generate("test", test_model)
        
        # Verify error message
        assert "Event loop closed during Ollama request" in str(exc_info.value)
        
        # Verify session was set to None
        assert ollama_adapter.session is None


@pytest.mark.asyncio
async def test_other_runtime_errors_not_converted(ollama_adapter, test_model):
    """Test that other RuntimeErrors are not converted to ConnectionError."""
    
    # Mock model pulling
    with patch.object(ollama_adapter, '_ensure_ollama_model_pulled', return_value=True):
        # Create a mock session
        mock_session = AsyncMock()
        mock_session.closed = False
        
        # Mock post() to raise a different RuntimeError
        async def raise_other_error(*args, **kwargs):
            raise RuntimeError("Some other error")
        
        mock_session.post = Mock(side_effect=raise_other_error)
        
        ollama_adapter.session = mock_session
        
        # Should raise the original RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await ollama_adapter.generate("test", test_model)
        
        assert "Some other error" in str(exc_info.value)
        assert "Event loop" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_session_recreation_on_closed_event_loop(ollama_adapter):
    """Test that _ensure_session recreates session when event loop is closed."""
    
    # Create a mock session
    mock_old_session = AsyncMock()
    mock_old_session.closed = False
    mock_old_session.close = AsyncMock()
    
    ollama_adapter.session = mock_old_session
    
    # Mock event loop as closed
    mock_loop = Mock()
    mock_loop.is_closed.return_value = True
    
    with patch('asyncio.get_running_loop', return_value=mock_loop):
        with patch('aiohttp.ClientSession') as mock_client_session:
            mock_new_session = AsyncMock()
            mock_client_session.return_value = mock_new_session
            
            # Call _ensure_session
            result = await ollama_adapter._ensure_session()
            
            # Should have closed old session and created new one
            mock_old_session.close.assert_called_once()
            mock_client_session.assert_called_once()
            assert result == mock_new_session
            assert ollama_adapter.session == mock_new_session


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
