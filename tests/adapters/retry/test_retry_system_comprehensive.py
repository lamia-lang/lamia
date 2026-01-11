"""Comprehensive tests for Retry System: adapters, factory, and defaults."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import timedelta
from lamia.adapters.retry.adapter_wrappers.retrying_fs_adapter import RetryingFSAdapter
from lamia.adapters.retry.adapter_wrappers.retrying_llm_adapter import RetryingLLMAdapter
from lamia.adapters.retry.adapter_wrappers.retrying_browser_adapter import RetryingBrowserAdapter
from lamia.adapters.retry.factory import RetriableAdapterFactory
from lamia.adapters.retry.defaults import get_default_config_for_adapter, RETRY_DEFAULTS
from lamia.adapters.filesystem.base import BaseFSAdapter
from lamia.adapters.llm.base import BaseLLMAdapter, LLMModel, LLMResponse
from lamia.adapters.web.browser.base import BaseBrowserAdapter
from lamia.types import ExternalOperationRetryConfig
from lamia.internal_types import BrowserActionParams


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def mock_fs_adapter():
    """Create a mock filesystem adapter."""
    adapter = Mock(spec=BaseFSAdapter)
    adapter.read = AsyncMock(return_value=b"file contents")
    adapter.write = AsyncMock(return_value=None)
    return adapter


@pytest.fixture
def mock_llm_adapter():
    """Create a mock LLM adapter."""
    adapter = Mock(spec=BaseLLMAdapter)
    adapter.generate = AsyncMock(return_value=LLMResponse(
        content="Generated text",
        model_name="test-model",
        total_tokens=100
    ))
    adapter.has_context_memory = False
    adapter.is_remote = Mock(return_value=True)
    adapter.close = AsyncMock(return_value=None)
    return adapter


@pytest.fixture
def mock_browser_adapter():
    """Create a mock browser adapter."""
    adapter = Mock(spec=BaseBrowserAdapter)
    adapter.initialize = AsyncMock(return_value=None)
    adapter.close = AsyncMock(return_value=None)
    adapter.navigate = AsyncMock(return_value=None)
    adapter.click = AsyncMock(return_value=None)
    adapter.type_text = AsyncMock(return_value=None)
    adapter.get_text = AsyncMock(return_value="Element text")
    adapter.get_current_url = AsyncMock(return_value="https://example.com")
    adapter.set_profile = Mock(return_value=None)
    adapter.load_session_state = AsyncMock(return_value=None)
    adapter.save_session_state = AsyncMock(return_value=None)
    return adapter


@pytest.fixture
def retry_config():
    """Create a basic retry configuration."""
    return ExternalOperationRetryConfig(
        max_attempts=3,
        base_delay=0.1,
        max_delay=1.0,
        exponential_base=2.0,
        max_total_duration=timedelta(seconds=30)
    )


# ============================================================================
# RETRYING FS ADAPTER TESTS
# ============================================================================

class TestRetryingFSAdapterInitialization:
    """Test RetryingFSAdapter initialization."""

    def test_init_with_adapter(self, mock_fs_adapter, retry_config):
        """Test initialization with adapter and config."""
        wrapper = RetryingFSAdapter(
            adapter=mock_fs_adapter,
            retry_config=retry_config,
            collect_stats=True
        )

        assert wrapper._adapter == mock_fs_adapter
        assert wrapper._retry_handler is not None

    def test_init_with_default_config(self, mock_fs_adapter):
        """Test initialization with default config."""
        wrapper = RetryingFSAdapter(
            adapter=mock_fs_adapter,
            retry_config=None,
            collect_stats=False
        )

        assert wrapper._adapter == mock_fs_adapter
        assert wrapper._retry_handler is not None

    def test_init_stats_collection_disabled(self, mock_fs_adapter, retry_config):
        """Test initialization with stats collection disabled."""
        wrapper = RetryingFSAdapter(
            adapter=mock_fs_adapter,
            retry_config=retry_config,
            collect_stats=False
        )

        assert wrapper._retry_handler is not None


@pytest.mark.asyncio
class TestRetryingFSAdapterOperations:
    """Test RetryingFSAdapter file operations."""

    async def test_read_success(self, mock_fs_adapter, retry_config):
        """Test successful file read."""
        wrapper = RetryingFSAdapter(mock_fs_adapter, retry_config)

        result = await wrapper.read("/path/to/file.txt")

        assert result == b"file contents"
        mock_fs_adapter.read.assert_called_once()

    async def test_read_with_retry(self, mock_fs_adapter, retry_config):
        """Test file read with retry on transient error."""
        mock_fs_adapter.read.side_effect = [
            Exception("Temporary error"),
            b"file contents"
        ]

        wrapper = RetryingFSAdapter(mock_fs_adapter, retry_config)
        result = await wrapper.read("/path/to/file.txt")

        assert result == b"file contents"
        assert mock_fs_adapter.read.call_count == 2

    async def test_write_success(self, mock_fs_adapter, retry_config):
        """Test successful file write."""
        wrapper = RetryingFSAdapter(mock_fs_adapter, retry_config)

        await wrapper.write("/path/to/file.txt", b"data")

        mock_fs_adapter.write.assert_called_once_with("/path/to/file.txt", b"data")

    async def test_write_with_retry(self, mock_fs_adapter, retry_config):
        """Test file write with retry on transient error."""
        mock_fs_adapter.write.side_effect = [
            Exception("Disk busy"),
            None
        ]

        wrapper = RetryingFSAdapter(mock_fs_adapter, retry_config)
        await wrapper.write("/path/to/file.txt", b"data")

        assert mock_fs_adapter.write.call_count == 2

    async def test_get_stats(self, mock_fs_adapter, retry_config):
        """Test getting retry statistics."""
        wrapper = RetryingFSAdapter(mock_fs_adapter, retry_config, collect_stats=True)

        # Execute some operations
        await wrapper.read("/path/file.txt")

        stats = wrapper.get_stats()
        assert stats is not None


# ============================================================================
# RETRYING LLM ADAPTER TESTS
# ============================================================================

class TestRetryingLLMAdapterInitialization:
    """Test RetryingLLMAdapter initialization."""

    def test_init_with_adapter(self, mock_llm_adapter, retry_config):
        """Test initialization with adapter and config."""
        wrapper = RetryingLLMAdapter(
            adapter=mock_llm_adapter,
            retry_config=retry_config,
            collect_stats=True
        )

        assert wrapper._adapter == mock_llm_adapter
        assert wrapper._retry_handler is not None

    def test_init_with_default_config(self, mock_llm_adapter):
        """Test initialization with default config."""
        wrapper = RetryingLLMAdapter(
            adapter=mock_llm_adapter,
            retry_config=None,
            collect_stats=True
        )

        assert wrapper._adapter == mock_llm_adapter

    def test_has_context_memory_property(self, mock_llm_adapter, retry_config):
        """Test has_context_memory property proxies to adapter."""
        mock_llm_adapter.has_context_memory = True
        wrapper = RetryingLLMAdapter(mock_llm_adapter, retry_config)

        assert wrapper.has_context_memory is True

    def test_class_methods_raise_not_implemented(self):
        """Test that class methods raise NotImplementedError."""
        with pytest.raises(NotImplementedError):
            RetryingLLMAdapter.name()

        with pytest.raises(NotImplementedError):
            RetryingLLMAdapter.env_var_names()

        with pytest.raises(NotImplementedError):
            RetryingLLMAdapter.is_remote()


@pytest.mark.asyncio
class TestRetryingLLMAdapterOperations:
    """Test RetryingLLMAdapter LLM operations."""

    async def test_generate_success(self, mock_llm_adapter, retry_config):
        """Test successful text generation."""
        wrapper = RetryingLLMAdapter(mock_llm_adapter, retry_config)

        result = await wrapper.generate("Test prompt")

        assert result.content == "Generated text"
        mock_llm_adapter.generate.assert_called_once()

    async def test_generate_with_model(self, mock_llm_adapter, retry_config):
        """Test generation with specific model."""
        wrapper = RetryingLLMAdapter(mock_llm_adapter, retry_config)
        model = LLMModel(name="gpt-4", max_tokens=1000)

        result = await wrapper.generate("Test prompt", model=model)

        assert result.content == "Generated text"
        mock_llm_adapter.generate.assert_called_once_with("Test prompt", model)

    async def test_generate_with_retry(self, mock_llm_adapter, retry_config):
        """Test generation with retry on rate limit."""
        mock_llm_adapter.generate.side_effect = [
            Exception("Rate limit exceeded"),
            LLMResponse(content="Generated after retry", model_name="test", total_tokens=100)
        ]

        wrapper = RetryingLLMAdapter(mock_llm_adapter, retry_config)
        result = await wrapper.generate("Test prompt")

        assert result.content == "Generated after retry"
        assert mock_llm_adapter.generate.call_count == 2

    async def test_close(self, mock_llm_adapter, retry_config):
        """Test close proxies to underlying adapter."""
        wrapper = RetryingLLMAdapter(mock_llm_adapter, retry_config)

        await wrapper.close()

        mock_llm_adapter.close.assert_called_once()

    async def test_get_stats(self, mock_llm_adapter, retry_config):
        """Test getting retry statistics."""
        wrapper = RetryingLLMAdapter(mock_llm_adapter, retry_config, collect_stats=True)

        await wrapper.generate("Test")

        stats = wrapper.get_stats()
        assert stats is not None


# ============================================================================
# RETRYING BROWSER ADAPTER TESTS
# ============================================================================

class TestRetryingBrowserAdapterInitialization:
    """Test RetryingBrowserAdapter initialization."""

    def test_init_with_adapter(self, mock_browser_adapter, retry_config):
        """Test initialization with adapter and config."""
        wrapper = RetryingBrowserAdapter(
            adapter=mock_browser_adapter,
            retry_config=retry_config,
            collect_stats=True
        )

        assert wrapper.adapter == mock_browser_adapter
        assert wrapper.retry_handler is not None


@pytest.mark.asyncio
class TestRetryingBrowserAdapterOperations:
    """Test RetryingBrowserAdapter browser operations."""

    async def test_initialize(self, mock_browser_adapter, retry_config):
        """Test browser initialization."""
        wrapper = RetryingBrowserAdapter(mock_browser_adapter, retry_config)

        await wrapper.initialize()

        mock_browser_adapter.initialize.assert_called_once()

    async def test_close(self, mock_browser_adapter, retry_config):
        """Test browser close."""
        wrapper = RetryingBrowserAdapter(mock_browser_adapter, retry_config)

        await wrapper.close()

        mock_browser_adapter.close.assert_called_once()

    async def test_navigate(self, mock_browser_adapter, retry_config):
        """Test page navigation."""
        wrapper = RetryingBrowserAdapter(mock_browser_adapter, retry_config)
        params = BrowserActionParams(url="https://example.com")

        await wrapper.navigate(params)

        mock_browser_adapter.navigate.assert_called_once_with(params)

    async def test_click(self, mock_browser_adapter, retry_config):
        """Test element click."""
        wrapper = RetryingBrowserAdapter(mock_browser_adapter, retry_config)
        params = BrowserActionParams(selector="button.submit")

        await wrapper.click(params)

        mock_browser_adapter.click.assert_called_once_with(params)

    async def test_type_text(self, mock_browser_adapter, retry_config):
        """Test typing text."""
        wrapper = RetryingBrowserAdapter(mock_browser_adapter, retry_config)
        params = BrowserActionParams(selector="input#username", text="testuser")

        await wrapper.type_text(params)

        mock_browser_adapter.type_text.assert_called_once_with(params)

    async def test_get_text(self, mock_browser_adapter, retry_config):
        """Test getting element text."""
        wrapper = RetryingBrowserAdapter(mock_browser_adapter, retry_config)
        params = BrowserActionParams(selector=".title")

        result = await wrapper.get_text(params)

        assert result == "Element text"
        mock_browser_adapter.get_text.assert_called_once_with(params)

    async def test_get_current_url(self, mock_browser_adapter, retry_config):
        """Test getting current URL."""
        wrapper = RetryingBrowserAdapter(mock_browser_adapter, retry_config)

        result = await wrapper.get_current_url()

        assert result == "https://example.com"
        mock_browser_adapter.get_current_url.assert_called_once()

    async def test_click_with_retry(self, mock_browser_adapter, retry_config):
        """Test click with retry on transient error."""
        mock_browser_adapter.click.side_effect = [
            Exception("Element not found"),
            None
        ]

        wrapper = RetryingBrowserAdapter(mock_browser_adapter, retry_config)
        params = BrowserActionParams(selector="button")

        await wrapper.click(params)

        assert mock_browser_adapter.click.call_count == 2

    async def test_set_profile(self, mock_browser_adapter, retry_config):
        """Test setting browser profile (synchronous)."""
        wrapper = RetryingBrowserAdapter(mock_browser_adapter, retry_config)

        wrapper.set_profile("test_profile")

        mock_browser_adapter.set_profile.assert_called_once_with("test_profile")

    async def test_load_session_state(self, mock_browser_adapter, retry_config):
        """Test loading session state."""
        wrapper = RetryingBrowserAdapter(mock_browser_adapter, retry_config)

        await wrapper.load_session_state()

        mock_browser_adapter.load_session_state.assert_called_once()

    async def test_save_session_state(self, mock_browser_adapter, retry_config):
        """Test saving session state."""
        wrapper = RetryingBrowserAdapter(mock_browser_adapter, retry_config)

        await wrapper.save_session_state()

        mock_browser_adapter.save_session_state.assert_called_once()


# ============================================================================
# RETRIABLE ADAPTER FACTORY TESTS
# ============================================================================

class TestRetriableAdapterFactoryConfiguration:
    """Test RetriableAdapterFactory configuration."""

    def test_default_configuration(self):
        """Test default factory configuration."""
        # Reset to defaults
        RetriableAdapterFactory.configure(collect_stats=True, retries_enabled=True)

        assert RetriableAdapterFactory._collect_stats is True
        assert RetriableAdapterFactory._retries_enabled is True

    def test_configure_collect_stats(self):
        """Test configuring stats collection."""
        RetriableAdapterFactory.configure(collect_stats=False)

        assert RetriableAdapterFactory._collect_stats is False

        # Reset
        RetriableAdapterFactory.configure(collect_stats=True)

    def test_configure_retries_enabled(self):
        """Test configuring retry enablement."""
        RetriableAdapterFactory.configure(retries_enabled=False)

        assert RetriableAdapterFactory._retries_enabled is False

        # Reset
        RetriableAdapterFactory.configure(retries_enabled=True)

    def test_configure_both(self):
        """Test configuring both parameters."""
        RetriableAdapterFactory.configure(collect_stats=False, retries_enabled=False)

        assert RetriableAdapterFactory._collect_stats is False
        assert RetriableAdapterFactory._retries_enabled is False

        # Reset
        RetriableAdapterFactory.configure(collect_stats=True, retries_enabled=True)


class TestRetriableAdapterFactoryCreation:
    """Test RetriableAdapterFactory adapter creation."""

    def setup_method(self):
        """Set up test fixtures."""
        # Ensure defaults
        RetriableAdapterFactory.configure(collect_stats=True, retries_enabled=True)

    def test_create_llm_adapter(self, mock_llm_adapter):
        """Test creating LLM adapter with retry wrapper."""
        result = RetriableAdapterFactory.create_llm_adapter(mock_llm_adapter)

        assert isinstance(result, RetryingLLMAdapter)
        assert result._adapter == mock_llm_adapter

    def test_create_llm_adapter_with_custom_config(self, mock_llm_adapter, retry_config):
        """Test creating LLM adapter with custom config."""
        result = RetriableAdapterFactory.create_llm_adapter(
            mock_llm_adapter,
            retry_config=retry_config
        )

        assert isinstance(result, RetryingLLMAdapter)

    def test_create_fs_adapter(self, mock_fs_adapter):
        """Test creating filesystem adapter with retry wrapper."""
        result = RetriableAdapterFactory.create_fs_adapter(mock_fs_adapter)

        assert isinstance(result, RetryingFSAdapter)
        assert result._adapter == mock_fs_adapter

    def test_create_fs_adapter_with_custom_config(self, mock_fs_adapter, retry_config):
        """Test creating FS adapter with custom config."""
        result = RetriableAdapterFactory.create_fs_adapter(
            mock_fs_adapter,
            retry_config=retry_config
        )

        assert isinstance(result, RetryingFSAdapter)

    def test_create_browser_adapter(self, mock_browser_adapter):
        """Test creating browser adapter with retry wrapper."""
        result = RetriableAdapterFactory.create_browser_adapter(mock_browser_adapter)

        assert isinstance(result, RetryingBrowserAdapter)
        assert result.adapter == mock_browser_adapter

    def test_create_browser_adapter_with_custom_config(self, mock_browser_adapter, retry_config):
        """Test creating browser adapter with custom config."""
        result = RetriableAdapterFactory.create_browser_adapter(
            mock_browser_adapter,
            retry_config=retry_config
        )

        assert isinstance(result, RetryingBrowserAdapter)

    def test_create_adapter_auto_detect_llm(self, mock_llm_adapter):
        """Test auto-detecting LLM adapter type."""
        result = RetriableAdapterFactory.create_adapter(mock_llm_adapter)

        assert isinstance(result, RetryingLLMAdapter)

    def test_create_adapter_auto_detect_fs(self, mock_fs_adapter):
        """Test auto-detecting FS adapter type."""
        result = RetriableAdapterFactory.create_adapter(mock_fs_adapter)

        assert isinstance(result, RetryingFSAdapter)

    def test_create_adapter_auto_detect_browser(self, mock_browser_adapter):
        """Test auto-detecting browser adapter type."""
        result = RetriableAdapterFactory.create_adapter(mock_browser_adapter)

        assert isinstance(result, RetryingBrowserAdapter)

    def test_create_adapter_unsupported_type(self):
        """Test creating adapter with unsupported type returns original."""
        unknown_adapter = Mock()

        result = RetriableAdapterFactory.create_adapter(unknown_adapter)

        assert result == unknown_adapter  # Returns as-is


class TestRetriableAdapterFactoryRetriesDisabled:
    """Test RetriableAdapterFactory with retries disabled."""

    def setup_method(self):
        """Set up test fixtures."""
        RetriableAdapterFactory.configure(retries_enabled=False)

    def teardown_method(self):
        """Clean up."""
        RetriableAdapterFactory.configure(retries_enabled=True)

    @patch('lamia.adapters.retry.factory.get_default_config_for_adapter')
    def test_create_llm_adapter_no_retries(self, mock_get_config, mock_llm_adapter):
        """Test creating LLM adapter with retries disabled."""
        mock_get_config.return_value = ExternalOperationRetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=60.0,
            exponential_base=2.0,
            max_total_duration=timedelta(seconds=600)
        )

        result = RetriableAdapterFactory.create_llm_adapter(mock_llm_adapter)

        assert isinstance(result, RetryingLLMAdapter)
        # Should have called to get base config
        mock_get_config.assert_called_once_with(mock_llm_adapter)


# ============================================================================
# DEFAULTS MODULE TESTS
# ============================================================================

class TestRetryDefaults:
    """Test retry default configurations."""

    def test_retry_defaults_exist(self):
        """Test that default configurations are defined."""
        assert "network" in RETRY_DEFAULTS
        assert "llm" in RETRY_DEFAULTS
        assert "self_hosted_llm" in RETRY_DEFAULTS
        assert "filesystem" in RETRY_DEFAULTS

    def test_network_defaults(self):
        """Test network retry defaults."""
        network_config = RETRY_DEFAULTS["network"]

        assert network_config["max_attempts"] == 3
        assert network_config["base_delay"] == 1.0
        assert network_config["max_delay"] == 32.0
        assert network_config["exponential_base"] == 2.0
        assert network_config["max_duration_seconds"] == 300

    def test_llm_defaults(self):
        """Test LLM retry defaults."""
        llm_config = RETRY_DEFAULTS["llm"]

        assert llm_config["max_attempts"] == 5
        assert llm_config["base_delay"] == 2.0
        assert llm_config["max_delay"] == 60.0
        assert llm_config["exponential_base"] == 2.0
        assert llm_config["max_duration_seconds"] == 600

    def test_self_hosted_llm_defaults(self):
        """Test self-hosted LLM retry defaults."""
        self_hosted_config = RETRY_DEFAULTS["self_hosted_llm"]

        assert self_hosted_config["max_attempts"] == 3
        assert self_hosted_config["base_delay"] == 5.0
        assert self_hosted_config["max_delay"] == 180.0
        assert self_hosted_config["exponential_base"] == 2.0
        assert self_hosted_config["max_duration_seconds"] == 1800

    def test_filesystem_defaults(self):
        """Test filesystem retry defaults."""
        fs_config = RETRY_DEFAULTS["filesystem"]

        assert fs_config["max_attempts"] == 2
        assert fs_config["base_delay"] == 0.5
        assert fs_config["max_delay"] == 5.0
        assert fs_config["exponential_base"] == 2.0
        assert fs_config["max_duration_seconds"] == 60


class TestGetDefaultConfigForAdapter:
    """Test get_default_config_for_adapter function."""

    def test_remote_llm_adapter_config(self, mock_llm_adapter):
        """Test config for remote LLM adapter."""
        mock_llm_adapter.is_remote.return_value = True

        config = get_default_config_for_adapter(mock_llm_adapter)

        assert config.max_attempts == 5  # LLM defaults
        assert config.base_delay == 2.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.max_total_duration == timedelta(seconds=600)

    def test_self_hosted_llm_adapter_config(self, mock_llm_adapter):
        """Test config for self-hosted LLM adapter."""
        mock_llm_adapter.is_remote.return_value = False

        config = get_default_config_for_adapter(mock_llm_adapter)

        assert config.max_attempts == 3  # Self-hosted LLM defaults
        assert config.base_delay == 5.0
        assert config.max_delay == 180.0
        assert config.max_total_duration == timedelta(seconds=1800)

    def test_fs_adapter_config(self, mock_fs_adapter):
        """Test config for filesystem adapter."""
        config = get_default_config_for_adapter(mock_fs_adapter)

        assert config.max_attempts == 2  # Filesystem defaults
        assert config.base_delay == 0.5
        assert config.max_delay == 5.0
        assert config.max_total_duration == timedelta(seconds=60)

    def test_unknown_adapter_type(self):
        """Test config for unknown adapter type falls back to network defaults."""
        unknown_adapter = Mock()

        config = get_default_config_for_adapter(unknown_adapter)

        assert config.max_attempts == 3  # Network defaults
        assert config.base_delay == 1.0
        assert config.max_delay == 32.0
        assert config.max_total_duration == timedelta(seconds=300)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
class TestRetrySystemIntegration:
    """Integration tests for the retry system."""

    async def test_end_to_end_llm_retry_flow(self):
        """Test complete LLM retry flow."""
        # Create mock LLM adapter that fails then succeeds
        mock_llm = Mock(spec=BaseLLMAdapter)
        mock_llm.generate = AsyncMock(side_effect=[
            Exception("Rate limit"),
            LLMResponse(content="Success", model_name="test", total_tokens=50)
        ])
        mock_llm.is_remote = Mock(return_value=True)
        mock_llm.has_context_memory = False

        # Create wrapper using factory
        wrapper = RetriableAdapterFactory.create_llm_adapter(mock_llm)

        # Execute and verify retry behavior
        result = await wrapper.generate("Test prompt")

        assert result.content == "Success"
        assert mock_llm.generate.call_count == 2

    async def test_end_to_end_fs_retry_flow(self):
        """Test complete filesystem retry flow."""
        mock_fs = Mock(spec=BaseFSAdapter)
        mock_fs.read = AsyncMock(side_effect=[
            Exception("Disk busy"),
            b"file data"
        ])

        wrapper = RetriableAdapterFactory.create_fs_adapter(mock_fs)

        result = await wrapper.read("/test/path.txt")

        assert result == b"file data"
        assert mock_fs.read.call_count == 2

    async def test_end_to_end_browser_retry_flow(self):
        """Test complete browser retry flow."""
        mock_browser = Mock(spec=BaseBrowserAdapter)
        mock_browser.click = AsyncMock(side_effect=[
            Exception("Element not found"),
            None
        ])

        wrapper = RetriableAdapterFactory.create_browser_adapter(mock_browser)
        params = BrowserActionParams(selector="button")

        await wrapper.click(params)

        assert mock_browser.click.call_count == 2

    async def test_factory_with_custom_config_integration(self, mock_llm_adapter):
        """Test factory creation with custom config integration."""
        custom_config = ExternalOperationRetryConfig(
            max_attempts=10,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=1.5,
            max_total_duration=timedelta(seconds=120)
        )

        wrapper = RetriableAdapterFactory.create_llm_adapter(
            mock_llm_adapter,
            retry_config=custom_config
        )

        # Wrapper should be created with custom config
        assert isinstance(wrapper, RetryingLLMAdapter)
