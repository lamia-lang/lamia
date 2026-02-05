"""Tests for CompositeErrorClassifier."""

import pytest
from aiohttp import ClientResponseError as AiohttpError, RequestInfo
from multidict import CIMultiDict
from yarl import URL

from lamia.adapters.error_classifiers.composite import CompositeErrorClassifier
from lamia.adapters.error_classifiers.http import HttpErrorClassifier
from lamia.adapters.error_classifiers.self_hosted import SelfHostedLLMErrorClassifier
from lamia.adapters.error_classifiers.base import ErrorClassifier
from lamia.adapters.error_classifiers.categories import ErrorCategory

_DUMMY_URL = URL('http://localhost:11434')
_DUMMY_REQUEST_INFO = RequestInfo(
    url=_DUMMY_URL, method='GET', headers=CIMultiDict(), real_url=_DUMMY_URL
)


def make_aiohttp_error(status: int, message: str = "") -> AiohttpError:
    """Create an aiohttp ClientResponseError for testing."""
    return AiohttpError(_DUMMY_REQUEST_INFO, (), status=status, message=message)


class TestCompositeErrorClassifierInterface:
    """Test CompositeErrorClassifier interface."""

    def test_inherits_from_error_classifier(self):
        classifier = CompositeErrorClassifier(HttpErrorClassifier())
        assert isinstance(classifier, ErrorClassifier)

    def test_can_instantiate_with_multiple_classifiers(self):
        classifier = CompositeErrorClassifier(
            HttpErrorClassifier(),
            SelfHostedLLMErrorClassifier(),
        )
        assert classifier is not None
        assert len(classifier.classifiers) == 2


class TestCompositeErrorClassifierChaining:
    """Test CompositeErrorClassifier classifier chaining."""

    def setup_method(self):
        self.classifier = CompositeErrorClassifier(
            HttpErrorClassifier(),
            SelfHostedLLMErrorClassifier(),
        )

    def test_http_404_classified_as_permanent(self):
        """HTTP 404 should be caught by HttpErrorClassifier."""
        error = make_aiohttp_error(404)
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT

    def test_http_429_classified_as_rate_limit(self):
        """HTTP 429 should be caught by HttpErrorClassifier."""
        error = make_aiohttp_error(429)
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.RATE_LIMIT

    def test_http_503_classified_as_transient(self):
        """HTTP 503 should be caught by HttpErrorClassifier."""
        error = make_aiohttp_error(503)
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT

    def test_model_not_found_message_classified_as_permanent(self):
        """LLM-specific message should be caught by SelfHostedLLMErrorClassifier."""
        error = Exception("model not found in registry")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT

    def test_out_of_memory_message_classified_as_transient(self):
        """LLM-specific transient message should return TRANSIENT."""
        error = Exception("CUDA out of memory")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT

    def test_queue_full_message_classified_as_rate_limit(self):
        """LLM queue full should be caught by SelfHostedLLMErrorClassifier."""
        error = Exception("inference queue at capacity")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.RATE_LIMIT

    def test_unknown_error_defaults_to_transient(self):
        """Unknown errors should default to TRANSIENT."""
        error = Exception("some random error")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT


class TestCompositeErrorClassifierPriority:
    """Test that first decisive classifier wins."""

    def setup_method(self):
        self.classifier = CompositeErrorClassifier(
            HttpErrorClassifier(),
            SelfHostedLLMErrorClassifier(),
        )

    def test_http_status_takes_priority_over_message(self):
        """HTTP status should be checked before message patterns."""
        # HTTP 404 with transient-sounding message
        error = make_aiohttp_error(404, "server timeout occurred")
        result = self.classifier.classify_error(error)
        # HTTP 404 → PERMANENT wins over "timeout" → TRANSIENT
        assert result == ErrorCategory.PERMANENT

    def test_permanent_stops_chain(self):
        """Once PERMANENT is found, chain stops."""
        error = make_aiohttp_error(401)  # Unauthorized
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT

    def test_rate_limit_stops_chain(self):
        """Once RATE_LIMIT is found, chain stops."""
        error = make_aiohttp_error(429)
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.RATE_LIMIT


class TestCompositeErrorClassifierRealWorldScenarios:
    """Test realistic self-hosted LLM error scenarios."""

    def setup_method(self):
        self.classifier = CompositeErrorClassifier(
            HttpErrorClassifier(),
            SelfHostedLLMErrorClassifier(),
        )

    def test_ollama_model_not_found_http_404(self):
        """Ollama returns HTTP 404 when model not found."""
        error = make_aiohttp_error(404, "model 'llama2' not found")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT

    def test_ollama_server_down_connection_error(self):
        """Ollama connection refused is transient."""
        error = ConnectionError("Connection refused to localhost:11434")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT

    def test_vllm_overloaded_http_503(self):
        """vLLM returns HTTP 503 when overloaded."""
        error = make_aiohttp_error(503, "Service temporarily unavailable")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT

    def test_vllm_queue_full_message(self):
        """vLLM queue full error from message."""
        error = Exception("vLLM: Request queue at capacity")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.RATE_LIMIT

    def test_cuda_oom_message(self):
        """CUDA OOM is transient (can retry after other requests finish)."""
        error = Exception("CUDA out of memory. Tried to allocate 2.00 GiB")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT

    def test_invalid_api_key_http_401(self):
        """Invalid API key returns HTTP 401."""
        error = make_aiohttp_error(401, "Invalid API key")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT







