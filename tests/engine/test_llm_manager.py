import pytest
from lamia.engine import llm_manager

def test_import_llm_manager():
    assert llm_manager is not None 