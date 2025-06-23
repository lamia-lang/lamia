"""
Integration tests for FunctionalValidator with Docker.
These tests require Docker to be available and running.
Run with: pytest tests/validation/validators/test_functional_validator_integration.py
"""
import pytest
import asyncio
import subprocess
from lamia.validation.validators.functional_validator import FunctionalValidator
from lamia.validation.base import ValidationResult


def check_docker_available():
    """Check if Docker is available and running for testing."""
    try:
        # Check if docker command exists
        result = subprocess.run(['docker', '--version'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        if result.returncode != 0:
            return False
            
        # Check if Docker daemon is running by trying to list containers
        result = subprocess.run(['docker', 'ps'], 
                              capture_output=True, 
                              text=True, 
                              timeout=10)
        return result.returncode == 0
        
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
    except Exception:
        # Any other exception means Docker is not properly available
        return False


DOCKER_AVAILABLE = check_docker_available()


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available or not running")
@pytest.mark.integration
@pytest.mark.asyncio
async def test_functional_validator_executes_simple_function_in_docker():
    """Test that FunctionalValidator can execute a basic addition function inside Docker container."""
    test_cases = [((1, 2), 3), ((5, 4), 9)]
    validator = FunctionalValidator(test_cases, use_docker=True, execution_timeout=10)
    
    simple_code = """def add_function(a, b):
    return a + b"""
    
    result = await validator.validate_strict(simple_code)
    assert result.is_valid


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available or not running")
@pytest.mark.integration
@pytest.mark.asyncio
async def test_functional_validator_extracts_code_from_markdown_in_docker():
    """Test that FunctionalValidator can extract and execute Python code from markdown response in Docker."""
    test_cases = [((3, 4), 12), ((2, 5), 10)]
    validator = FunctionalValidator(test_cases, use_docker=True, strict=False)
    
    chatty_response = """
I'll create a multiplication function for you:

```python
def multiply_numbers(x, y):
    return x * y
```

This function multiplies two numbers together.
"""
    
    result = await validator.validate_permissive(chatty_response)
    assert result.is_valid


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available or not running")
@pytest.mark.integration
@pytest.mark.asyncio
async def test_functional_validator_handles_expected_exceptions_in_docker():
    """Test that FunctionalValidator correctly validates functions that should raise specific exceptions in Docker."""
    test_cases = [
        ((10, 2), 5),
        ((1, 0), ZeroDivisionError)
    ]
    validator = FunctionalValidator(test_cases, use_docker=True)
    
    division_code = """def divide_function(a, b):
    if b == 0:
        raise ZeroDivisionError("Division by zero")
    return a // b"""
    
    result = await validator.validate_strict(division_code)
    assert result.is_valid


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available or not running")
@pytest.mark.integration
@pytest.mark.asyncio
async def test_functional_validator_blocks_dangerous_imports_before_docker_execution():
    """Test that FunctionalValidator blocks dangerous code during security checks before Docker execution."""
    test_cases = [((1, 2), 3)]
    validator = FunctionalValidator(test_cases, use_docker=True)
    
    # This should fail security checks before even reaching Docker
    malicious_code = """
import subprocess
def bad_function(a, b):
    subprocess.run(['ls', '/'])
    return a + b
"""
    
    result = await validator.validate_strict(malicious_code)
    assert not result.is_valid
    assert "dangerous" in result.error_message.lower()


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available or not running")
@pytest.mark.integration
@pytest.mark.asyncio
async def test_functional_validator_respects_docker_resource_limits():
    """Test that FunctionalValidator can execute functions within Docker memory and timeout limits."""
    test_cases = [((1,), 1)]
    validator = FunctionalValidator(
        test_cases, 
        use_docker=True, 
        execution_timeout=3,
        docker_memory_limit="64m"
    )
    
    # Function that should work within limits
    simple_code = """def simple_function(x):
    return x"""
    
    result = await validator.validate_strict(simple_code)
    assert result.is_valid


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available or not running")
@pytest.mark.integration
@pytest.mark.asyncio
async def test_functional_validator_blocks_time_import_for_security():
    """Test that FunctionalValidator blocks time import for security even with Docker execution."""
    test_cases = [((1,), 1)]
    validator = FunctionalValidator(test_cases, use_docker=True, execution_timeout=2)
    
    # Function with dangerous import (should fail security check)
    delay_code = """
import time
def slow_function(x):
    time.sleep(0.1)  # Short delay
    return x
"""
    
    # This should fail security check (time import), not timeout
    result = await validator.validate_strict(delay_code)
    assert not result.is_valid
    assert "dangerous" in result.error_message.lower()


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available or not running")
@pytest.mark.integration
@pytest.mark.asyncio
async def test_functional_validator_reports_wrong_results_in_docker():
    """Test that FunctionalValidator correctly identifies when function returns wrong results in Docker."""
    test_cases = [((2, 3), 5), ((4, 1), 5)]
    validator = FunctionalValidator(test_cases, use_docker=True)
    
    wrong_code = """def subtract_function(a, b):
    return a - b"""  # Should add, not subtract
    
    result = await validator.validate_strict(wrong_code)
    assert not result.is_valid
    assert "Expected 5 but got -1" in result.error_message


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available or not running")
@pytest.mark.integration
@pytest.mark.asyncio
async def test_functional_validator_docker_and_namespace_execution_produce_same_results():
    """Test that FunctionalValidator produces consistent results between Docker and namespace execution modes."""
    test_cases = [((1, 2), 3), ((5, 3), 8), ((-1, 1), 0)]
    
    clean_code = """def add_function(a, b):
    return a + b"""
    
    # Test with namespace execution
    validator_namespace = FunctionalValidator(test_cases, use_docker=False)
    result_namespace = await validator_namespace.validate_strict(clean_code)
    
    # Test with Docker execution
    validator_docker = FunctionalValidator(test_cases, use_docker=True)
    result_docker = await validator_docker.validate_strict(clean_code)
    
    # Both should succeed
    assert result_namespace.is_valid
    assert result_docker.is_valid


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available or not running")
@pytest.mark.integration
@pytest.mark.asyncio
async def test_functional_validator_security_consistent_between_docker_and_namespace():
    """Test that FunctionalValidator consistently blocks dangerous code in both Docker and namespace modes."""
    test_cases = [((1, 2), 3)]
    
    dangerous_code = """
import os
def bad_function(a, b):
    return a + b
"""
    
    # Test with namespace execution
    validator_namespace = FunctionalValidator(test_cases, use_docker=False)
    result_namespace = await validator_namespace.validate_strict(dangerous_code)
    
    # Test with Docker execution
    validator_docker = FunctionalValidator(test_cases, use_docker=True)
    result_docker = await validator_docker.validate_strict(dangerous_code)
    
    # Both should fail for security reasons
    assert not result_namespace.is_valid
    assert not result_docker.is_valid
    assert "dangerous" in result_namespace.error_message.lower()
    assert "dangerous" in result_docker.error_message.lower()


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available or not running")
@pytest.mark.integration
def test_functional_validator_docker_configuration_options():
    """Test that FunctionalValidator correctly accepts and stores Docker configuration options."""
    test_cases = [((1, 2), 3)]
    validator = FunctionalValidator(
        test_cases, 
        use_docker=True,
        docker_image="python:3.11-slim",
        docker_memory_limit="256m"
    )
    
    assert validator.use_docker == True
    assert validator.docker_image == "python:3.11-slim"
    assert validator.docker_memory_limit == "256m"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_functional_validator_falls_back_from_docker_to_namespace_when_docker_unavailable():
    """Test that FunctionalValidator automatically falls back to namespace execution when Docker is not available."""
    test_cases = [((1, 2), 3), ((5, 3), 8)]
    
    # Request Docker mode (will fallback if not available)
    validator = FunctionalValidator(test_cases, use_docker=True)
    
    # This should work regardless of Docker availability due to fallback
    simple_code = """def add_function(a, b):
    return a + b"""
    
    result = await validator.validate_strict(simple_code)
    # Should be valid due to fallback mechanism
    assert result.is_valid


@pytest.mark.integration
@pytest.mark.asyncio
async def test_functional_validator_security_applies_regardless_of_execution_mode():
    """Test that FunctionalValidator applies security restrictions in both Docker and namespace execution modes."""
    test_cases = [((1, 2), 3)]
    
    dangerous_code = """
import os
def bad_function(a, b):
    os.system("echo 'This should be blocked'")
    return a + b
"""
    
    # Test with namespace execution
    validator_namespace = FunctionalValidator(test_cases, use_docker=False)
    result_namespace = await validator_namespace.validate_strict(dangerous_code)
    assert not result_namespace.is_valid
    assert "dangerous" in result_namespace.error_message.lower()
    
    # Test with Docker execution (will fallback if Docker not available)
    validator_docker = FunctionalValidator(test_cases, use_docker=True)
    result_docker = await validator_docker.validate_strict(dangerous_code)
    assert not result_docker.is_valid
    assert "dangerous" in result_docker.error_message.lower()


@pytest.mark.integration
def test_functional_validator_handles_docker_unavailable_gracefully():
    """Test that FunctionalValidator handles Docker unavailability gracefully without raising errors."""
    test_cases = [((1, 2), 3)]
    
    # This should not raise an error even if Docker is not available
    validator = FunctionalValidator(test_cases, use_docker=True)
    
    # If Docker is not available, use_docker should be set to False
    if not DOCKER_AVAILABLE:
        assert validator.use_docker == False
    else:
        assert validator.use_docker == True


if __name__ == "__main__":
    if DOCKER_AVAILABLE:
        print("✅ Docker is available - running integration tests")
        pytest.main([__file__, "-v", "-m", "integration"])
    else:
        print("⚠️  Docker not available - running fallback tests only")
        pytest.main([__file__, "-v", "-k", "fallback"]) 