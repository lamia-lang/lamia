import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock
#from lamia.adapters.llm.local.llama_adapter import LlamaAdapter
#from lamia.adapters.llm.local import llama_adapter


"""@pytest_asyncio.fixture
def llama_model_mock():
    mock = MagicMock()
    mock.create_completion.return_value = {
        "choices": [{"text": "Hello, world!"}],
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": 3,
            "total_tokens": 8
        }
    }
    return mock

@pytest.mark.asyncio
@patch("lamia.adapters.llm.llama_adapter.Llama")
async def test_initialize_sets_model(mock_llama, llama_model_mock):
    mock_llama.return_value = llama_model_mock
    adapter = LlamaAdapter(model_path="/tmp/fake-model.bin")
    await adapter.initialize()
    assert adapter.model is llama_model_mock
    mock_llama.assert_called_once_with(model_path="/tmp/fake-model.bin")

@pytest.mark.asyncio
@patch("lamia.adapters.llm.llama_adapter.Llama")
async def test_generate_returns_llmresponse(mock_llama, llama_model_mock):
    mock_llama.return_value = llama_model_mock
    adapter = LlamaAdapter(model_path="/tmp/fake-model.bin")
    await adapter.initialize()
    response = await adapter.generate("Say hi")
    assert response.text == "Hello, world!"
    assert response.usage == {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
    assert response.model.startswith("llama-")

@pytest.mark.asyncio
@patch("lamia.adapters.llm.llama_adapter.Llama")
async def test_generate_raises_if_not_initialized(mock_llama):
    adapter = LlamaAdapter(model_path="/tmp/fake-model.bin")
    with pytest.raises(RuntimeError):
        await adapter.generate("Say hi")

@pytest.mark.asyncio
@patch("lamia.adapters.llm.llama_adapter.Llama")
async def test_close_sets_model_to_none(mock_llama, llama_model_mock):
    mock_llama.return_value = llama_model_mock
    adapter = LlamaAdapter(model_path="/tmp/fake-model.bin")
    await adapter.initialize()
    await adapter.close()
    assert adapter.model is None

@pytest.mark.parametrize("model_path,expected", [
    ("/tmp/llama-chat.bin", True),
    ("/tmp/llama-instruct.bin", True),
    ("/tmp/llama-plain.bin", False),
])
def test_has_context_memory_inference(model_path, expected):
    adapter = LlamaAdapter(model_path=model_path)
    assert adapter.has_context_memory is expected

@patch("lamia.adapters.llm.llama_adapter.Path.exists", return_value=False)
def test_model_path_file_not_found(mock_exists):
    with pytest.raises(FileNotFoundError):
        LlamaAdapter(model_path="/tmp/nonexistent.bin")

@patch("lamia.adapters.llm.llama_adapter.Path.exists", return_value=True)
def test_model_path_env(monkeypatch, mock_exists):
    monkeypatch.setenv("LLAMA_MODEL_PATH", "/tmp/from-env.bin")
    adapter = LlamaAdapter()
    assert adapter.model_path == "/tmp/from-env.bin"

def test_import_llama_adapter():
    assert llama_adapter is not None """