"""Tests for discovering user adapters from the extensions folder."""

import pytest

from lamia.engine.managers.llm.providers import ProviderRegistry

OPENAI_COMPATIBLE_ADAPTER = '''
from lamia.adapters.llm.openai_compatible_adapter import OpenAICompatibleAdapter
from lamia.adapters.llm.openai_adapter import OpenAIAdapter


class MistralAdapter(OpenAICompatibleAdapter):
    API_URL = "https://api.mistral.ai/v1/chat/completions"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = None

    @classmethod
    def name(cls) -> str:
        return "mistral"

    @classmethod
    def is_remote(cls) -> bool:
        return True
'''

BASE_ADAPTER_WITHOUT_GENERATE = '''
from lamia.adapters.llm.base import BaseLLMAdapter


class LegacyAdapter(BaseLLMAdapter):
    API_URL = "https://api.example.com/v1/chat/completions"

    @classmethod
    def name(cls) -> str:
        return "legacy"

    @classmethod
    def is_remote(cls) -> bool:
        return True

    async def close(self) -> None:
        pass
'''


def _registry_with(tmp_path, code: str) -> ProviderRegistry:
    (tmp_path / "adapter.py").write_text(code)
    registry = ProviderRegistry(needed_providers={"openai", "mistral", "legacy"})
    registry.add_user_adapters([str(tmp_path)])
    return registry


def test_registers_only_adapters_defined_in_the_file(tmp_path):
    registry = _registry_with(tmp_path, OPENAI_COMPATIBLE_ADAPTER)

    assert registry.get_adapter_class("mistral").__name__ == "MistralAdapter"
    assert registry.get_adapter_class("openai").__module__ == "lamia.adapters.llm.openai_adapter"


def test_api_url_adapter_without_generate_reports_base_class(tmp_path):
    with pytest.raises(RuntimeError, match="OpenAICompatibleAdapter"):
        _registry_with(tmp_path, BASE_ADAPTER_WITHOUT_GENERATE)
