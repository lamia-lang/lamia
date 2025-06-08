import pytest
from lamia.adapters.llm import anthropic_adapter

def test_import_anthropic_adapter():
    assert anthropic_adapter is not None 