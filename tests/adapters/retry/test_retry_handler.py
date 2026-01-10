"""Tests for retry handler."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from lamia.adapters.retry.retry_handler import RetryHandler, RetryStats
from lamia.adapters.retry.strategies import RetryStrategy
from lamia.adapters.error_classifiers.categories import ErrorCategory
from lamia.adapters.llm.base import BaseLLMAdapter
from lamia.errors import ExternalOperationError, ExternalOperationTransientError, ExternalOperationPermanentError
from lamia.types import ExternalOperationRetryConfig
from datetime import timedelta


class MockLLMAdapter(BaseLLMAdapter):
    """Mock LLM adapter for testing."""
    
    @property
    def name(self) -> str:
        return "mock_adapter"
    
    def is_remote(self) -> bool:
        return True
    
    async def complete(self, *args, **kwargs):
        return "test completion"
    
    async def generate(self, *args, **kwargs):
        return "test generation"
    
    async def close(self):
        pass


class TestRetryHandlerInitialization:
    """Test RetryHandler initialization."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_adapter = MockLLMAdapter()
    
    def test_basic_initialization(self):
        """Test basic RetryHandler initialization."""
        handler = RetryHandler(self.mock_adapter)
        
        assert handler.config is not None
        assert handler.error_classifier is not None
        assert isinstance(handler.stats, RetryStats)
    
    def test_initialization_with_custom_config(self):
        """Test RetryHandler with custom config."""
        config = ExternalOperationRetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=30.0,
            exponential_base=3.0,
            max_total_duration=timedelta(minutes=5)
        )
        handler = RetryHandler(self.mock_adapter, config=config)
        
        assert handler.config == config
        assert handler.config.max_attempts == 5
        assert handler.config.base_delay == 2.0
    
    def test_initialization_without_stats(self):
        """Test RetryHandler initialization without stats collection."""
        handler = RetryHandler(self.mock_adapter, collect_stats=False)
        
        assert handler.stats is None


class TestRetryHandlerExecution:
    """Test RetryHandler execution logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_adapter = MockLLMAdapter()
        config = ExternalOperationRetryConfig(
            max_attempts=3,
            base_delay=0.1,
            max_delay=1.0,
            exponential_base=2.0,
            max_total_duration=timedelta(seconds=30)
        )
        self.handler = RetryHandler(self.mock_adapter, config=config)
    
    @pytest.mark.asyncio
    async def test_successful_execution_no_retry(self):
        """Test successful execution without retries."""
        mock_operation = AsyncMock(return_value="success")
        
        result = await self.handler.execute(mock_operation)
        
        assert result == "success"
        mock_operation.assert_called_once()
        
        # Check stats
        stats = self.handler.get_stats()
        assert stats.total_operations == 1
        assert stats.successful_operations == 1
        assert stats.failed_operations == 0
    
    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        """Test retry behavior on transient errors."""
        mock_operation = AsyncMock()
        mock_operation.side_effect = [
            ExternalOperationTransientError("Transient error", []),
            ExternalOperationTransientError("Another transient error", []),
            "success"
        ]
        
        result = await self.handler.execute(mock_operation)
        
        assert result == "success"
        assert mock_operation.call_count == 3
        
        # Check stats
        stats = self.handler.get_stats()
        assert stats.total_operations == 1
        assert stats.successful_operations == 1
        assert stats.total_retries == 2
    
    @pytest.mark.asyncio
    async def test_no_retry_on_permanent_error(self):
        """Test no retry on permanent errors."""
        mock_operation = AsyncMock(side_effect=ExternalOperationPermanentError("Permanent error", []))
        
        with pytest.raises(ExternalOperationPermanentError, match="Permanent error"):
            await self.handler.execute(mock_operation)
        
        mock_operation.assert_called_once()
        
        # Check stats
        stats = self.handler.get_stats()
        assert stats.total_operations == 1
        assert stats.failed_operations == 1
        assert stats.total_retries == 0
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        mock_operation = AsyncMock(side_effect=ExternalOperationTransientError("Persistent error", []))
        
        with pytest.raises(ExternalOperationTransientError, match="Persistent error"):
            await self.handler.execute(mock_operation)
        
        # Should try max_attempts times
        assert mock_operation.call_count == self.handler.config.max_attempts
        
        # Check stats
        stats = self.handler.get_stats()
        assert stats.total_operations == 1
        assert stats.failed_operations == 1
        assert stats.total_retries == self.handler.config.max_attempts - 1
    
    @pytest.mark.asyncio
    async def test_programming_error_not_retried(self):
        """Test that programming errors (non-ExternalOperationError) are not retried."""
        mock_operation = AsyncMock(side_effect=ValueError("Programming error"))
        
        with pytest.raises(ValueError, match="Programming error"):
            await self.handler.execute(mock_operation)
        
        # Should only be called once - no retries for programming errors
        mock_operation.assert_called_once()


class TestRetryHandlerBackoff:
    """Test retry handler backoff strategies."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_adapter = MockLLMAdapter()
        config = ExternalOperationRetryConfig(
            max_attempts=4,
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            max_total_duration=timedelta(seconds=60)
        )
        self.handler = RetryHandler(self.mock_adapter, config=config)
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff delay calculation."""
        mock_operation = AsyncMock(side_effect=[
            ExternalOperationTransientError("Error 1", []),
            ExternalOperationTransientError("Error 2", []),
            ExternalOperationTransientError("Error 3", []),
            "success"
        ])
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await self.handler.execute(mock_operation)
            
            assert result == "success"
            
            # Check that delays increased (exponential backoff)
            sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
            assert len(sleep_calls) == 3  # 3 retries
            assert sleep_calls[1] > sleep_calls[0]  # Exponential increase
            assert sleep_calls[2] > sleep_calls[1]
    
    @pytest.mark.asyncio
    async def test_delay_calculation(self):
        """Test delay calculation based on attempt number."""
        mock_operation = AsyncMock(side_effect=[
            ExternalOperationTransientError("Error", []),
            "success"
        ])
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await self.handler.execute(mock_operation)
            
            assert result == "success"
            assert mock_operation.call_count == 2
            
            # Check delay was calculated correctly (base_delay * exponential_base^0)
            assert len(mock_sleep.call_args_list) == 1
            delay = mock_sleep.call_args_list[0].args[0]
            assert delay == 1.0  # base_delay for first retry


class TestRetryHandlerStats:
    """Test retry handler statistics functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_adapter = MockLLMAdapter()
        config = ExternalOperationRetryConfig(
            max_attempts=3,
            base_delay=0.1,
            max_delay=1.0,
            exponential_base=2.0,
            max_total_duration=timedelta(seconds=30)
        )
        self.handler = RetryHandler(self.mock_adapter, config=config)
    
    @pytest.mark.asyncio
    async def test_stats_collection(self):
        """Test statistics collection during operations."""
        mock_operation = AsyncMock()
        mock_operation.side_effect = [
            ExternalOperationTransientError("Error 1", []),
            "success"
        ]
        
        result = await self.handler.execute(mock_operation)
        
        assert result == "success"
        
        stats = self.handler.get_stats()
        assert stats.total_operations == 1
        assert stats.successful_operations == 1
        assert stats.failed_operations == 0
        assert stats.total_retries == 1
        assert stats.total_operation_time > 0
        assert "ExternalOperationTransientError" in stats.errors_by_type
        assert len(stats.error_history) == 1
    
    @pytest.mark.asyncio
    async def test_stats_disabled(self):
        """Test handler with stats collection disabled."""
        handler = RetryHandler(self.mock_adapter, collect_stats=False)
        
        mock_operation = AsyncMock(return_value="success")
        result = await handler.execute(mock_operation)
        
        assert result == "success"
        assert handler.get_stats() is None


class TestRetryHandlerEdgeCases:
    """Test retry handler edge cases."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_adapter = MockLLMAdapter()
        config = ExternalOperationRetryConfig(
            max_attempts=2,
            base_delay=0.1,
            max_delay=1.0,
            exponential_base=2.0,
            max_total_duration=timedelta(seconds=15)
        )
        self.handler = RetryHandler(self.mock_adapter, config=config)
    
    @pytest.mark.asyncio
    async def test_operation_returns_none(self):
        """Test operation that returns None."""
        mock_operation = AsyncMock(return_value=None)
        
        result = await self.handler.execute(mock_operation)
        
        assert result is None
        mock_operation.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_operation_returns_false(self):
        """Test operation that returns False."""
        mock_operation = AsyncMock(return_value=False)
        
        result = await self.handler.execute(mock_operation)
        
        assert result is False
        mock_operation.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_operation_with_lambda(self):
        """Test operation that uses lambda."""
        async def complex_operation(a, b, c=None):
            if a == "fail":
                raise ValueError("Test error")
            return f"{a}-{b}-{c}"
        
        result = await self.handler.execute(
            lambda: complex_operation("success", "test", c="param")
        )
        
        assert result == "success-test-param"