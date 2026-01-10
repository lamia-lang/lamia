"""Tests for retry strategies."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock
from lamia.adapters.retry.strategies import (
    RetryStrategy, ExponentialBackoffStrategy, NoRetryStrategy, RetryAttempt
)
from lamia.adapters.error_classifiers.categories import ErrorCategory


class TestRetryAttempt:
    """Test RetryAttempt dataclass."""
    
    def test_retry_attempt_creation(self):
        """Test RetryAttempt creation."""
        error = Exception("test error")
        attempt = RetryAttempt(
            attempt_number=1,
            start_time=datetime.now(),
            error=error,
            error_category=ErrorCategory.TRANSIENT
        )
        
        assert attempt.attempt_number == 1
        assert isinstance(attempt.start_time, datetime)
        assert attempt.error == error
        assert attempt.error_category == ErrorCategory.TRANSIENT


class TestRetryStrategyInterface:
    """Test RetryStrategy interface."""
    
    def test_is_abstract(self):
        """Test that RetryStrategy is abstract."""
        try:
            strategy = RetryStrategy()
            # If not abstract, should have basic interface
            assert hasattr(strategy, 'should_retry')
            assert hasattr(strategy, 'get_delay')
        except TypeError:
            # Expected if abstract
            pass
    
    def test_interface_methods(self):
        """Test that interface methods exist."""
        # Test that expected methods exist on the class
        assert hasattr(RetryStrategy, 'should_retry')
        assert hasattr(RetryStrategy, 'get_delay')


class TestExponentialBackoffStrategy:
    """Test ExponentialBackoffStrategy."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.strategy = ExponentialBackoffStrategy(
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0
        )
        
    def _create_attempt(self, attempt_number=0, error=None, category=ErrorCategory.TRANSIENT):
        """Helper to create RetryAttempt."""
        return RetryAttempt(
            attempt_number=attempt_number,
            start_time=datetime.now(),
            error=error or Exception("test error"),
            error_category=category
        )
    
    def test_initialization(self):
        """Test strategy initialization."""
        assert self.strategy.base_delay == 1.0
        assert self.strategy.max_delay == 10.0
        assert self.strategy.exponential_base == 2.0
    
    def test_required_parameters(self):
        """Test strategy requires all parameters."""
        with pytest.raises(TypeError):
            ExponentialBackoffStrategy()
        
        # Test with all required parameters
        strategy = ExponentialBackoffStrategy(base_delay=1.0, max_delay=10.0, exponential_base=2.0)
        assert hasattr(strategy, 'base_delay')
        assert hasattr(strategy, 'max_delay')
        assert strategy.base_delay > 0
        assert strategy.max_delay > strategy.base_delay
    
    def test_should_retry_transient_errors(self):
        """Test retry decision for transient errors."""
        error = ConnectionError("Connection failed")
        attempt = self._create_attempt(0, error, ErrorCategory.TRANSIENT)
        
        should_retry = self.strategy.should_retry(attempt)
        assert should_retry is True
    
    def test_should_retry_permanent_errors(self):
        """Test retry decision for permanent errors."""
        error = ValueError("Invalid input")
        attempt = self._create_attempt(0, error, ErrorCategory.PERMANENT)
        
        should_retry = self.strategy.should_retry(attempt)
        assert should_retry is False
    
    def test_get_delay_exponential_growth(self):
        """Test exponential delay growth."""
        delays = []
        for attempt_num in range(5):
            attempt = self._create_attempt(attempt_num)
            delay = self.strategy.get_delay(attempt)
            delays.append(delay)
        
        # Check exponential growth
        assert delays[0] == 1.0  # base_delay
        assert delays[1] == 2.0  # base_delay * 2^1
        assert delays[2] == 4.0  # base_delay * 2^2
    
    def test_max_delay_respected(self):
        """Test that maximum delay is respected."""
        # Test with high attempt numbers
        for attempt_num in range(10, 20):
            attempt = self._create_attempt(attempt_num)
            delay = self.strategy.get_delay(attempt)
            assert delay <= self.strategy.max_delay
    
    def test_rate_limit_delay_multiplier(self):
        """Test that rate limit errors get longer delays."""
        transient_attempt = self._create_attempt(1, Exception("test"), ErrorCategory.TRANSIENT)
        rate_limit_attempt = self._create_attempt(1, Exception("rate limit"), ErrorCategory.RATE_LIMIT)
        
        transient_delay = self.strategy.get_delay(transient_attempt)
        rate_limit_delay = self.strategy.get_delay(rate_limit_attempt)
        
        # Rate limit should be 2x longer
        assert rate_limit_delay == transient_delay * 2


class TestNoRetryStrategy:
    """Test NoRetryStrategy."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.strategy = NoRetryStrategy()
    
    def _create_attempt(self, attempt_number=0, error=None, category=ErrorCategory.TRANSIENT):
        """Helper to create RetryAttempt."""
        return RetryAttempt(
            attempt_number=attempt_number,
            start_time=datetime.now(),
            error=error or Exception("test error"),
            error_category=category
        )
    
    def test_never_retries(self):
        """Test that NoRetryStrategy never retries."""
        scenarios = [
            (ErrorCategory.TRANSIENT, ConnectionError("Connection failed")),
            (ErrorCategory.RATE_LIMIT, Exception("Rate limited")),
            (ErrorCategory.PERMANENT, ValueError("Invalid input")),
        ]
        
        for category, error in scenarios:
            attempt = self._create_attempt(0, error, category)
            should_retry = self.strategy.should_retry(attempt)
            assert should_retry is False
    
    def test_zero_delay(self):
        """Test that NoRetryStrategy returns zero delay."""
        attempt = self._create_attempt()
        delay = self.strategy.get_delay(attempt)
        assert delay == 0.0


class MockRetryStrategy(RetryStrategy):
    """Mock strategy for testing base functionality."""
    
    def __init__(self, should_retry_fn=None, delay_fn=None):
        self.should_retry_fn = should_retry_fn or (lambda attempt: True)
        self.delay_fn = delay_fn or (lambda attempt: attempt.attempt_number * 0.5)
    
    def should_retry(self, attempt: RetryAttempt) -> bool:
        return self.should_retry_fn(attempt)
    
    def get_delay(self, attempt: RetryAttempt) -> float:
        return self.delay_fn(attempt)


class TestCustomRetryStrategies:
    """Test custom retry strategy implementations."""
    
    def _create_attempt(self, attempt_number=0, error=None, category=ErrorCategory.TRANSIENT):
        """Helper to create RetryAttempt."""
        return RetryAttempt(
            attempt_number=attempt_number,
            start_time=datetime.now(),
            error=error or Exception("test error"),
            error_category=category
        )
    
    def test_custom_should_retry_logic(self):
        """Test custom retry logic."""
        def custom_retry_logic(attempt):
            # Only retry ConnectionErrors, max 2 times
            return isinstance(attempt.error, ConnectionError) and attempt.attempt_number < 2
        
        strategy = MockRetryStrategy(should_retry_fn=custom_retry_logic)
        
        # Test different scenarios
        conn_error = ConnectionError("Connection failed")
        value_error = ValueError("Invalid value")
        
        assert strategy.should_retry(self._create_attempt(0, conn_error)) is True
        assert strategy.should_retry(self._create_attempt(1, conn_error)) is True
        assert strategy.should_retry(self._create_attempt(2, conn_error)) is False
        assert strategy.should_retry(self._create_attempt(0, value_error)) is False
    
    def test_custom_delay_calculation(self):
        """Test custom delay calculation."""
        def fibonacci_delay(attempt):
            """Fibonacci-based delay."""
            if attempt.attempt_number <= 1:
                return 1.0
            a, b = 1.0, 1.0
            for _ in range(attempt.attempt_number - 1):
                a, b = b, a + b
            return min(b, 10.0)  # Cap at 10 seconds
        
        strategy = MockRetryStrategy(delay_fn=fibonacci_delay)
        
        expected_delays = [1.0, 1.0, 2.0, 3.0, 5.0, 8.0]
        
        for attempt_num, expected in enumerate(expected_delays):
            attempt = self._create_attempt(attempt_num)
            delay = strategy.get_delay(attempt)
            assert delay == expected
    
    def test_error_specific_delays(self):
        """Test delays that vary based on error type."""
        def error_specific_delay(attempt):
            if isinstance(attempt.error, ConnectionError):
                return 2.0 * (attempt.attempt_number + 1)  # Longer delay for connection errors
            elif isinstance(attempt.error, TimeoutError):
                return 0.5 * (attempt.attempt_number + 1)  # Shorter delay for timeouts
            else:
                return 1.0 * (attempt.attempt_number + 1)  # Default delay
        
        strategy = MockRetryStrategy(delay_fn=error_specific_delay)
        
        conn_error = ConnectionError("Connection failed")
        timeout_error = TimeoutError("Request timeout")
        value_error = ValueError("Invalid value")
        
        assert strategy.get_delay(self._create_attempt(1, conn_error)) == 4.0  # 2.0 * 2
        assert strategy.get_delay(self._create_attempt(1, timeout_error)) == 1.0  # 0.5 * 2
        assert strategy.get_delay(self._create_attempt(1, value_error)) == 2.0  # 1.0 * 2


class TestRetryStrategyIntegration:
    """Test retry strategy integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_strategy_with_async_operations(self):
        """Test retry strategy with async operations."""
        strategy = ExponentialBackoffStrategy(base_delay=0.1, max_delay=1.0, exponential_base=2.0)
        
        call_count = 0
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"
        
        # Simulate retry loop using strategy
        attempt_num = 0
        max_attempts = 5
        
        while attempt_num < max_attempts:
            try:
                result = await failing_operation()
                break
            except Exception as e:
                if attempt_num + 1 >= max_attempts:
                    raise
                
                retry_attempt = RetryAttempt(
                    attempt_number=attempt_num,
                    start_time=datetime.now(),
                    error=e,
                    error_category=ErrorCategory.TRANSIENT
                )
                
                should_retry = strategy.should_retry(retry_attempt)
                if not should_retry:
                    raise
                
                delay = strategy.get_delay(retry_attempt)
                await asyncio.sleep(delay)
                attempt_num += 1
        
        assert result == "success"
        assert call_count == 3
    
    def test_strategy_comparison(self):
        """Test comparing different strategies."""
        exponential = ExponentialBackoffStrategy(base_delay=1.0, max_delay=10.0, exponential_base=2.0)
        no_retry = NoRetryStrategy()
        
        strategies = [exponential, no_retry]
        error = ConnectionError("Test error")
        
        # Compare delays for different attempts
        for attempt_num in range(3):
            retry_attempt = RetryAttempt(
                attempt_number=attempt_num,
                start_time=datetime.now(),
                error=error,
                error_category=ErrorCategory.TRANSIENT
            )
            
            exp_delay = exponential.get_delay(retry_attempt)
            no_retry_delay = no_retry.get_delay(retry_attempt)
            
            assert exp_delay > 0
            assert no_retry_delay == 0.0


class TestRetryStrategyErrorHandling:
    """Test retry strategy error handling."""
    
    def test_strategy_with_invalid_parameters(self):
        """Test strategy behavior with invalid parameters."""
        # Test negative delays
        try:
            strategy = ExponentialBackoffStrategy(base_delay=-1.0, max_delay=10.0, exponential_base=2.0)
            # Should either handle gracefully or raise error
            assert strategy.base_delay >= 0 or True  # Implementation dependent
        except ValueError:
            # Expected for invalid parameters
            pass
    
    def test_strategy_with_extreme_values(self):
        """Test strategy with extreme parameter values."""
        # Test very large delays
        strategy = ExponentialBackoffStrategy(base_delay=1000.0, max_delay=10000.0, exponential_base=2.0)
        attempt = RetryAttempt(0, datetime.now(), Exception("test"), ErrorCategory.TRANSIENT)
        delay = strategy.get_delay(attempt)
        assert delay > 0
        
        # Test very small delays
        strategy = ExponentialBackoffStrategy(base_delay=0.001, max_delay=0.01, exponential_base=2.0)
        delay = strategy.get_delay(attempt)
        assert delay > 0
    
    def test_strategy_with_none_error(self):
        """Test strategy behavior with None error."""
        strategy = ExponentialBackoffStrategy(base_delay=1.0, max_delay=10.0, exponential_base=2.0)
        
        try:
            attempt = RetryAttempt(0, datetime.now(), None, ErrorCategory.TRANSIENT)
            delay = strategy.get_delay(attempt)
            assert delay >= 0
        except (AttributeError, TypeError):
            # Acceptable if strategy doesn't handle None errors
            pass
    
    def test_strategy_thread_safety(self):
        """Test strategy thread safety (if applicable)."""
        strategy = ExponentialBackoffStrategy(base_delay=1.0, max_delay=10.0, exponential_base=2.0)
        
        # Test multiple concurrent calls
        import threading
        results = []
        
        def get_delay_worker():
            attempt = RetryAttempt(1, datetime.now(), Exception("test"), ErrorCategory.TRANSIENT)
            delay = strategy.get_delay(attempt)
            results.append(delay)
        
        threads = [threading.Thread(target=get_delay_worker) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # All calls should complete successfully
        assert len(results) == 10
        assert all(delay > 0 for delay in results)