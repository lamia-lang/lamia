import pytest
from lamia.adapters.llm import strategy

def test_import_strategy():
    assert strategy is not None 