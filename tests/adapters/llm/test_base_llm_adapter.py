import pytest
from lamia.adapters.llm import base

def test_import_base_llm_adapter():
    assert base is not None 