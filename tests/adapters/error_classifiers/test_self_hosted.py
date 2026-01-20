"""Comprehensive tests for Self-hosted LLM error classifier."""

import pytest

from lamia.adapters.error_classifiers.self_hosted import SelfHostedLLMErrorClassifier
from lamia.adapters.error_classifiers.base import ErrorClassifier
from lamia.adapters.error_classifiers.categories import ErrorCategory


class TestSelfHostedLLMErrorClassifierInterface:
    """Test SelfHostedLLMErrorClassifier interface and inheritance."""

    def test_inherits_from_error_classifier(self):
        """Test that SelfHostedLLMErrorClassifier inherits from ErrorClassifier."""
        classifier = SelfHostedLLMErrorClassifier()
        assert isinstance(classifier, ErrorClassifier)

    def test_implements_classify_error_method(self):
        """Test that SelfHostedLLMErrorClassifier implements classify_error."""
        assert hasattr(SelfHostedLLMErrorClassifier, 'classify_error')
        assert callable(SelfHostedLLMErrorClassifier.classify_error)

    def test_can_instantiate(self):
        """Test that SelfHostedLLMErrorClassifier can be instantiated."""
        classifier = SelfHostedLLMErrorClassifier()
        assert classifier is not None
        assert isinstance(classifier, SelfHostedLLMErrorClassifier)


class TestSelfHostedLLMErrorClassifierPermanentErrors:
    """Test SelfHostedLLMErrorClassifier permanent error detection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = SelfHostedLLMErrorClassifier()

    def test_model_not_found_errors(self):
        """Test permanent model not found errors."""
        model_errors = [
            "model not found in registry",
            "model not loaded on server",
            "invalid model specified",
            "model does not exist",
            "unknown model name"
        ]

        for message in model_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"

    def test_authentication_errors(self):
        """Test permanent authentication and authorization errors."""
        auth_errors = [
            "authentication failed",
            "unauthorized access to model",
            "forbidden model access",
            "invalid credentials provided",
            "access denied to resource"
        ]

        for message in auth_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"

    def test_bad_request_errors(self):
        """Test permanent bad request errors."""
        bad_request_errors = [
            "bad request format",
            "invalid request parameters",
            "malformed prompt input",
            "unsupported parameter",
            "invalid inference configuration"
        ]

        for message in bad_request_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"

    def test_configuration_errors(self):
        """Test permanent configuration errors."""
        config_errors = [
            "configuration error in model setup",
            "invalid model configuration",
            "misconfigured server settings",
            "configuration not found"
        ]

        for message in config_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"

    def test_not_found_errors(self):
        """Test permanent resource not found errors."""
        not_found_errors = [
            "endpoint not found",
            "resource not found on server",
            "404 not found",
            "requested resource does not exist"
        ]

        for message in not_found_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"

    def test_permanent_error_case_insensitive(self):
        """Test that permanent error detection is case insensitive."""
        case_variations = [
            "MODEL NOT FOUND",
            "Model Not Found",
            "AUTHENTICATION FAILED",
            "Authentication Failed",
            "CONFIGURATION ERROR",
            "Configuration Error",
            "BAD REQUEST"
        ]

        for message in case_variations:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"


class TestSelfHostedLLMErrorClassifierTransientErrors:
    """Test SelfHostedLLMErrorClassifier transient error detection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = SelfHostedLLMErrorClassifier()

    def test_timeout_errors(self):
        """Test transient timeout errors."""
        timeout_errors = [
            "request timeout occurred",
            "inference timeout exceeded",
            "generation timeout",
            "model response timeout",
            "connection timeout to server"
        ]

        for message in timeout_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"

    def test_connection_errors(self):
        """Test transient connection errors."""
        connection_errors = [
            "connection failed to server",
            "connection refused by host",
            "connection reset during inference",
            "network connection lost",
            "unable to establish connection"
        ]

        for message in connection_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"

    def test_server_error_patterns(self):
        """Test transient server error patterns."""
        server_errors = [
            "internal server error occurred",
            "server error during inference",
            "internal error in model",
            "server side error",
            "backend service error"
        ]

        for message in server_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"

    def test_service_unavailable_errors(self):
        """Test transient service unavailable errors."""
        unavailable_errors = [
            "service unavailable",
            "service temporarily unavailable",
            "server unavailable for inference",
            "temporarily unavailable"
        ]

        for message in unavailable_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"

    def test_memory_errors(self):
        """Test transient memory-related errors."""
        memory_errors = [
            "out of memory during inference",
            "OOM error occurred",
            "insufficient memory for model",
            "memory allocation failed",
            "CUDA out of memory"
        ]

        for message in memory_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"

    def test_resource_errors(self):
        """Test transient resource errors."""
        resource_errors = [
            "insufficient resources available",
            "resource allocation failed",
            "GPU resources busy",
            "resource temporarily unavailable",
            "system resources exhausted"
        ]

        for message in resource_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"

    def test_busy_errors(self):
        """Test transient busy/processing errors."""
        busy_errors = [
            "server busy with other requests",
            "model currently busy",
            "processing another request",
            "busy generating response"
        ]

        for message in busy_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"

    def test_loading_errors(self):
        """Test transient model loading errors."""
        loading_errors = [
            "model currently loading",
            "loading model weights",
            "model initialization in progress",
            "loading checkpoint"
        ]

        for message in loading_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"

    def test_queue_errors(self):
        """Test transient queue-related errors."""
        queue_errors = [
            "request queued for processing",
            "waiting in inference queue",
            "queue position: 5",
            "queued for GPU allocation"
        ]

        for message in queue_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"

    def test_connection_exception_types(self):
        """Test that connection exception types are classified as transient."""
        connection_exceptions = [
            ConnectionError("Connection failed"),
            TimeoutError("Request timed out"),
            ConnectionResetError("Connection reset"),
            ConnectionRefusedError("Connection refused"),
            ConnectionAbortedError("Connection aborted")
        ]

        for error in connection_exceptions:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for error: {type(error).__name__}"

    def test_transient_error_case_insensitive(self):
        """Test that transient error detection is case insensitive."""
        case_variations = [
            "TIMEOUT OCCURRED",
            "Timeout Occurred",
            "CONNECTION FAILED",
            "Connection Failed",
            "OUT OF MEMORY",
            "Out Of Memory",
            "SERVER ERROR"
        ]

        for message in case_variations:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"


class TestSelfHostedLLMErrorClassifierRateLimitErrors:
    """Test SelfHostedLLMErrorClassifier rate limit error detection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = SelfHostedLLMErrorClassifier()

    def test_rate_limit_patterns(self):
        """Test rate limit error patterns."""
        rate_limit_errors = [
            "rate limit exceeded",
            "too many requests to server",
            "request rate too high",
            "rate limiting enforced"
        ]

        for message in rate_limit_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.RATE_LIMIT, f"Failed for message: {message}"

    def test_quota_errors(self):
        """Test quota-related rate limit errors."""
        quota_errors = [
            "quota exceeded for user",
            "API quota limit reached",
            "inference quota exhausted",
            "monthly quota exceeded"
        ]

        for message in quota_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.RATE_LIMIT, f"Failed for message: {message}"

    def test_concurrency_limit_errors(self):
        """Test concurrency limit errors."""
        concurrency_errors = [
            "concurrency limit reached",
            "maximum concurrent requests exceeded",
            "concurrent request limit enforced",
            "too many concurrent connections"
        ]

        for message in concurrency_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.RATE_LIMIT, f"Failed for message: {message}"

    def test_queue_full_errors(self):
        """Test queue full errors (rate limiting indicator)."""
        queue_full_errors = [
            "queue full, cannot accept request",
            "inference queue at capacity",
            "request queue full",
            "maximum queue size reached"
        ]

        for message in queue_full_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.RATE_LIMIT, f"Failed for message: {message}"

    def test_rate_limit_case_insensitive(self):
        """Test that rate limit error detection is case insensitive."""
        case_variations = [
            "RATE LIMIT EXCEEDED",
            "Rate Limit Exceeded",
            "TOO MANY REQUESTS",
            "Too Many Requests",
            "QUOTA EXCEEDED",
            "Quota Exceeded"
        ]

        for message in case_variations:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.RATE_LIMIT, f"Failed for message: {message}"


class TestSelfHostedLLMErrorClassifierOllamaErrors:
    """Test SelfHostedLLMErrorClassifier with Ollama-specific errors."""

    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = SelfHostedLLMErrorClassifier()

    def test_ollama_model_errors(self):
        """Test Ollama model-specific error classification."""
        ollama_errors = [
            ("Ollama: model 'llama2' not found", ErrorCategory.PERMANENT),
            ("Ollama: model not loaded", ErrorCategory.PERMANENT),
            ("Ollama: pulling model in progress", ErrorCategory.TRANSIENT),
            ("Ollama: server connection timeout", ErrorCategory.TRANSIENT),
            ("Ollama: out of memory during inference", ErrorCategory.TRANSIENT)
        ]

        for message, expected_category in ollama_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"

    def test_ollama_server_errors(self):
        """Test Ollama server error classification."""
        server_errors = [
            ("Ollama server not responding", ErrorCategory.TRANSIENT),
            ("Ollama: service unavailable", ErrorCategory.TRANSIENT),
            ("Ollama server internal error", ErrorCategory.TRANSIENT)
        ]

        for message, expected_category in server_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"


class TestSelfHostedLLMErrorClassifierLocalModelErrors:
    """Test SelfHostedLLMErrorClassifier with local model errors."""

    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = SelfHostedLLMErrorClassifier()

    def test_cuda_errors(self):
        """Test CUDA-related error classification."""
        cuda_errors = [
            ("CUDA out of memory", ErrorCategory.TRANSIENT),
            ("CUDA initialization failed", ErrorCategory.TRANSIENT),
            ("CUDA device unavailable", ErrorCategory.TRANSIENT),
            ("GPU memory exhausted", ErrorCategory.TRANSIENT)
        ]

        for message, expected_category in cuda_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"

    def test_model_loading_errors(self):
        """Test model loading error classification."""
        loading_errors = [
            ("Loading model checkpoint", ErrorCategory.TRANSIENT),
            ("Model weights loading in progress", ErrorCategory.TRANSIENT),
            ("Initializing model on GPU", ErrorCategory.TRANSIENT)
        ]

        for message, expected_category in loading_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"

    def test_hardware_resource_errors(self):
        """Test hardware resource error classification."""
        hardware_errors = [
            ("Insufficient GPU memory", ErrorCategory.TRANSIENT),
            ("CPU resources exhausted", ErrorCategory.TRANSIENT),
            ("System memory limit reached", ErrorCategory.TRANSIENT),
            ("GPU utilization at maximum", ErrorCategory.TRANSIENT)
        ]

        for message, expected_category in hardware_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"


class TestSelfHostedLLMErrorClassifierCustomServerErrors:
    """Test SelfHostedLLMErrorClassifier with custom server errors."""

    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = SelfHostedLLMErrorClassifier()

    def test_vllm_errors(self):
        """Test vLLM server error classification."""
        vllm_errors = [
            ("vLLM: engine initialization error", ErrorCategory.TRANSIENT),
            ("vLLM: invalid model name", ErrorCategory.PERMANENT),
            ("vLLM: request queue full", ErrorCategory.RATE_LIMIT),
            ("vLLM: GPU out of memory", ErrorCategory.TRANSIENT)
        ]

        for message, expected_category in vllm_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"

    def test_text_generation_inference_errors(self):
        """Test Text Generation Inference server errors."""
        tgi_errors = [
            ("TGI: model not found in repository", ErrorCategory.PERMANENT),
            ("TGI: inference timeout", ErrorCategory.TRANSIENT),
            ("TGI: server busy", ErrorCategory.TRANSIENT),
            ("TGI: concurrency limit reached", ErrorCategory.RATE_LIMIT)
        ]

        for message, expected_category in tgi_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"

    def test_custom_api_errors(self):
        """Test custom API server errors."""
        api_errors = [
            ("Custom API: authentication required", ErrorCategory.PERMANENT),
            ("Custom API: temporary maintenance", ErrorCategory.TRANSIENT),
            ("Custom API: rate limit exceeded", ErrorCategory.RATE_LIMIT),
            ("Custom API: invalid endpoint", ErrorCategory.PERMANENT)
        ]

        for message, expected_category in api_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for message: {message}"


class TestSelfHostedLLMErrorClassifierEdgeCases:
    """Test SelfHostedLLMErrorClassifier edge cases and error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = SelfHostedLLMErrorClassifier()

    def test_empty_error_message(self):
        """Test handling of errors with empty messages."""
        empty_errors = [
            Exception(""),
            RuntimeError(""),
            ValueError("")
        ]

        for error in empty_errors:
            result = self.classifier.classify_error(error)
            # Should default to transient (conservative for self-hosted)
            assert result == ErrorCategory.TRANSIENT

    def test_none_error_handling(self):
        """Test handling of None error."""
        try:
            result = self.classifier.classify_error(None)
            assert result == ErrorCategory.TRANSIENT
        except (TypeError, AttributeError):
            # Acceptable if implementation doesn't handle None
            pass

    def test_mixed_pattern_errors(self):
        """Test errors that match multiple patterns."""
        mixed_pattern_errors = [
            "model not found due to timeout",  # Permanent + transient patterns
            "rate limit - connection timeout",  # Rate limit + transient
            "authentication failed - server busy"  # Permanent + transient
        ]

        for message in mixed_pattern_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert isinstance(result, ErrorCategory)
            # Priority should be: rate limit > permanent > transient

    def test_unicode_error_messages(self):
        """Test handling of Unicode error messages."""
        unicode_errors = [
            Exception("模型未找到 (model not found)"),
            Exception("Модель не найдена (model not found)"),
            Exception("Timeout: 超时错误")
        ]

        for error in unicode_errors:
            result = self.classifier.classify_error(error)
            assert isinstance(result, ErrorCategory)

    def test_very_long_error_messages(self):
        """Test handling of very long error messages."""
        long_message = "timeout occurred " * 1000
        error = Exception(long_message)
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT

    def test_error_message_with_special_characters(self):
        """Test handling of error messages with special characters."""
        special_char_errors = [
            Exception("model not found: @#$%^&*()"),
            Exception("timeout [model: llama-2-7b]"),
            Exception("rate limit {user_id: 12345}")
        ]

        expected = [ErrorCategory.PERMANENT, ErrorCategory.TRANSIENT, ErrorCategory.RATE_LIMIT]

        for error, expected_category in zip(special_char_errors, expected):
            result = self.classifier.classify_error(error)
            assert result == expected_category


class TestSelfHostedLLMErrorClassifierDefaultBehavior:
    """Test SelfHostedLLMErrorClassifier default behavior and decision priority."""

    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = SelfHostedLLMErrorClassifier()

    def test_default_classification_for_unknown_errors(self):
        """Test default classification for unknown self-hosted errors."""
        unknown_errors = [
            Exception("Unknown LLM error"),
            Exception("Mysterious inference failure"),
            ValueError("Non-LLM related error"),
            RuntimeError("Generic runtime error")
        ]

        for error in unknown_errors:
            result = self.classifier.classify_error(error)
            # Should default to transient (hardware issues often transient)
            assert result == ErrorCategory.TRANSIENT

    def test_rate_limit_takes_priority(self):
        """Test that rate limit classification takes highest priority."""
        # Error with both rate limit and permanent indicators
        mixed_error = Exception("rate limit exceeded - model not found")
        result = self.classifier.classify_error(mixed_error)
        assert result == ErrorCategory.RATE_LIMIT

    def test_permanent_takes_priority_over_transient(self):
        """Test that permanent classification takes priority over transient."""
        # Error with both permanent and transient indicators
        mixed_error = Exception("model not found - connection timeout")
        result = self.classifier.classify_error(mixed_error)
        assert result == ErrorCategory.PERMANENT

    def test_classification_consistency(self):
        """Test that classification is consistent for the same error."""
        error = Exception("model not loaded on server")

        # Should return same result multiple times
        result1 = self.classifier.classify_error(error)
        result2 = self.classifier.classify_error(error)
        result3 = self.classifier.classify_error(error)

        assert result1 == result2 == result3
        assert result1 == ErrorCategory.PERMANENT


class TestSelfHostedLLMErrorClassifierIntegrationScenarios:
    """Test SelfHostedLLMErrorClassifier with realistic integration scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = SelfHostedLLMErrorClassifier()

    def test_ollama_deployment_scenarios(self):
        """Test classification for common Ollama deployment scenarios."""
        ollama_scenarios = [
            ("Ollama: Failed to pull model 'mistral'", ErrorCategory.TRANSIENT),
            ("Ollama: Model 'llama2' not in library", ErrorCategory.PERMANENT),
            ("Ollama: Connection refused on port 11434", ErrorCategory.TRANSIENT),
            ("Ollama: Inference timeout after 60s", ErrorCategory.TRANSIENT),
            ("Ollama: Invalid model parameters", ErrorCategory.PERMANENT)
        ]

        for message, expected_category in ollama_scenarios:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for scenario: {message}"

    def test_local_gpu_inference_scenarios(self):
        """Test classification for local GPU inference scenarios."""
        gpu_scenarios = [
            ("CUDA out of memory during batch inference", ErrorCategory.TRANSIENT),
            ("GPU driver initialization failed", ErrorCategory.TRANSIENT),
            ("Model checkpoint file not found", ErrorCategory.PERMANENT),
            ("Unsupported model architecture", ErrorCategory.PERMANENT),
            ("GPU busy with another process", ErrorCategory.TRANSIENT)
        ]

        for message, expected_category in gpu_scenarios:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for scenario: {message}"

    def test_custom_server_deployment_scenarios(self):
        """Test classification for custom server deployment scenarios."""
        server_scenarios = [
            ("Server authentication token expired", ErrorCategory.PERMANENT),
            ("Server temporarily overloaded", ErrorCategory.TRANSIENT),
            ("Server rate limiting active", ErrorCategory.RATE_LIMIT),
            ("Invalid API endpoint path", ErrorCategory.PERMANENT),
            ("Server maintenance mode", ErrorCategory.TRANSIENT)
        ]

        for message, expected_category in server_scenarios:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for scenario: {message}"

    def test_model_serving_framework_scenarios(self):
        """Test classification across different model serving frameworks."""
        framework_scenarios = [
            ("vLLM: Request queue at capacity", ErrorCategory.RATE_LIMIT),
            ("TGI: Model weights corrupted", ErrorCategory.PERMANENT),
            ("Ray Serve: Worker crashed", ErrorCategory.TRANSIENT),
            ("Triton: Invalid model configuration", ErrorCategory.PERMANENT),
            ("FastAPI: Internal server error", ErrorCategory.TRANSIENT)
        ]

        for message, expected_category in framework_scenarios:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for scenario: {message}"
