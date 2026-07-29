import pytest
from unittest.mock import Mock, AsyncMock, patch
import aiohttp
from lamia.adapters.llm.local.ollama_adapter import OllamaAdapter


def test_import_ollama_adapter():
    assert OllamaAdapter is not None


class TestOllamaAdapterClassMethods:
    """Test OllamaAdapter class-level methods."""

    def test_name(self):
        assert OllamaAdapter.name() == "ollama"

    def test_is_remote(self):
        assert OllamaAdapter.is_remote() is False

    def test_env_var_names_empty(self):
        assert OllamaAdapter.env_var_names() == []


class TestOllamaAdapterModels:
    """Test OllamaAdapter models classmethod."""

    @pytest.mark.asyncio
    async def test_list_models_success(self):
        """Test fetching installed models from Ollama."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "models": [
                {"name": "llama3:latest", "size": 4000000000},
                {"name": "mistral:latest", "size": 3500000000},
            ]
        })

        class MockGetContext:
            def __init__(self, resp):
                self.resp = resp
            async def __aenter__(self):
                return self.resp
            async def __aexit__(self, *a):
                return None

        mock_session = Mock()
        mock_session.get = Mock(return_value=MockGetContext(mock_response))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            models = await OllamaAdapter.models()

        assert len(models) == 2
        assert models[0]["id"] == "llama3:latest"
        assert models[0]["size"] == 4000000000
        assert models[1]["id"] == "mistral:latest"

    @pytest.mark.asyncio
    async def test_list_models_empty(self):
        """Test models returns empty when no models installed."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"models": []})

        class MockGetContext:
            def __init__(self, resp):
                self.resp = resp
            async def __aenter__(self):
                return self.resp
            async def __aexit__(self, *a):
                return None

        mock_session = Mock()
        mock_session.get = Mock(return_value=MockGetContext(mock_response))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            models = await OllamaAdapter.models()

        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_server_not_running(self):
        """Test models returns empty when Ollama is not running."""
        mock_session = Mock()
        mock_session.get = Mock(side_effect=aiohttp.ClientError("Connection refused"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            models = await OllamaAdapter.models()

        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_non_200_status(self):
        """Test models returns empty on non-200 status."""
        mock_response = AsyncMock()
        mock_response.status = 500

        class MockGetContext:
            def __init__(self, resp):
                self.resp = resp
            async def __aenter__(self):
                return self.resp
            async def __aexit__(self, *a):
                return None

        mock_session = Mock()
        mock_session.get = Mock(return_value=MockGetContext(mock_response))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            models = await OllamaAdapter.models()

        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_custom_base_url(self):
        """Test models with custom base URL."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "models": [{"name": "phi3:latest"}]
        })

        class MockGetContext:
            def __init__(self, resp):
                self.resp = resp
            async def __aenter__(self):
                return self.resp
            async def __aexit__(self, *a):
                return None

        mock_session = Mock()
        mock_session.get = Mock(return_value=MockGetContext(mock_response))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            models = await OllamaAdapter.models(base_url="http://192.168.1.10:11434")

        assert len(models) == 1
        mock_session.get.assert_called_once_with("http://192.168.1.10:11434/api/tags")


class TestOllamaAdapterGenerate:
    """Test OllamaAdapter generate error handling."""

    @pytest.mark.asyncio
    async def test_generate_raises_permanent_error_on_404(self):
        """Test that 4xx Ollama errors raise ExternalOperationPermanentError."""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="model not found")

        class MockPostContext:
            def __init__(self, resp):
                self.resp = resp
            async def __aenter__(self):
                return self.resp
            async def __aexit__(self, *a):
                return None

        mock_session = Mock()
        mock_session.post = Mock(return_value=MockPostContext(mock_response))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch.object(OllamaAdapter, '_start_ollama_service', return_value=None):
            with patch.object(OllamaAdapter, '_ensure_ollama_model_pulled', return_value=True):
                with patch('aiohttp.ClientSession', return_value=mock_session):
                    adapter = OllamaAdapter()
                    mock_model = Mock()
                    mock_model.get_model_name_without_provider.return_value = "missing-model"
                    mock_model.name = "ollama:missing-model"

                    from lamia.errors import ExternalOperationPermanentError
                    with pytest.raises(ExternalOperationPermanentError, match="Ollama API error"):
                        await adapter.generate("Test prompt", mock_model)

    @pytest.mark.asyncio
    async def test_generate_raises_transient_error_on_529(self):
        """Test that 5xx Ollama errors raise ExternalOperationTransientError."""
        mock_response = AsyncMock()
        mock_response.status = 529
        mock_response.text = AsyncMock(return_value="overloaded")

        class MockPostContext:
            def __init__(self, resp):
                self.resp = resp
            async def __aenter__(self):
                return self.resp
            async def __aexit__(self, *a):
                return None

        mock_session = Mock()
        mock_session.post = Mock(return_value=MockPostContext(mock_response))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch.object(OllamaAdapter, '_start_ollama_service', return_value=None):
            with patch.object(OllamaAdapter, '_ensure_ollama_model_pulled', return_value=True):
                with patch('aiohttp.ClientSession', return_value=mock_session):
                    adapter = OllamaAdapter()
                    mock_model = Mock()
                    mock_model.get_model_name_without_provider.return_value = "llama3"
                    mock_model.name = "ollama:llama3"

                    from lamia.errors import ExternalOperationTransientError
                    with pytest.raises(ExternalOperationTransientError, match="Ollama API error"):
                        await adapter.generate("Test prompt", mock_model)