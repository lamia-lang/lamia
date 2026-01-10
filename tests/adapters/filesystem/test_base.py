"""Tests for filesystem base adapter."""

import pytest
from abc import ABC
from lamia.adapters.filesystem.base import BaseFSAdapter


class TestBaseFSAdapterInterface:
    """Test BaseFSAdapter interface."""
    
    def test_is_abstract_base_class(self):
        """Test that BaseFSAdapter is an abstract base class."""
        assert issubclass(BaseFSAdapter, ABC) is False  # It doesn't inherit from ABC but has abstract methods
        
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            BaseFSAdapter()
    
    def test_abstract_methods_exist(self):
        """Test that all required abstract methods are defined."""
        abstract_methods = ['read', 'write', 'exists', 'delete']
        
        for method_name in abstract_methods:
            assert hasattr(BaseFSAdapter, method_name)
            method = getattr(BaseFSAdapter, method_name)
            assert callable(method)
    
    def test_read_method_signature(self):
        """Test read method signature."""
        method = BaseFSAdapter.read
        # Test that it takes path parameter
        assert method.__name__ == 'read'
        # Check docstring
        assert "Read file contents" in method.__doc__
        assert "bytes" in method.__doc__
    
    def test_write_method_signature(self):
        """Test write method signature."""
        method = BaseFSAdapter.write
        assert method.__name__ == 'write'
        assert "Write data to a file" in method.__doc__
        assert "Union[str, bytes]" in method.__doc__
    
    def test_exists_method_signature(self):
        """Test exists method signature."""
        method = BaseFSAdapter.exists
        assert method.__name__ == 'exists'
        assert "Check if a path exists" in method.__doc__
        assert "bool" in method.__doc__
    
    def test_delete_method_signature(self):
        """Test delete method signature."""
        method = BaseFSAdapter.delete
        assert method.__name__ == 'delete'
        assert "Delete a file" in method.__doc__


class MockFSAdapter(BaseFSAdapter):
    """Mock implementation for testing."""
    
    def __init__(self):
        self.files = {}
    
    async def read(self, path: str) -> bytes:
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
        return self.files[path]
    
    async def write(self, path: str, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        self.files[path] = data
    
    async def exists(self, path: str) -> bool:
        return path in self.files
    
    async def delete(self, path: str) -> None:
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
        del self.files[path]


@pytest.mark.asyncio
class TestBaseFSAdapterImplementation:
    """Test implementation behavior through mock adapter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = MockFSAdapter()
    
    async def test_write_and_read(self):
        """Test basic write and read operations."""
        data = b"test data"
        path = "/test/file.txt"
        
        await self.adapter.write(path, data)
        result = await self.adapter.read(path)
        
        assert result == data
    
    async def test_write_string_data(self):
        """Test writing string data."""
        data = "Hello, World!"
        path = "/test/string.txt"
        
        await self.adapter.write(path, data)
        result = await self.adapter.read(path)
        
        assert result == data.encode('utf-8')
    
    async def test_exists(self):
        """Test path existence checking."""
        path = "/test/exists.txt"
        
        # Should not exist initially
        assert not await self.adapter.exists(path)
        
        # Should exist after writing
        await self.adapter.write(path, b"data")
        assert await self.adapter.exists(path)
    
    async def test_delete(self):
        """Test file deletion."""
        path = "/test/delete.txt"
        
        # Write file
        await self.adapter.write(path, b"data")
        assert await self.adapter.exists(path)
        
        # Delete file
        await self.adapter.delete(path)
        assert not await self.adapter.exists(path)
    
    async def test_read_nonexistent_file(self):
        """Test reading a file that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            await self.adapter.read("/nonexistent/file.txt")
    
    async def test_delete_nonexistent_file(self):
        """Test deleting a file that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            await self.adapter.delete("/nonexistent/file.txt")
    
    async def test_multiple_files(self):
        """Test operations with multiple files."""
        files = {
            "/dir1/file1.txt": b"content1",
            "/dir1/file2.txt": b"content2",
            "/dir2/file3.txt": b"content3"
        }
        
        # Write all files
        for path, data in files.items():
            await self.adapter.write(path, data)
        
        # Verify all exist
        for path in files:
            assert await self.adapter.exists(path)
        
        # Read and verify content
        for path, expected_data in files.items():
            actual_data = await self.adapter.read(path)
            assert actual_data == expected_data
        
        # Delete one file
        del_path = "/dir1/file1.txt"
        await self.adapter.delete(del_path)
        assert not await self.adapter.exists(del_path)
        
        # Other files should still exist
        for path in ["/dir1/file2.txt", "/dir2/file3.txt"]:
            assert await self.adapter.exists(path)


class TestBaseFSAdapterDocumentation:
    """Test documentation and error handling specifications."""
    
    def test_read_method_errors(self):
        """Test read method error documentation."""
        doc = BaseFSAdapter.read.__doc__
        assert "FileNotFoundError" in doc
        assert "PermissionError" in doc
        assert "IOError" in doc
    
    def test_write_method_errors(self):
        """Test write method error documentation."""
        doc = BaseFSAdapter.write.__doc__
        assert "PermissionError" in doc
        assert "IOError" in doc
    
    def test_delete_method_errors(self):
        """Test delete method error documentation."""
        doc = BaseFSAdapter.delete.__doc__
        assert "FileNotFoundError" in doc
        assert "PermissionError" in doc
        assert "IOError" in doc
    
    def test_method_parameter_documentation(self):
        """Test that all methods document their parameters."""
        methods_to_check = ['read', 'write', 'exists', 'delete']
        
        for method_name in methods_to_check:
            method = getattr(BaseFSAdapter, method_name)
            doc = method.__doc__
            assert "Args:" in doc
            assert "path:" in doc.lower() or "path " in doc.lower()
    
    def test_method_return_documentation(self):
        """Test that methods document their return values."""
        # Methods that should have Returns documentation
        methods_with_returns = ['read', 'exists']
        
        for method_name in methods_with_returns:
            method = getattr(BaseFSAdapter, method_name)
            doc = method.__doc__
            assert "Returns:" in doc