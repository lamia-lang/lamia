import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from lamia.adapters.llm.openai_adapter import OpenAIAdapter

@pytest_asyncio.fixture
def openai_client_mock():
    mock = MagicMock()
    mock.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(content="OpenAI response"))],
        usage=MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    ))
    return mock

@pytest_asyncio.fixture
def aiohttp_session_mock():
    mock_session = MagicMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "choices": [{"message": {"content": "HTTP response"}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 4, "total_tokens": 11}
    })
    mock_session.post = AsyncMock(return_value=mock_response)
    return mock_session

@pytest.mark.asyncio
@patch("lamia.adapters.llm.openai_adapter.openai.AsyncOpenAI")
async def test_initialize_sdk_sets_client(mock_async_openai, openai_client_mock):
    mock_async_openai.return_value = openai_client_mock
    adapter = OpenAIAdapter(api_key="sk-test", model="gpt-3.5-turbo")
    await adapter.initialize()
    assert adapter.client is openai_client_mock
    mock_async_openai.assert_called_once_with(api_key="sk-test")

@pytest.mark.asyncio
@patch("lamia.adapters.llm.openai_adapter.aiohttp.ClientSession")
async def test_initialize_http_sets_session(mock_client_session, aiohttp_session_mock):
    adapter = OpenAIAdapter(api_key="sk-test", model="gpt-3.5-turbo")
    adapter._use_sdk = False
    mock_client_session.return_value = aiohttp_session_mock
    await adapter.initialize()
    assert adapter.session is aiohttp_session_mock
    mock_client_session.assert_called_once()

@pytest.mark.asyncio
@patch("lamia.adapters.llm.openai_adapter.openai.AsyncOpenAI")
async def test_generate_sdk_returns_llmresponse(mock_async_openai, openai_client_mock):
    mock_async_openai.return_value = openai_client_mock
    adapter = OpenAIAdapter(api_key="sk-test")
    await adapter.initialize()
    response = await adapter.generate("Hello?")
    assert response.text == "OpenAI response"
    assert response.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    assert response.model == "gpt-3.5-turbo"

@pytest.mark.asyncio
@patch("lamia.adapters.llm.openai_adapter.aiohttp.ClientSession")
async def test_generate_http_returns_llmresponse(mock_client_session, aiohttp_session_mock):
    adapter = OpenAIAdapter(api_key="sk-test")
    adapter._use_sdk = False
    mock_client_session.return_value = aiohttp_session_mock
    await adapter.initialize()
    response = await adapter.generate("Hello?")
    assert response.text == "HTTP response"
    assert response.usage == {"prompt_tokens": 7, "completion_tokens": 4, "total_tokens": 11}
    assert response.model == "gpt-3.5-turbo"

@pytest.mark.asyncio
@patch("lamia.adapters.llm.openai_adapter.aiohttp.ClientSession")
async def test_generate_http_error_handling(mock_client_session, aiohttp_session_mock):
    adapter = OpenAIAdapter(api_key="sk-test")
    adapter._use_sdk = False
    mock_client_session.return_value = aiohttp_session_mock
    await adapter.initialize()
    # Simulate non-200 response
    aiohttp_session_mock.post.return_value.status = 400
    aiohttp_session_mock.post.return_value.text = AsyncMock(return_value="Bad Request")
    with pytest.raises(RuntimeError) as exc:
        await adapter.generate("fail")
    assert "OpenAI API error" in str(exc.value)

@pytest.mark.asyncio
@patch("lamia.adapters.llm.openai_adapter.openai.AsyncOpenAI")
async def test_generate_sdk_error_handling(mock_async_openai, openai_client_mock):
    # Simulate SDK raising an exception
    error = Exception("Bad request from SDK")
    openai_client_mock.chat.completions.create = AsyncMock(side_effect=error)
    mock_async_openai.return_value = openai_client_mock
    adapter = OpenAIAdapter(api_key="sk-test")
    await adapter.initialize()
    with pytest.raises(Exception) as exc:
        await adapter.generate("fail")
    assert "Bad request from SDK" in str(exc.value)

@pytest.mark.asyncio
@patch("lamia.adapters.llm.openai_adapter.openai.AsyncOpenAI")
async def test_close_sdk_closes_client(mock_async_openai, openai_client_mock):
    mock_async_openai.return_value = openai_client_mock
    adapter = OpenAIAdapter(api_key="sk-test")
    await adapter.initialize()
    await adapter.close()
    openai_client_mock.close.assert_awaited()

@pytest.mark.asyncio
@patch("lamia.adapters.llm.openai_adapter.aiohttp.ClientSession")
async def test_close_http_closes_session(mock_client_session, aiohttp_session_mock):
    adapter = OpenAIAdapter(api_key="sk-test")
    adapter._use_sdk = False
    mock_client_session.return_value = aiohttp_session_mock
    await adapter.initialize()
    await adapter.close()
    aiohttp_session_mock.close.assert_awaited()

def test_has_context_memory_variants():
    # Chat models (should be True)
    assert OpenAIAdapter(api_key="sk", model="gpt-3.5-turbo").has_context_memory is True
    assert OpenAIAdapter(api_key="sk", model="gpt-4").has_context_memory is True
    assert OpenAIAdapter(api_key="sk", model="gpt-4-turbo").has_context_memory is True
    # Legacy chat models (should be True)
    assert OpenAIAdapter(api_key="sk", model="text-davinci-003").has_context_memory is True
    assert OpenAIAdapter(api_key="sk", model="text-davinci-002").has_context_memory is True
    # Non-chat model (should be False)
    assert OpenAIAdapter(api_key="sk", model="ada").has_context_memory is False
    assert OpenAIAdapter(api_key="sk", model="babbage").has_context_memory is False
    assert OpenAIAdapter(api_key="sk", model="curie").has_context_memory is False
    assert OpenAIAdapter(api_key="sk", model="text-ada-001").has_context_memory is False
