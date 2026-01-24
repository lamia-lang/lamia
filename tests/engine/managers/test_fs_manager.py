"""Tests for filesystem manager."""

import pytest
import tempfile
import os
from unittest.mock import Mock, AsyncMock, mock_open, patch
from lamia.engine.managers.fs_manager import FSManager
from lamia.engine.managers.manager import Manager
from lamia.engine.config_provider import ConfigProvider
from lamia.interpreter.commands import FileCommand
from lamia.validation.base import BaseValidator, ValidationResult


class TestFSManagerInitialization:
    """Test FSManager initialization."""
    
    def test_initialization(self):
        """Test FSManager initialization."""
        config_provider = Mock(spec=ConfigProvider)
        fs_manager = FSManager(config_provider)
        
        assert fs_manager.config_provider == config_provider
        assert isinstance(fs_manager, Manager)
    
    def test_inheritance(self):
        """Test that FSManager inherits from Manager with FileCommand type."""
        config_provider = Mock(spec=ConfigProvider)
        fs_manager = FSManager(config_provider)
        
        assert isinstance(fs_manager, Manager)
        # Verify it's specialized for FileCommand
        assert hasattr(fs_manager, 'execute')


class MockValidator(BaseValidator):
    """Mock validator for testing."""
    
    def __init__(self, validation_result: ValidationResult):
        self._validation_result = validation_result
        self.validated_content = []
    
    @property
    def name(self):
        return "mock_validator"
    
    @property
    def initial_hint(self):
        return "Mock validation hint"
    
    async def validate(self, response, **kwargs):
        self.validated_content.append(response)
        return self._validation_result


@pytest.mark.asyncio
class TestFSManagerExecution:
    """Test FSManager execution."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config_provider = Mock(spec=ConfigProvider)
        self.fs_manager = FSManager(self.config_provider)
    
    async def test_execute_with_real_file(self):
        """Test executing with a real temporary file."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("Test file content\nLine 2\nLine 3")
            temp_file_path = temp_file.name
        
        try:
            # Create file command
            file_command = Mock(spec=FileCommand)
            file_command.path = temp_file_path
            
            # Create validator
            expected_result = ValidationResult(is_valid=True)
            validator = MockValidator(expected_result)
            
            # Execute
            result = await self.fs_manager.execute(file_command, validator)
            
            # Verify result
            assert result == expected_result
            assert len(validator.validated_content) == 1
            assert validator.validated_content[0] == "Test file content\nLine 2\nLine 3"
            
        finally:
            # Clean up
            os.unlink(temp_file_path)
    
    @patch('builtins.open', new_callable=mock_open, read_data="Mocked file content")
    async def test_execute_with_mocked_file(self, mock_file):
        """Test executing with mocked file operations."""
        # Create file command
        file_command = Mock(spec=FileCommand)
        file_command.path = "/mocked/path/file.txt"
        
        # Create validator
        expected_result = ValidationResult(is_valid=True, error_message="")
        validator = MockValidator(expected_result)
        
        # Execute
        result = await self.fs_manager.execute(file_command, validator)
        
        # Verify file was opened correctly
        mock_file.assert_called_once_with("/mocked/path/file.txt", 'r')
        
        # Verify result
        assert result == expected_result
        assert len(validator.validated_content) == 1
        assert validator.validated_content[0] == "Mocked file content"
    
    @patch('builtins.open', new_callable=mock_open, read_data="")
    async def test_execute_with_empty_file(self, mock_file):
        """Test executing with empty file."""
        file_command = Mock(spec=FileCommand)
        file_command.path = "/path/to/empty.txt"
        
        expected_result = ValidationResult(is_valid=False, error_message="Empty file")
        validator = MockValidator(expected_result)
        
        result = await self.fs_manager.execute(file_command, validator)
        
        assert result == expected_result
        assert len(validator.validated_content) == 1
        assert validator.validated_content[0] == ""
    
    async def test_execute_file_not_found(self):
        """Test executing with non-existent file."""
        file_command = Mock(spec=FileCommand)
        file_command.path = "/nonexistent/file.txt"
        
        validator = Mock(spec=BaseValidator)
        
        # Should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            await self.fs_manager.execute(file_command, validator)
        
        # Validator should not be called
        validator.validate.assert_not_called()
    
    async def test_execute_permission_error(self):
        """Test executing with permission denied."""
        # Mock open to raise PermissionError
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            file_command = Mock(spec=FileCommand)
            file_command.path = "/restricted/file.txt"
            
            validator = Mock(spec=BaseValidator)
            
            # Should raise PermissionError
            with pytest.raises(PermissionError):
                await self.fs_manager.execute(file_command, validator)
            
            # Validator should not be called
            validator.validate.assert_not_called()
    
    async def test_execute_with_validator_failure(self):
        """Test execution when validator fails."""
        with patch('builtins.open', mock_open(read_data="Invalid content")):
            file_command = Mock(spec=FileCommand)
            file_command.path = "/path/to/file.txt"
            
            # Create failing validator
            expected_result = ValidationResult(is_valid=False, error_message="Validation failed")
            validator = MockValidator(expected_result)
            
            result = await self.fs_manager.execute(file_command, validator)
            
            assert result == expected_result
            assert not result.is_valid
            assert result.error_message == "Validation failed"
            assert len(validator.validated_content) == 1
            assert validator.validated_content[0] == "Invalid content"
    
    async def test_execute_multiple_files(self):
        """Test executing multiple file commands."""
        file_contents = ["Content 1", "Content 2", "Content 3"]
        
        for i, content in enumerate(file_contents):
            with patch('builtins.open', mock_open(read_data=content)):
                file_command = Mock(spec=FileCommand)
                file_command.path = f"/path/to/file{i}.txt"
                
                expected_result = ValidationResult(is_valid=True)
                validator = MockValidator(expected_result)
                
                result = await self.fs_manager.execute(file_command, validator)
                
                assert result == expected_result
                assert len(validator.validated_content) == 1
                assert validator.validated_content[0] == content


@pytest.mark.asyncio
class TestFSManagerFileHandling:
    """Test FSManager file handling specifics."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config_provider = Mock(spec=ConfigProvider)
        self.fs_manager = FSManager(self.config_provider)
    
    async def test_file_encoding_handling(self):
        """Test that files are read with correct encoding."""
        # Test with UTF-8 content
        utf8_content = "UTF-8 content with émojis 🚀"
        
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as temp_file:
            temp_file.write(utf8_content)
            temp_file_path = temp_file.name
        
        try:
            file_command = Mock(spec=FileCommand)
            file_command.path = temp_file_path
            
            expected_result = ValidationResult(is_valid=True)
            validator = MockValidator(expected_result)
            
            result = await self.fs_manager.execute(file_command, validator)
            
            assert result == expected_result
            assert len(validator.validated_content) == 1
            assert validator.validated_content[0] == utf8_content
            
        finally:
            os.unlink(temp_file_path)
    
    async def test_large_file_handling(self):
        """Test handling of larger files."""
        # Create content with multiple lines
        large_content = "\n".join([f"Line {i}: {'x' * 100}" for i in range(1000)])
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(large_content)
            temp_file_path = temp_file.name
        
        try:
            file_command = Mock(spec=FileCommand)
            file_command.path = temp_file_path
            
            expected_result = ValidationResult(is_valid=True)
            validator = MockValidator(expected_result)
            
            result = await self.fs_manager.execute(file_command, validator)
            
            assert result == expected_result
            assert len(validator.validated_content) == 1
            assert len(validator.validated_content[0]) == len(large_content)
            assert validator.validated_content[0] == large_content
            
        finally:
            os.unlink(temp_file_path)
    
    async def test_binary_file_handling(self):
        """Test handling of binary files (should fail gracefully)."""
        # Create a binary file
        binary_content = b'\x00\x01\x02\x03\xFF\xFE\xFD'
        
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as temp_file:
            temp_file.write(binary_content)
            temp_file_path = temp_file.name
        
        try:
            file_command = Mock(spec=FileCommand)
            file_command.path = temp_file_path
            
            validator = Mock(spec=BaseValidator)
            
            # Should raise UnicodeDecodeError when trying to read binary file as text
            with pytest.raises(UnicodeDecodeError):
                await self.fs_manager.execute(file_command, validator)
            
        finally:
            os.unlink(temp_file_path)


class TestFSManagerTypeSystem:
    """Test FSManager type system compliance."""
    
    def test_manager_specialization(self):
        """Test that FSManager is properly specialized for FileCommand."""
        config_provider = Mock(spec=ConfigProvider)
        fs_manager = FSManager(config_provider)
        
        # Should be instance of Manager
        assert isinstance(fs_manager, Manager)
        
        # Should have execute method with correct signature
        assert hasattr(fs_manager, 'execute')
        assert callable(fs_manager.execute)
    
    @pytest.mark.asyncio
    async def test_type_enforcement_file_command(self):
        """Test that FSManager works with FileCommand objects."""
        config_provider = Mock(spec=ConfigProvider)
        fs_manager = FSManager(config_provider)
        
        with patch('builtins.open', mock_open(read_data="test content")):
            file_command = Mock(spec=FileCommand)
            file_command.path = "/test/path.txt"
            
            validator = MockValidator(ValidationResult(is_valid=True))
            
            result = await fs_manager.execute(file_command, validator)
            
            assert isinstance(result, ValidationResult)
            assert result.is_valid


class TestFSManagerErrorHandling:
    """Test FSManager error handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config_provider = Mock(spec=ConfigProvider)
        self.fs_manager = FSManager(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_validator_exception_handling(self):
        """Test handling of validator exceptions."""
        with patch('builtins.open', mock_open(read_data="test content")):
            file_command = Mock(spec=FileCommand)
            file_command.path = "/test/path.txt"
            
            # Create validator that raises exception
            validator = Mock(spec=BaseValidator)
            validator.validate.side_effect = Exception("Validator error")
            
            # Should propagate validator exception
            with pytest.raises(Exception, match="Validator error"):
                await self.fs_manager.execute(file_command, validator)
    
    @pytest.mark.asyncio
    async def test_none_validator_handling(self):
        """Test handling of None validator."""
        with patch('builtins.open', mock_open(read_data="test content")):
            file_command = Mock(spec=FileCommand)
            file_command.path = "/test/path.txt"
            
            # Should raise AttributeError when validator is None
            with pytest.raises(AttributeError):
                await self.fs_manager.execute(file_command, None)