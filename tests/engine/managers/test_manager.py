"""Tests for base manager class."""

import pytest
from abc import ABC
from unittest.mock import Mock, AsyncMock
from lamia.engine.managers.manager import Manager, T
from lamia.interpreter.commands import Command
from lamia.validation.base import BaseValidator


class TestManagerInterface:
    """Test Manager interface."""
    
    def test_is_abstract_base_class(self):
        """Test that Manager is an abstract base class."""
        assert issubclass(Manager, ABC)
        
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            Manager()
    
    def test_is_generic(self):
        """Test that Manager is a generic class."""
        # Check that it has type parameters
        assert hasattr(Manager, '__parameters__')
        assert hasattr(Manager, '__origin__') or hasattr(Manager, '__args__')
    
    def test_abstract_execute_method(self):
        """Test that execute method is abstract."""
        assert hasattr(Manager, 'execute')
        assert callable(Manager.execute)
    
    def test_execute_method_signature(self):
        """Test execute method signature and documentation."""
        method = Manager.execute
        assert method.__name__ == 'execute'
        assert method.__doc__ is not None
        assert "Execute a request in this domain" in method.__doc__
        assert "Args:" in method.__doc__
        assert "Returns:" in method.__doc__


class MockCommand(Command):
    """Mock command for testing."""
    
    def __init__(self, content: str = "test"):
        self.content = content


class MockManager(Manager[MockCommand]):
    """Mock implementation for testing."""
    
    def __init__(self):
        self.executed_commands = []
        self.executed_validators = []
    
    async def execute(self, command: MockCommand, validator: BaseValidator):
        self.executed_commands.append(command)
        self.executed_validators.append(validator)
        return f"Executed: {command.content}"


@pytest.mark.asyncio
class TestManagerImplementation:
    """Test Manager implementation through mock."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = MockManager()
        self.command = MockCommand("test content")
        self.validator = Mock(spec=BaseValidator)
    
    async def test_execute_method_implementation(self):
        """Test that execute method can be implemented."""
        result = await self.manager.execute(self.command, self.validator)
        
        assert result == "Executed: test content"
        assert len(self.manager.executed_commands) == 1
        assert self.manager.executed_commands[0] == self.command
        assert len(self.manager.executed_validators) == 1
        assert self.manager.executed_validators[0] == self.validator
    
    async def test_multiple_executions(self):
        """Test multiple command executions."""
        commands = [
            MockCommand("command 1"),
            MockCommand("command 2"),
            MockCommand("command 3")
        ]
        
        validators = [Mock(spec=BaseValidator) for _ in range(3)]
        
        results = []
        for command, validator in zip(commands, validators):
            result = await self.manager.execute(command, validator)
            results.append(result)
        
        assert len(results) == 3
        assert results[0] == "Executed: command 1"
        assert results[1] == "Executed: command 2"
        assert results[2] == "Executed: command 3"
        
        assert len(self.manager.executed_commands) == 3
        assert len(self.manager.executed_validators) == 3
    
    async def test_command_type_enforcement(self):
        """Test that manager enforces command type through generics."""
        # This is more of a type checking test, but we can verify the implementation works
        command = MockCommand("type test")
        result = await self.manager.execute(command, self.validator)
        
        assert isinstance(result, str)
        assert self.manager.executed_commands[0] == command


class TestManagerTypeSystem:
    """Test Manager type system and generics."""
    
    def test_type_var_definition(self):
        """Test that TypeVar T is properly defined."""
        from lamia.engine.managers.manager import T
        
        assert T is not None
        assert hasattr(T, '__bound__')
        assert T.__bound__ == Command
    
    def test_generic_specialization(self):
        """Test that Manager can be specialized with different command types."""
        # Test that we can create specialized managers
        class AnotherCommand(Command):
            pass
        
        class SpecializedManager(Manager[AnotherCommand]):
            async def execute(self, command: AnotherCommand, validator: BaseValidator):
                return f"Special: {command}"
        
        # Should be able to instantiate specialized manager
        manager = SpecializedManager()
        assert manager is not None
        assert issubclass(SpecializedManager, Manager)


class TestManagerDocumentation:
    """Test Manager documentation and contracts."""
    
    def test_class_documentation(self):
        """Test that Manager class has proper documentation."""
        assert Manager.__doc__ is not None
        assert "Abstract base class for all domain managers" in Manager.__doc__
    
    def test_execute_method_documentation(self):
        """Test execute method documentation."""
        doc = Manager.execute.__doc__
        assert doc is not None
        assert "Execute a request in this domain" in doc
        assert "command:" in doc.lower() or "content:" in doc.lower()
        assert "validator:" in doc.lower()
        assert "returns:" in doc.lower()
    
    def test_parameter_documentation(self):
        """Test that all parameters are documented."""
        doc = Manager.execute.__doc__
        assert "Args:" in doc
        assert "validator" in doc
        assert "Returns:" in doc


class AsyncMockValidator(BaseValidator):
    """Async mock validator for testing."""
    
    def __init__(self, result=True):
        self.result = result
        self.validated_content = []
    
    @property
    def name(self):
        return "async_mock_validator"
    
    @property
    def initial_hint(self):
        return "Mock validation hint"
    
    async def validate(self, response, **kwargs):
        self.validated_content.append(response)
        from lamia.validation.base import ValidationResult
        return ValidationResult(is_valid=self.result)


class IntegrationTestManager(Manager[MockCommand]):
    """Manager for integration testing with real validators."""
    
    async def execute(self, command: MockCommand, validator: BaseValidator):
        # Simulate processing the command content
        processed_content = f"Processed: {command.content}"
        
        # Validate the result
        validation_result = await validator.validate(processed_content)
        
        return {
            'content': processed_content,
            'validation_result': validation_result,
            'is_valid': validation_result.is_valid
        }


@pytest.mark.asyncio
class TestManagerValidatorIntegration:
    """Test Manager integration with validators."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = IntegrationTestManager()
    
    async def test_integration_with_mock_validator(self):
        """Test manager integration with mock validator."""
        command = MockCommand("integration test")
        validator = AsyncMockValidator(result=True)
        
        result = await self.manager.execute(command, validator)
        
        assert result['content'] == "Processed: integration test"
        assert result['is_valid'] is True
        assert len(validator.validated_content) == 1
        assert validator.validated_content[0] == "Processed: integration test"
    
    async def test_integration_with_failing_validator(self):
        """Test manager integration with failing validator."""
        command = MockCommand("failing test")
        validator = AsyncMockValidator(result=False)
        
        result = await self.manager.execute(command, validator)
        
        assert result['content'] == "Processed: failing test"
        assert result['is_valid'] is False
        assert len(validator.validated_content) == 1
    
    async def test_multiple_validations(self):
        """Test multiple validations with same validator."""
        validator = AsyncMockValidator(result=True)
        commands = [MockCommand(f"test {i}") for i in range(3)]
        
        results = []
        for command in commands:
            result = await self.manager.execute(command, validator)
            results.append(result)
        
        assert len(results) == 3
        assert all(result['is_valid'] for result in results)
        assert len(validator.validated_content) == 3
        
        for i, content in enumerate(validator.validated_content):
            assert content == f"Processed: test {i}"