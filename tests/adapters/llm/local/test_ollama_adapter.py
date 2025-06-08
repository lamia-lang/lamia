import pytest
from lamia.adapters.llm.local import ollama_adapter

def test_import_ollama_adapter():
    assert ollama_adapter is not None 