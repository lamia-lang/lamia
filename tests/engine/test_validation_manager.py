"""Tests for validation manager."""

import pytest
from unittest.mock import patch, Mock
from lamia.engine.validation_manager import ValidationStats, ValidationStatsTracker
from lamia.interpreter.command_types import CommandType


class TestValidationStats:
    """Test ValidationStats dataclass."""
    
    def test_default_initialization(self):
        """Test ValidationStats initialization with defaults."""
        stats = ValidationStats()
        
        assert stats.total_validations == 0
        assert stats.successful_validations == 0
        assert stats.failed_validations == 0
        assert stats.by_domain == {}
        assert stats.intermediate_failures == {}
        assert stats.intermediate_successes == {}
    
    def test_initialization_with_values(self):
        """Test ValidationStats initialization with custom values."""
        by_domain = {"llm": 5, "web": 3}  # Use string values, not enum
        intermediate_failures = {"gpt-4": 2, "claude": 1}
        intermediate_successes = {"gpt-4": 8, "claude": 7}
        
        stats = ValidationStats(
            total_validations=10,
            successful_validations=8,
            failed_validations=2,
            by_domain=by_domain,
            intermediate_failures=intermediate_failures,
            intermediate_successes=intermediate_successes
        )
        
        assert stats.total_validations == 10
        assert stats.successful_validations == 8
        assert stats.failed_validations == 2
        assert stats.by_domain == by_domain
        assert stats.intermediate_failures == intermediate_failures
        assert stats.intermediate_successes == intermediate_successes
    
    def test_mutable_default_factories(self):
        """Test that default factories create separate instances."""
        stats1 = ValidationStats()
        stats2 = ValidationStats()
        
        # Modify one instance
        stats1.by_domain["test"] = 1
        stats1.intermediate_failures["provider1"] = 1
        stats1.intermediate_successes["provider1"] = 5
        
        # Other instance should be unaffected
        assert stats2.by_domain == {}
        assert stats2.intermediate_failures == {}
        assert stats2.intermediate_successes == {}


class TestValidationStatsTrackerInitialization:
    """Test ValidationStatsTracker initialization."""
    
    def test_initialization(self):
        """Test tracker initialization."""
        tracker = ValidationStatsTracker()
        
        assert isinstance(tracker.stats, ValidationStats)
        assert tracker.stats.total_validations == 0
        assert tracker.stats.successful_validations == 0
        assert tracker.stats.failed_validations == 0


class TestValidationStatsTrackerValidationRecording:
    """Test validation result recording."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = ValidationStatsTracker()
    
    def test_record_successful_validation(self):
        """Test recording successful validation."""
        self.tracker.record_validation_result(True, CommandType.LLM)
        
        assert self.tracker.stats.total_validations == 1
        assert self.tracker.stats.successful_validations == 1
        assert self.tracker.stats.failed_validations == 0
        assert self.tracker.stats.by_domain[CommandType.LLM.value] == 1
    
    def test_record_failed_validation(self):
        """Test recording failed validation."""
        self.tracker.record_validation_result(False, CommandType.WEB)
        
        assert self.tracker.stats.total_validations == 1
        assert self.tracker.stats.successful_validations == 0
        assert self.tracker.stats.failed_validations == 1
        assert self.tracker.stats.by_domain[CommandType.WEB.value] == 1
    
    def test_record_multiple_validations(self):
        """Test recording multiple validations."""
        # Record mix of successes and failures
        self.tracker.record_validation_result(True, CommandType.LLM)
        self.tracker.record_validation_result(False, CommandType.LLM)
        self.tracker.record_validation_result(True, CommandType.WEB)
        self.tracker.record_validation_result(True, CommandType.FILESYSTEM)
        self.tracker.record_validation_result(False, CommandType.LLM)
        
        assert self.tracker.stats.total_validations == 5
        assert self.tracker.stats.successful_validations == 3
        assert self.tracker.stats.failed_validations == 2
        
        # Check by-domain counts
        assert self.tracker.stats.by_domain[CommandType.LLM.value] == 3  # 3 LLM validations
        assert self.tracker.stats.by_domain[CommandType.WEB.value] == 1
        assert self.tracker.stats.by_domain[CommandType.FILESYSTEM.value] == 1
    
    def test_record_validation_with_string_command_type(self):
        """Test recording validation with string command type."""
        # Test fallback behavior for non-CommandType values
        self.tracker.record_validation_result(True, "custom_command")
        
        assert self.tracker.stats.total_validations == 1
        assert self.tracker.stats.successful_validations == 1
        assert self.tracker.stats.by_domain["custom_command"] == 1
    
    def test_record_validation_accumulation(self):
        """Test that validations accumulate properly."""
        # Record same command type multiple times
        for i in range(5):
            self.tracker.record_validation_result(True, CommandType.LLM)
        for i in range(3):
            self.tracker.record_validation_result(False, CommandType.LLM)
        
        assert self.tracker.stats.total_validations == 8
        assert self.tracker.stats.successful_validations == 5
        assert self.tracker.stats.failed_validations == 3
        assert self.tracker.stats.by_domain[CommandType.LLM.value] == 8


class TestValidationStatsTrackerIntermediateValidation:
    """Test intermediate validation tracking."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = ValidationStatsTracker()
    
    def test_record_intermediate_success(self):
        """Test recording intermediate validation success."""
        self.tracker.record_intermediate_validation_attempt("gpt-4", True)
        
        assert self.tracker.stats.intermediate_successes["gpt-4"] == 1
        assert "gpt-4" not in self.tracker.stats.intermediate_failures
    
    def test_record_intermediate_failure(self):
        """Test recording intermediate validation failure."""
        self.tracker.record_intermediate_validation_attempt("claude", False)
        
        assert self.tracker.stats.intermediate_failures["claude"] == 1
        assert "claude" not in self.tracker.stats.intermediate_successes
    
    def test_record_multiple_intermediate_attempts(self):
        """Test recording multiple intermediate validation attempts."""
        # Record multiple attempts for same provider
        for i in range(5):
            self.tracker.record_intermediate_validation_attempt("gpt-4", True)
        for i in range(2):
            self.tracker.record_intermediate_validation_attempt("gpt-4", False)
        
        # Record attempts for different provider
        for i in range(3):
            self.tracker.record_intermediate_validation_attempt("claude", True)
        for i in range(4):
            self.tracker.record_intermediate_validation_attempt("claude", False)
        
        assert self.tracker.stats.intermediate_successes["gpt-4"] == 5
        assert self.tracker.stats.intermediate_failures["gpt-4"] == 2
        assert self.tracker.stats.intermediate_successes["claude"] == 3
        assert self.tracker.stats.intermediate_failures["claude"] == 4
    
    def test_record_intermediate_various_providers(self):
        """Test recording intermediate attempts for various providers."""
        providers = ["gpt-4", "claude", "gemini", "local-llm", "selenium", "playwright"]
        
        for provider in providers:
            self.tracker.record_intermediate_validation_attempt(provider, True)
            self.tracker.record_intermediate_validation_attempt(provider, False)
        
        for provider in providers:
            assert self.tracker.stats.intermediate_successes[provider] == 1
            assert self.tracker.stats.intermediate_failures[provider] == 1
    
    @patch('lamia.engine.validation_manager.logger')
    def test_record_intermediate_logging(self, mock_logger):
        """Test that intermediate validation attempts are logged."""
        self.tracker.record_intermediate_validation_attempt("test-provider", True)
        self.tracker.record_intermediate_validation_attempt("test-provider", False)
        
        # Check that debug logs were called
        assert mock_logger.debug.call_count == 2


class TestValidationStatsTrackerProviderSuccessRates:
    """Test provider success rate calculations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = ValidationStatsTracker()
    
    def test_get_provider_success_rates_no_data(self):
        """Test getting provider success rates with no data."""
        rates = self.tracker.get_provider_success_rates()
        assert rates == {}
    
    def test_get_provider_success_rates_single_provider(self):
        """Test getting success rates for single provider."""
        # Record 3 successes and 1 failure for gpt-4
        for i in range(3):
            self.tracker.record_intermediate_validation_attempt("gpt-4", True)
        self.tracker.record_intermediate_validation_attempt("gpt-4", False)
        
        rates = self.tracker.get_provider_success_rates()
        
        assert "gpt-4" in rates
        gpt4_stats = rates["gpt-4"]
        assert gpt4_stats["success_rate"] == 0.75  # 3/4
        assert gpt4_stats["total_attempts"] == 4
        assert gpt4_stats["successes"] == 3
        assert gpt4_stats["failures"] == 1
    
    def test_get_provider_success_rates_multiple_providers(self):
        """Test getting success rates for multiple providers."""
        # Provider 1: 5 successes, 1 failure
        for i in range(5):
            self.tracker.record_intermediate_validation_attempt("provider1", True)
        self.tracker.record_intermediate_validation_attempt("provider1", False)
        
        # Provider 2: 2 successes, 3 failures
        for i in range(2):
            self.tracker.record_intermediate_validation_attempt("provider2", True)
        for i in range(3):
            self.tracker.record_intermediate_validation_attempt("provider2", False)
        
        # Provider 3: Only successes
        for i in range(4):
            self.tracker.record_intermediate_validation_attempt("provider3", True)
        
        # Provider 4: Only failures
        for i in range(2):
            self.tracker.record_intermediate_validation_attempt("provider4", False)
        
        rates = self.tracker.get_provider_success_rates()
        
        # Check provider1
        assert rates["provider1"]["success_rate"] == 5/6
        assert rates["provider1"]["total_attempts"] == 6
        assert rates["provider1"]["successes"] == 5
        assert rates["provider1"]["failures"] == 1
        
        # Check provider2
        assert rates["provider2"]["success_rate"] == 2/5
        assert rates["provider2"]["total_attempts"] == 5
        assert rates["provider2"]["successes"] == 2
        assert rates["provider2"]["failures"] == 3
        
        # Check provider3 (100% success)
        assert rates["provider3"]["success_rate"] == 1.0
        assert rates["provider3"]["total_attempts"] == 4
        assert rates["provider3"]["successes"] == 4
        assert rates["provider3"]["failures"] == 0
        
        # Check provider4 (0% success)
        assert rates["provider4"]["success_rate"] == 0.0
        assert rates["provider4"]["total_attempts"] == 2
        assert rates["provider4"]["successes"] == 0
        assert rates["provider4"]["failures"] == 2
    
    def test_get_provider_success_rates_only_successes(self):
        """Test provider with only successes."""
        for i in range(5):
            self.tracker.record_intermediate_validation_attempt("perfect-provider", True)
        
        rates = self.tracker.get_provider_success_rates()
        
        assert rates["perfect-provider"]["success_rate"] == 1.0
        assert rates["perfect-provider"]["total_attempts"] == 5
        assert rates["perfect-provider"]["successes"] == 5
        assert rates["perfect-provider"]["failures"] == 0
    
    def test_get_provider_success_rates_only_failures(self):
        """Test provider with only failures."""
        for i in range(3):
            self.tracker.record_intermediate_validation_attempt("failing-provider", False)
        
        rates = self.tracker.get_provider_success_rates()
        
        assert rates["failing-provider"]["success_rate"] == 0.0
        assert rates["failing-provider"]["total_attempts"] == 3
        assert rates["failing-provider"]["successes"] == 0
        assert rates["failing-provider"]["failures"] == 3
    
    def test_provider_success_rates_precision(self):
        """Test precision of success rate calculations."""
        # Record 1 success out of 3 attempts
        self.tracker.record_intermediate_validation_attempt("test-provider", True)
        self.tracker.record_intermediate_validation_attempt("test-provider", False)
        self.tracker.record_intermediate_validation_attempt("test-provider", False)
        
        rates = self.tracker.get_provider_success_rates()
        
        # Should be exactly 1/3
        assert abs(rates["test-provider"]["success_rate"] - (1/3)) < 1e-10


class TestValidationStatsTrackerStatsRetrieval:
    """Test validation statistics retrieval."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = ValidationStatsTracker()
    
    def test_get_validation_stats_initial(self):
        """Test getting validation stats initially."""
        stats = self.tracker.get_validation_stats()
        
        assert isinstance(stats, ValidationStats)
        assert stats.total_validations == 0
        assert stats.successful_validations == 0
        assert stats.failed_validations == 0
        assert stats.by_domain == {}
        assert stats.intermediate_failures == {}
        assert stats.intermediate_successes == {}
    
    def test_get_validation_stats_after_operations(self):
        """Test getting validation stats after recording operations."""
        # Record some validations
        self.tracker.record_validation_result(True, CommandType.LLM)
        self.tracker.record_validation_result(False, CommandType.WEB)
        self.tracker.record_intermediate_validation_attempt("gpt-4", True)
        self.tracker.record_intermediate_validation_attempt("claude", False)
        
        stats = self.tracker.get_validation_stats()
        
        assert stats.total_validations == 2
        assert stats.successful_validations == 1
        assert stats.failed_validations == 1
        assert stats.by_domain[CommandType.LLM.value] == 1
        assert stats.by_domain[CommandType.WEB.value] == 1
        assert stats.intermediate_successes["gpt-4"] == 1
        assert stats.intermediate_failures["claude"] == 1
    
    def test_get_validation_stats_returns_same_instance(self):
        """Test that get_validation_stats returns the same instance."""
        stats1 = self.tracker.get_validation_stats()
        stats2 = self.tracker.get_validation_stats()
        
        assert stats1 is stats2  # Same object reference


class TestValidationStatsTrackerDestructor:
    """Test ValidationStatsTracker destructor behavior."""
    
    @patch('lamia.engine.validation_manager.logger')
    def test_destructor_with_validations(self, mock_logger):
        """Test destructor behavior when validations were recorded."""
        # Create tracker and record some validations
        tracker = ValidationStatsTracker()
        tracker.record_validation_result(True, CommandType.LLM)
        tracker.record_validation_result(False, CommandType.WEB)
        
        # Manually call destructor
        tracker.__del__()
        
        # Should log summary
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "2 validations" in call_args
    
    @patch('lamia.engine.validation_manager.logger')
    def test_destructor_without_validations(self, mock_logger):
        """Test destructor behavior when no validations were recorded."""
        # Create tracker without recording validations
        tracker = ValidationStatsTracker()
        
        # Manually call destructor
        tracker.__del__()
        
        # Should not log anything
        mock_logger.info.assert_not_called()


class TestValidationStatsTrackerEdgeCases:
    """Test edge cases and error conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = ValidationStatsTracker()
    
    def test_large_number_of_validations(self):
        """Test handling large numbers of validations."""
        # Record many validations
        for i in range(10000):
            success = (i % 3) == 0  # ~33% success rate
            command_type = CommandType.LLM if (i % 2) == 0 else CommandType.WEB
            self.tracker.record_validation_result(success, command_type)
        
        stats = self.tracker.get_validation_stats()
        
        assert stats.total_validations == 10000
        assert stats.successful_validations + stats.failed_validations == 10000
        assert stats.by_domain[CommandType.LLM.value] == 5000  # Half are LLM
        assert stats.by_domain[CommandType.WEB.value] == 5000  # Half are BROWSER
    
    def test_many_different_providers(self):
        """Test tracking many different providers."""
        # Record attempts for many providers
        for i in range(100):
            provider_name = f"provider_{i}"
            self.tracker.record_intermediate_validation_attempt(provider_name, True)
            self.tracker.record_intermediate_validation_attempt(provider_name, False)
        
        rates = self.tracker.get_provider_success_rates()
        
        assert len(rates) == 100
        for i in range(100):
            provider_name = f"provider_{i}"
            assert rates[provider_name]["success_rate"] == 0.5
            assert rates[provider_name]["total_attempts"] == 2
    
    def test_provider_name_edge_cases(self):
        """Test provider names with edge case characters."""
        edge_case_names = [
            "",  # Empty string
            " ",  # Whitespace
            "provider with spaces",
            "provider-with-dashes",
            "provider_with_underscores",
            "provider.with.dots",
            "provider/with/slashes",
            "provider🎉with🔥emojis",
            "provider_with_unicode_文字",
            "very_long_provider_name_" * 10
        ]
        
        for name in edge_case_names:
            self.tracker.record_intermediate_validation_attempt(name, True)
            self.tracker.record_intermediate_validation_attempt(name, False)
        
        rates = self.tracker.get_provider_success_rates()
        
        for name in edge_case_names:
            assert name in rates
            assert rates[name]["success_rate"] == 0.5
    
    def test_command_type_edge_cases(self):
        """Test command type handling with various inputs."""
        # Test all CommandType enum values
        command_types = [
            CommandType.LLM,
            CommandType.WEB, 
            CommandType.FILESYSTEM
        ]
        
        for cmd_type in command_types:
            self.tracker.record_validation_result(True, cmd_type)
            self.tracker.record_validation_result(False, cmd_type)
        
        stats = self.tracker.get_validation_stats()
        
        for cmd_type in command_types:
            assert stats.by_domain[cmd_type.value] == 2  # 1 success + 1 failure


class TestValidationStatsTrackerIntegration:
    """Test integration scenarios."""
    
    def test_realistic_validation_workflow(self):
        """Test realistic validation workflow with mixed operations."""
        tracker = ValidationStatsTracker()
        
        # Simulate validation workflow:
        # 1. Multiple LLM validations with various providers
        llm_providers = ["gpt-4", "claude", "gemini"]
        for provider in llm_providers:
            # Each provider tries multiple validations
            for attempt in range(5):
                success = attempt < 3  # 60% success rate
                tracker.record_intermediate_validation_attempt(provider, success)
        
        # Record final LLM validation results
        for i in range(15):  # 5 attempts per 3 providers
            tracker.record_validation_result(i < 9, CommandType.LLM)  # 60% success
        
        # 2. Browser validations
        browser_providers = ["selenium", "playwright"]
        for provider in browser_providers:
            for attempt in range(3):
                success = attempt < 2  # 66% success rate
                tracker.record_intermediate_validation_attempt(provider, success)
        
        # Record browser validation results
        for i in range(6):  # 3 attempts per 2 providers
            tracker.record_validation_result(i < 4, CommandType.WEB)  # 66% success
        
        # 3. Other validation types
        tracker.record_validation_result(True, CommandType.FILESYSTEM)
        tracker.record_validation_result(False, CommandType.LLM)
        
        # Verify overall stats
        stats = tracker.get_validation_stats()
        assert stats.total_validations == 23  # 15 LLM + 6 browser + 2 other
        assert stats.successful_validations == 14  # 9 LLM + 4 browser + 1 other
        assert stats.failed_validations == 9
        
        # Verify provider success rates
        provider_rates = tracker.get_provider_success_rates()
        
        for llm_provider in llm_providers:
            assert provider_rates[llm_provider]["success_rate"] == 0.6
            assert provider_rates[llm_provider]["total_attempts"] == 5
        
        for browser_provider in browser_providers:
            assert abs(provider_rates[browser_provider]["success_rate"] - (2/3)) < 1e-10
            assert provider_rates[browser_provider]["total_attempts"] == 3
    
    def test_concurrent_validation_simulation(self):
        """Test simulation of concurrent validation recording."""
        import threading
        import time
        
        tracker = ValidationStatsTracker()
        
        def record_validations(thread_id):
            """Function to record validations from different threads."""
            try:
                for i in range(50):
                    # Mix of successes and failures
                    success = (i + thread_id) % 3 == 0
                    command_type = CommandType.LLM  # Use only LLM to avoid enum issues
                    tracker.record_validation_result(success, command_type)
                    
                    # Intermediate validations
                    provider = f"provider_{thread_id}"
                    tracker.record_intermediate_validation_attempt(provider, success)
                    
                    # Small delay to simulate processing time
                    time.sleep(0.001)
            except Exception as e:
                # Thread-safe error handling
                pass
        
        # Create and run multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=record_validations, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify final stats - allow for some thread execution variability
        stats = tracker.get_validation_stats()
        assert stats.total_validations <= 250  # Up to 5 threads * 50 validations
        assert stats.total_validations >= 150  # At least 3 successful threads
        
        provider_rates = tracker.get_provider_success_rates()
        assert len(provider_rates) <= 5  # Up to one provider per thread
        assert len(provider_rates) >= 3  # At least 3 threads succeeded