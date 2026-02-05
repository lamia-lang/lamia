"""Test complete error integration: base adapters + retry wrappers throw same meaningful errors."""

import pytest

from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse
from lamia.adapters.filesystem.base import BaseFSAdapter
from lamia.adapters.retry.adapter_wrappers.retrying_fs_adapter import RetryingFSAdapter
from lamia.adapters.retry.adapter_wrappers.retrying_llm_adapter import RetryingLLMAdapter
from lamia.errors import (
    ExternalOperationPermanentError,
    ExternalOperationRateLimitError,
    ExternalOperationTransientError,
    ExternalOperationFailedError,
)
from lamia.adapters.error_classifiers import HttpErrorClassifier, FilesystemErrorClassifier, SelfHostedLLMErrorClassifier


class TestRemoteLLMAdapter(BaseLLMAdapter):
    """Test remote LLM adapter that demonstrates error classification."""

    def __init__(self, error_to_raise=None):
        self.error_to_raise = error_to_raise

    @classmethod
    def name(cls):
        return "test_remote"

    @classmethod
    def is_remote(cls):
        return True

    async def generate(self, prompt, model):
        if self.error_to_raise:
            try:
                raise self.error_to_raise
            except Exception as e:
                self._classify_and_raise_error(e)
        return LLMResponse(text="test response", raw_response={}, usage={}, model="test")

    async def close(self):
        pass


class TestLocalLLMAdapter(BaseLLMAdapter):
    """Test local LLM adapter that demonstrates error classification."""

    def __init__(self, error_to_raise=None):
        self.error_to_raise = error_to_raise

    @classmethod
    def name(cls):
        return "test_local"

    @classmethod
    def is_remote(cls):
        return False

    async def generate(self, prompt, model):
        if self.error_to_raise:
            try:
                raise self.error_to_raise
            except Exception as e:
                self._classify_and_raise_error(e)
        return LLMResponse(text="test response", raw_response={}, usage={}, model="test")

    async def close(self):
        pass


class TestFSAdapter(BaseFSAdapter):
    """Test filesystem adapter that demonstrates error classification."""

    def __init__(self, error_to_raise=None):
        self.error_to_raise = error_to_raise

    async def read(self, path):
        if self.error_to_raise:
            try:
                raise self.error_to_raise
            except Exception as e:
                self._classify_and_raise_error(e)
        return b"test content"

    async def write(self, path, data):
        if self.error_to_raise:
            try:
                raise self.error_to_raise
            except Exception as e:
                self._classify_and_raise_error(e)

    async def exists(self, path):
        return True

    async def delete(self, path):
        if self.error_to_raise:
            try:
                raise self.error_to_raise
            except Exception as e:
                self._classify_and_raise_error(e)


@pytest.mark.asyncio
class TestCompleteErrorIntegration:
    """Test that all adapters (plain and retry-wrapped) throw consistent meaningful errors."""

    async def test_remote_llm_adapter_error_classification(self):
        """Test that remote LLM adapters classify errors correctly."""
        adapter = TestRemoteLLMAdapter(error_to_raise=Exception("401 Unauthorized"))

        with pytest.raises(ExternalOperationPermanentError) as exc_info:
            await adapter.generate("test", None)

        assert "401 Unauthorized" in str(exc_info.value)
        assert len(exc_info.value.retry_history) == 1
        assert "Attempt 1:" in exc_info.value.retry_history[0]
        assert exc_info.value.original_error is not None

    async def test_local_llm_adapter_error_classification(self):
        """Test that local LLM adapters classify errors correctly."""
        adapter = TestLocalLLMAdapter(error_to_raise=Exception("connection timeout"))

        with pytest.raises(ExternalOperationTransientError) as exc_info:
            await adapter.generate("test", None)

        assert "connection timeout" in str(exc_info.value)
        assert len(exc_info.value.retry_history) == 1

    async def test_filesystem_adapter_error_classification(self):
        """Test that filesystem adapters classify errors correctly."""
        adapter = TestFSAdapter(error_to_raise=FileNotFoundError("No such file"))

        with pytest.raises(ExternalOperationPermanentError) as exc_info:
            await adapter.read("/nonexistent")

        assert "No such file" in str(exc_info.value)
        assert len(exc_info.value.retry_history) == 1

    async def test_adapter_gets_correct_classifier(self):
        """Test that adapters get the correct error classifier based on type."""
        remote_adapter = TestRemoteLLMAdapter()
        local_adapter = TestLocalLLMAdapter()
        fs_adapter = TestFSAdapter()

        assert isinstance(remote_adapter._get_error_classifier(), HttpErrorClassifier)
        assert isinstance(local_adapter._get_error_classifier(), SelfHostedLLMErrorClassifier)
        assert isinstance(fs_adapter._get_error_classifier(), FilesystemErrorClassifier)

    async def test_consistency_between_plain_and_wrapped_adapters(self):
        """Test that plain adapters and retry-wrapped adapters throw the same error types."""
        base_adapter = TestRemoteLLMAdapter(error_to_raise=Exception("invalid api key"))

        with pytest.raises(ExternalOperationPermanentError) as plain_exc:
            await base_adapter.generate("test", None)

        base_adapter2 = TestRemoteLLMAdapter(error_to_raise=Exception("invalid api key"))
        wrapped_adapter = RetryingLLMAdapter(base_adapter2)

        with pytest.raises(ExternalOperationPermanentError) as wrapped_exc:
            await wrapped_adapter.generate("test", None)

        assert type(plain_exc.value) == type(wrapped_exc.value)
        assert "invalid api key" in str(plain_exc.value)
        assert "invalid api key" in str(wrapped_exc.value)

        assert len(plain_exc.value.retry_history) == 1
        assert len(wrapped_exc.value.retry_history) == 1

    async def test_rate_limit_error_consistency(self):
        """Test rate limit error consistency between plain and wrapped adapters."""
        rate_limit_error = Exception("429 Too Many Requests")

        plain_adapter = TestRemoteLLMAdapter(error_to_raise=rate_limit_error)
        with pytest.raises(ExternalOperationRateLimitError) as plain_exc:
            await plain_adapter.generate("test", None)

        base_adapter = TestRemoteLLMAdapter(error_to_raise=rate_limit_error)
        wrapped_adapter = RetryingLLMAdapter(base_adapter)
        with pytest.raises(ExternalOperationRateLimitError) as wrapped_exc:
            await wrapped_adapter.generate("test", None)

        assert type(plain_exc.value) == type(wrapped_exc.value)
        assert "429" in str(plain_exc.value)
        assert "429" in str(wrapped_exc.value)

    async def test_filesystem_consistency(self):
        """Test filesystem error consistency between plain and wrapped adapters."""
        perm_error = PermissionError("Permission denied")

        plain_adapter = TestFSAdapter(error_to_raise=perm_error)
        with pytest.raises(ExternalOperationPermanentError) as plain_exc:
            await plain_adapter.read("/forbidden")

        base_adapter = TestFSAdapter(error_to_raise=perm_error)
        wrapped_adapter = RetryingFSAdapter(base_adapter)
        with pytest.raises(ExternalOperationPermanentError) as wrapped_exc:
            await wrapped_adapter.read("/forbidden")

        assert type(plain_exc.value) == type(wrapped_exc.value)
        assert "Permission denied" in str(plain_exc.value)
        assert "Permission denied" in str(wrapped_exc.value)

    async def test_error_details_preservation(self):
        """Test that error details are preserved correctly."""
        original_error = ValueError("Custom error message")
        adapter = TestRemoteLLMAdapter(error_to_raise=original_error)

        with pytest.raises(ExternalOperationFailedError) as exc_info:
            await adapter.generate("test", None)

        external_error = exc_info.value
        assert str(external_error) == "Custom error message"
        assert external_error.original_error is original_error
        assert len(external_error.retry_history) == 1
        assert "ValueError: Custom error message" in external_error.retry_history[0]
