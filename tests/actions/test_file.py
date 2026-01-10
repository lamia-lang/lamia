"""Tests for file actions module."""

import pytest
import json
from lamia.actions.file import FileActions, file


class TestFileActions:
    """Test FileActions class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.file_actions = FileActions()
    
    def test_read(self):
        """Test file read command generation."""
        # Basic read
        result = self.file_actions.read("/path/to/file.txt")
        assert result == "file://read:/path/to/file.txt"
        
        # Read with custom encoding
        result = self.file_actions.read("/path/to/file.txt", encoding="latin1")
        assert result == "file://read:/path/to/file.txt encoding:latin1"
        
        # Read with default encoding (should not add encoding)
        result = self.file_actions.read("/path/to/file.txt", encoding="utf-8")
        assert result == "file://read:/path/to/file.txt"
    
    def test_write(self):
        """Test file write command generation."""
        content = "Hello, World!"
        
        # Basic write
        result = self.file_actions.write("/path/to/file.txt", content)
        expected = f"file://write:/path/to/file.txt content:{json.dumps(content)}"
        assert result == expected
        
        # Write with custom encoding
        result = self.file_actions.write("/path/to/file.txt", content, encoding="latin1")
        expected = f"file://write:/path/to/file.txt content:{json.dumps(content)} encoding:latin1"
        assert result == expected
        
        # Write with create_dirs disabled
        result = self.file_actions.write("/path/to/file.txt", content, create_dirs=False)
        expected = f"file://write:/path/to/file.txt content:{json.dumps(content)} create_dirs:false"
        assert result == expected
        
        # Write with all options
        result = self.file_actions.write("/path/to/file.txt", content, encoding="latin1", create_dirs=False)
        expected = f"file://write:/path/to/file.txt content:{json.dumps(content)} encoding:latin1 create_dirs:false"
        assert result == expected
    
    def test_append(self):
        """Test file append command generation."""
        content = "Additional content"
        
        # Basic append
        result = self.file_actions.append("/path/to/file.txt", content)
        expected = f"file://append:/path/to/file.txt content:{json.dumps(content)}"
        assert result == expected
        
        # Append with custom encoding
        result = self.file_actions.append("/path/to/file.txt", content, encoding="latin1")
        expected = f"file://append:/path/to/file.txt content:{json.dumps(content)} encoding:latin1"
        assert result == expected
        
        # Append with create_dirs disabled
        result = self.file_actions.append("/path/to/file.txt", content, create_dirs=False)
        expected = f"file://append:/path/to/file.txt content:{json.dumps(content)} create_dirs:false"
        assert result == expected
    
    def test_delete(self):
        """Test file delete command generation."""
        result = self.file_actions.delete("/path/to/file.txt")
        assert result == "file://delete:/path/to/file.txt"
    
    def test_exists(self):
        """Test file exists command generation."""
        result = self.file_actions.exists("/path/to/file.txt")
        assert result == "file://exists:/path/to/file.txt"
    
    def test_copy(self):
        """Test file copy command generation."""
        # Basic copy
        result = self.file_actions.copy("/source/file.txt", "/dest/file.txt")
        assert result == "file://copy:/source/file.txt:/dest/file.txt"
        
        # Copy with create_dirs disabled
        result = self.file_actions.copy("/source/file.txt", "/dest/file.txt", create_dirs=False)
        assert result == "file://copy:/source/file.txt:/dest/file.txt create_dirs:false"
    
    def test_move(self):
        """Test file move command generation."""
        # Basic move
        result = self.file_actions.move("/source/file.txt", "/dest/file.txt")
        assert result == "file://move:/source/file.txt:/dest/file.txt"
        
        # Move with create_dirs disabled
        result = self.file_actions.move("/source/file.txt", "/dest/file.txt", create_dirs=False)
        assert result == "file://move:/source/file.txt:/dest/file.txt create_dirs:false"
    
    def test_size(self):
        """Test file size command generation."""
        result = self.file_actions.size("/path/to/file.txt")
        assert result == "file://size:/path/to/file.txt"
    
    def test_mkdir(self):
        """Test directory creation command generation."""
        # Basic mkdir
        result = self.file_actions.mkdir("/path/to/directory")
        assert result == "file://mkdir:/path/to/directory"
        
        # mkdir with parents disabled
        result = self.file_actions.mkdir("/path/to/directory", parents=False)
        assert result == "file://mkdir:/path/to/directory parents:false"
    
    def test_list_dir(self):
        """Test directory listing command generation."""
        # Basic list
        result = self.file_actions.list_dir()
        assert result == "file://list:."
        
        # List specific directory
        result = self.file_actions.list_dir("/path/to/directory")
        assert result == "file://list:/path/to/directory"
        
        # List with pattern
        result = self.file_actions.list_dir("/path/to/directory", pattern="*.py")
        assert result == "file://list:/path/to/directory pattern:*.py"
        
        # List current directory with pattern
        result = self.file_actions.list_dir(".", pattern="*.txt")
        assert result == "file://list:. pattern:*.txt"
    
    def test_content_encoding_handling(self):
        """Test proper JSON encoding of content."""
        # Test content with special characters
        content = 'Text with "quotes" and \n newlines'
        result = self.file_actions.write("/path/to/file.txt", content)
        expected_content = json.dumps(content)
        assert expected_content in result
        
        # Test empty content
        result = self.file_actions.write("/path/to/file.txt", "")
        assert 'content:""' in result
        
        # Test unicode content
        content = "Unicode: café, naïve, résumé"
        result = self.file_actions.write("/path/to/file.txt", content)
        expected_content = json.dumps(content)
        assert expected_content in result


class TestFileSingleton:
    """Test the singleton file instance."""
    
    def test_singleton_exists(self):
        """Test that the singleton file instance exists."""
        assert file is not None
        assert isinstance(file, FileActions)
    
    def test_singleton_functionality(self):
        """Test that the singleton works correctly."""
        result = file.read("/test/path.txt")
        assert result == "file://read:/test/path.txt"
        
        result = file.write("/test/path.txt", "content")
        expected = f"file://write:/test/path.txt content:{json.dumps('content')}"
        assert result == expected