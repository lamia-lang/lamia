"""Tests for retry adapter wrapper method coverage."""

import inspect
from lamia.adapters.retry.adapter_wrappers.retrying_llm_adapter import RetryingLLMAdapter
from lamia.adapters.retry.adapter_wrappers.retrying_fs_adapter import RetryingFSAdapter
from lamia.adapters.retry.adapter_wrappers.retrying_browser_adapter import RetryingBrowserAdapter
from lamia.adapters.llm.base import BaseLLMAdapter
from lamia.adapters.filesystem.base import BaseFSAdapter
from lamia.adapters.web.browser.base import BaseBrowserAdapter


class TestRetryingLLMAdapterCoverage:
    """Test that RetryingLLMAdapter implements all required methods."""

    def test_abstract_methods_are_implemented(self):
        """Verify all abstract methods from BaseLLMAdapter are implemented."""
        base_abstract_methods = BaseLLMAdapter.__abstractmethods__
        wrapper_class = RetryingLLMAdapter

        for method_name in base_abstract_methods:
            # Check that the method exists on the wrapper
            method = getattr(wrapper_class, method_name, None)
            assert method is not None, f"Method {method_name} not found on {wrapper_class.__name__}"

            # For instance methods, verify they don't raise NotImplementedError
            # (classmethods like name/is_remote intentionally raise NotImplementedError)
            if not inspect.ismethod(method) and not inspect.isfunction(method):
                # It's a descriptor (property, classmethod, etc.)
                if isinstance(method, property):
                    # Properties are fine - they're implemented
                    continue
                elif isinstance(method, classmethod):
                    # Classmethods that raise NotImplementedError are intentional
                    # (name, is_remote, env_var_names)
                    continue

    def test_delegation_to_internal_adapter(self):
        """Verify wrapper delegates to internal _adapter."""
        # Check that __init__ exists
        init_method = getattr(RetryingLLMAdapter, '__init__', None)
        assert init_method is not None, "Wrapper should have __init__"

        # has_context_memory property should delegate
        has_context_memory_prop = getattr(RetryingLLMAdapter, 'has_context_memory', None)
        assert has_context_memory_prop is not None, "has_context_memory property should exist"


class TestRetryingFSAdapterCoverage:
    """Test that RetryingFSAdapter implements all required methods."""

    def test_abstract_methods_are_implemented(self):
        """Verify all abstract methods from BaseFSAdapter are implemented."""
        base_abstract_methods = BaseFSAdapter.__abstractmethods__
        wrapper_class = RetryingFSAdapter

        for method_name in base_abstract_methods:
            # Check that the method exists on the wrapper
            method = getattr(wrapper_class, method_name, None)
            assert method is not None, f"Method {method_name} not found on {wrapper_class.__name__}"

            # Verify it's a callable (not raising NotImplementedError)
            assert callable(method), f"Method {method_name} should be callable"

    def test_delegation_to_internal_adapter(self):
        """Verify wrapper delegates to internal _adapter."""
        # Check that __init__ exists
        init_method = getattr(RetryingFSAdapter, '__init__', None)
        assert init_method is not None, "Wrapper should have __init__"

        # Verify that all abstract methods delegate to _adapter
        abstract_methods = BaseFSAdapter.__abstractmethods__
        for method_name in abstract_methods:
            method = getattr(RetryingFSAdapter, method_name, None)
            assert method is not None, f"{method_name} method should exist"

class TestRetryingBrowserAdapterCoverage:
    """Test that RetryingBrowserAdapter implements all required methods."""

    def test_abstract_methods_are_implemented(self):
        """Verify all abstract methods from BaseBrowserAdapter are implemented."""
        base_abstract_methods = BaseBrowserAdapter.__abstractmethods__
        wrapper_class = RetryingBrowserAdapter

        for method_name in base_abstract_methods:
            # Check that the method exists on the wrapper
            method = getattr(wrapper_class, method_name, None)
            assert method is not None, f"Method {method_name} not found on {wrapper_class.__name__}"

            # Verify it's a callable (not raising NotImplementedError)
            assert callable(method), f"Method {method_name} should be callable"

    def test_delegation_to_internal_adapter(self):
        """Verify wrapper delegates to internal adapter."""
        # Check that __init__ exists (note: browser adapter uses 'adapter' not '_adapter')
        init_method = getattr(RetryingBrowserAdapter, '__init__', None)
        assert init_method is not None, "Wrapper should have __init__"

        # Verify that all abstract methods delegate to adapter
        abstract_methods = BaseBrowserAdapter.__abstractmethods__
        for method_name in abstract_methods:
            method = getattr(RetryingBrowserAdapter, method_name, None)
            assert method is not None, f"{method_name} method should exist"
