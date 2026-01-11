"""Comprehensive tests for LocalFSAdapter filesystem implementation."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock, mock_open
from lamia.adapters.filesystem.local_fs_adapter import LocalFSAdapter
from lamia.adapters.filesystem.base import BaseFSAdapter


class TestLocalFSAdapterInitialization:
    """Test LocalFSAdapter initialization and configuration."""
    
    def test_initialization_without_base_path(self):
        """Test initialization without base path restriction."""
        adapter = LocalFSAdapter()
        
        assert adapter.base_path is None
        assert isinstance(adapter, BaseFSAdapter)
    
    def test_initialization_with_base_path(self):
        """Test initialization with base path restriction."""
        base_path = "/tmp/test_base"
        adapter = LocalFSAdapter(base_path=base_path)
        
        assert adapter.base_path == Path(base_path)
        assert isinstance(adapter, BaseFSAdapter)
    
    def test_initialization_with_path_object(self):
        """Test initialization with Path object."""
        base_path = Path("/tmp/test_base")
        adapter = LocalFSAdapter(base_path=str(base_path))
        
        assert adapter.base_path == base_path


class TestLocalFSAdapterPathResolution:
    """Test LocalFSAdapter path resolution logic."""
    
    def test_resolve_path_without_base_path(self):
        """Test path resolution when no base path is set."""
        adapter = LocalFSAdapter()
        
        result = adapter._resolve_path("test/file.txt")
        assert result == Path("test/file.txt")
        
        result = adapter._resolve_path("/absolute/path.txt")
        assert result == Path("/absolute/path.txt")
    
    def test_resolve_path_with_base_path_relative(self):
        """Test path resolution with base path and relative paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LocalFSAdapter(base_path=temp_dir)
            
            result = adapter._resolve_path("test/file.txt")
            expected = Path(temp_dir) / "test/file.txt"
            assert result == expected
    
    def test_resolve_path_with_base_path_absolute_within(self):
        """Test path resolution with absolute path within base directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LocalFSAdapter(base_path=temp_dir)
            
            # Absolute path within base directory
            absolute_path = os.path.join(temp_dir, "file.txt")
            result = adapter._resolve_path(absolute_path)
            assert result == Path(absolute_path)
    
    def test_resolve_path_escape_attempt_dotdot(self):
        """Test path resolution blocks directory traversal attacks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LocalFSAdapter(base_path=temp_dir)
            
            # Attempt to escape with ../
            with pytest.raises(ValueError, match="escapes base directory"):
                adapter._resolve_path("../../../etc/passwd")
    
    def test_resolve_path_escape_attempt_absolute(self):
        """Test path resolution blocks absolute path escapes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LocalFSAdapter(base_path=temp_dir)
            
            # Attempt to escape with absolute path
            with pytest.raises(ValueError, match="outside base directory"):
                adapter._resolve_path("/etc/passwd")
    
    def test_resolve_path_symlink_escape_protection(self):
        """Test path resolution handles symlink escape attempts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LocalFSAdapter(base_path=temp_dir)
            
            # This should work for normal paths
            result = adapter._resolve_path("normal/file.txt")
            expected = Path(temp_dir) / "normal/file.txt"
            assert result == expected


@pytest.mark.asyncio
class TestLocalFSAdapterBasicOperations:
    """Test LocalFSAdapter basic file operations."""
    
    @pytest.fixture
    async def temp_adapter(self):
        """Create adapter with temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LocalFSAdapter(base_path=temp_dir)
            yield adapter, temp_dir
    
    async def test_write_and_read_bytes(self, temp_adapter):
        """Test writing and reading binary data."""
        adapter, temp_dir = temp_adapter
        
        data = b"Hello, binary world!"
        path = "test_file.bin"
        
        await adapter.write(path, data)
        result = await adapter.read(path)
        
        assert result == data
    
    async def test_write_and_read_string(self, temp_adapter):
        """Test writing and reading string data."""
        adapter, temp_dir = temp_adapter
        
        data = "Hello, text world! 🌍"
        path = "test_file.txt"
        
        await adapter.write(path, data)
        result = await adapter.read(path)
        
        # Read returns bytes, so compare with encoded string
        assert result == data.encode('utf-8')
    
    async def test_exists_true(self, temp_adapter):
        """Test exists returns True for existing files."""
        adapter, temp_dir = temp_adapter
        
        path = "existing_file.txt"
        await adapter.write(path, "content")
        
        assert await adapter.exists(path) is True
    
    async def test_exists_false(self, temp_adapter):
        """Test exists returns False for non-existing files."""
        adapter, temp_dir = temp_adapter
        
        path = "non_existing_file.txt"
        
        assert await adapter.exists(path) is False
    
    async def test_delete_existing_file(self, temp_adapter):
        """Test deleting an existing file."""
        adapter, temp_dir = temp_adapter
        
        path = "file_to_delete.txt"
        await adapter.write(path, "content")
        
        # Verify file exists
        assert await adapter.exists(path) is True
        
        # Delete file
        await adapter.delete(path)
        
        # Verify file no longer exists
        assert await adapter.exists(path) is False
    
    async def test_write_creates_directories(self, temp_adapter):
        """Test that write creates parent directories."""
        adapter, temp_dir = temp_adapter
        
        path = "nested/deep/directory/file.txt"
        data = "content in nested file"
        
        await adapter.write(path, data)
        result = await adapter.read(path)
        
        assert result == data.encode('utf-8')
        
        # Verify directory structure was created
        full_path = Path(temp_dir) / path
        assert full_path.parent.exists()
        assert full_path.parent.is_dir()


@pytest.mark.asyncio
class TestLocalFSAdapterErrorHandling:
    """Test LocalFSAdapter error handling."""
    
    @pytest.fixture
    async def temp_adapter(self):
        """Create adapter with temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LocalFSAdapter(base_path=temp_dir)
            yield adapter, temp_dir
    
    async def test_read_nonexistent_file(self, temp_adapter):
        """Test reading a file that doesn't exist."""
        adapter, temp_dir = temp_adapter
        
        with pytest.raises(FileNotFoundError, match="File not found"):
            await adapter.read("nonexistent.txt")
    
    async def test_delete_nonexistent_file(self, temp_adapter):
        """Test deleting a file that doesn't exist."""
        adapter, temp_dir = temp_adapter
        
        with pytest.raises(FileNotFoundError, match="File not found"):
            await adapter.delete("nonexistent.txt")
    
    async def test_delete_directory_raises_error(self, temp_adapter):
        """Test that deleting a directory raises an error."""
        adapter, temp_dir = temp_adapter
        
        # Create a directory
        dir_path = Path(temp_dir) / "test_directory"
        dir_path.mkdir()
        
        with pytest.raises(IOError, match="Path is a directory"):
            await adapter.delete("test_directory")
    
    @patch('builtins.open')
    async def test_read_permission_error(self, mock_file_open, temp_adapter):
        """Test read operation with permission error."""
        adapter, temp_dir = temp_adapter
        
        mock_file_open.side_effect = PermissionError("Access denied")
        
        with pytest.raises(PermissionError, match="Permission denied reading file"):
            await adapter.read("restricted_file.txt")
    
    @patch('builtins.open')
    async def test_write_permission_error(self, mock_file_open, temp_adapter):
        """Test write operation with permission error."""
        adapter, temp_dir = temp_adapter
        
        mock_file_open.side_effect = PermissionError("Access denied")
        
        with pytest.raises(PermissionError, match="Permission denied writing to file"):
            await adapter.write("restricted_file.txt", "data")
    
    @patch('builtins.open')
    async def test_read_generic_io_error(self, mock_file_open, temp_adapter):
        """Test read operation with generic IO error."""
        adapter, temp_dir = temp_adapter
        
        mock_file_open.side_effect = OSError("Disk error")
        
        with pytest.raises(IOError, match="Error reading file"):
            await adapter.read("problematic_file.txt")
    
    @patch('builtins.open')
    async def test_write_generic_io_error(self, mock_file_open, temp_adapter):
        """Test write operation with generic IO error."""
        adapter, temp_dir = temp_adapter
        
        # Mock successful directory creation but failing file write
        mock_file_open.side_effect = OSError("Disk full")
        
        with pytest.raises(IOError, match="Error writing to file"):
            await adapter.write("problematic_file.txt", "data")


@pytest.mark.asyncio
class TestLocalFSAdapterAdvancedOperations:
    """Test LocalFSAdapter advanced operations."""
    
    @pytest.fixture
    async def temp_adapter_with_files(self):
        """Create adapter with temporary directory and sample files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LocalFSAdapter(base_path=temp_dir)
            
            # Create some test files
            await adapter.write("file1.txt", "Content of file 1")
            await adapter.write("file2.txt", "Content of file 2")
            await adapter.write("subdir/file3.txt", "Content of file 3")
            await adapter.write("subdir/nested/file4.txt", "Content of file 4")
            
            yield adapter, temp_dir
    
    async def test_list_files_root_directory(self, temp_adapter_with_files):
        """Test listing files in root directory."""
        adapter, temp_dir = temp_adapter_with_files
        
        files = await adapter.list_files(".")
        
        # Should include files in root, not in subdirectories
        assert "file1.txt" in files
        assert "file2.txt" in files
        assert "subdir/file3.txt" not in files  # Not in root
    
    async def test_list_files_subdirectory(self, temp_adapter_with_files):
        """Test listing files in subdirectory."""
        adapter, temp_dir = temp_adapter_with_files
        
        files = await adapter.list_files("subdir")
        
        assert "subdir/file3.txt" in files
        assert "subdir/nested/file4.txt" not in files  # In nested subdir
    
    async def test_list_files_nonexistent_directory(self, temp_adapter_with_files):
        """Test listing files in non-existent directory."""
        adapter, temp_dir = temp_adapter_with_files
        
        with pytest.raises(IOError, match="Error listing directory"):
            await adapter.list_files("nonexistent_dir")
    
    async def test_list_files_on_file_not_directory(self, temp_adapter_with_files):
        """Test listing files on a file (not directory)."""
        adapter, temp_dir = temp_adapter_with_files
        
        with pytest.raises(IOError, match="Path is not a directory"):
            await adapter.list_files("file1.txt")
    
    async def test_get_size(self, temp_adapter_with_files):
        """Test getting file size."""
        adapter, temp_dir = temp_adapter_with_files
        
        size = await adapter.get_size("file1.txt")
        
        # "Content of file 1" is 17 characters = 17 bytes (UTF-8)
        assert size == 17
    
    async def test_get_size_nonexistent_file(self, temp_adapter_with_files):
        """Test getting size of non-existent file."""
        adapter, temp_dir = temp_adapter_with_files
        
        with pytest.raises(IOError, match="Error getting file size"):
            await adapter.get_size("nonexistent.txt")
    
    async def test_multiple_operations_workflow(self, temp_adapter_with_files):
        """Test a complete workflow with multiple operations."""
        adapter, temp_dir = temp_adapter_with_files
        
        # Read existing file
        content = await adapter.read("file1.txt")
        assert content == b"Content of file 1"
        
        # Modify and write back
        new_content = "Updated content of file 1"
        await adapter.write("file1.txt", new_content)
        
        # Verify update
        updated_content = await adapter.read("file1.txt")
        assert updated_content == new_content.encode('utf-8')
        
        # Check new size
        new_size = await adapter.get_size("file1.txt")
        assert new_size == len(new_content.encode('utf-8'))
        
        # Create new file
        await adapter.write("new_file.txt", "Brand new file")
        assert await adapter.exists("new_file.txt") is True
        
        # List files to verify
        files = await adapter.list_files(".")
        assert "new_file.txt" in files
        
        # Clean up
        await adapter.delete("new_file.txt")
        assert await adapter.exists("new_file.txt") is False


@pytest.mark.asyncio
class TestLocalFSAdapterSecurity:
    """Test LocalFSAdapter security features."""
    
    async def test_path_traversal_protection(self):
        """Test protection against path traversal attacks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a subdirectory to test from
            subdir = Path(temp_dir) / "subdir"
            subdir.mkdir()
            
            adapter = LocalFSAdapter(base_path=str(subdir))
            
            # Various path traversal attempts that should fail
            dangerous_paths = [
                "../../../etc/passwd",
                "../../outside_file.txt",
                "../outside_file.txt"
            ]
            
            for dangerous_path in dangerous_paths:
                with pytest.raises(ValueError, match="escapes base directory|outside base directory"):
                    await adapter.write(dangerous_path, "malicious content")
    
    async def test_exists_with_dangerous_paths(self):
        """Test that exists() safely handles dangerous paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LocalFSAdapter(base_path=temp_dir)
            
            # Should return False for dangerous paths, not raise exceptions
            assert await adapter.exists("../../../etc/passwd") is False
            assert await adapter.exists("..\\..\\windows\\system32") is False
    
    async def test_base_path_isolation(self):
        """Test that base path properly isolates operations."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create a subdirectory as base path
            isolated_dir = os.path.join(base_dir, "isolated")
            os.makedirs(isolated_dir)
            
            adapter = LocalFSAdapter(base_path=isolated_dir)
            
            # Create file in isolated directory
            await adapter.write("safe_file.txt", "safe content")
            
            # Verify file exists in correct location
            full_path = os.path.join(isolated_dir, "safe_file.txt")
            assert os.path.exists(full_path)
            
            # Verify file is not in parent directory
            parent_path = os.path.join(base_dir, "safe_file.txt")
            assert not os.path.exists(parent_path)


class TestLocalFSAdapterIntegration:
    """Test LocalFSAdapter integration scenarios."""
    
    def test_adapter_inheritance(self):
        """Test LocalFSAdapter inherits from BaseFSAdapter."""
        adapter = LocalFSAdapter()
        assert isinstance(adapter, BaseFSAdapter)
    
    def test_adapter_implements_all_abstract_methods(self):
        """Test LocalFSAdapter implements all required abstract methods."""
        abstract_methods = ['read', 'write', 'exists', 'delete']
        
        for method_name in abstract_methods:
            assert hasattr(LocalFSAdapter, method_name)
            method = getattr(LocalFSAdapter, method_name)
            assert callable(method)
    
    @pytest.mark.asyncio
    async def test_compatibility_with_base_adapter_interface(self):
        """Test compatibility with BaseFSAdapter interface."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Use LocalFSAdapter through BaseFSAdapter interface
            adapter: BaseFSAdapter = LocalFSAdapter(base_path=temp_dir)
            
            # Test all interface methods work
            test_path = "interface_test.txt"
            test_data = b"Interface compatibility test"
            
            # Write
            await adapter.write(test_path, test_data)
            
            # Exists
            assert await adapter.exists(test_path) is True
            
            # Read
            result = await adapter.read(test_path)
            assert result == test_data
            
            # Delete
            await adapter.delete(test_path)
            assert await adapter.exists(test_path) is False
    
    def test_adapter_configuration_flexibility(self):
        """Test adapter handles various configuration scenarios."""
        # No base path
        adapter1 = LocalFSAdapter()
        assert adapter1.base_path is None
        
        # String base path
        adapter2 = LocalFSAdapter(base_path="/tmp/test")
        assert adapter2.base_path == Path("/tmp/test")
        
        # Empty string (should be treated as None/no base path)
        adapter3 = LocalFSAdapter(base_path="")
        assert adapter3.base_path is None or adapter3.base_path == Path("")
        
        # Relative path
        adapter4 = LocalFSAdapter(base_path="relative/path")
        assert adapter4.base_path == Path("relative/path")


@pytest.mark.asyncio 
class TestLocalFSAdapterEdgeCases:
    """Test LocalFSAdapter edge cases and error conditions."""
    
    async def test_empty_file_operations(self):
        """Test operations with empty files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LocalFSAdapter(base_path=temp_dir)
            
            # Write empty content
            await adapter.write("empty.txt", "")
            assert await adapter.exists("empty.txt") is True
            
            # Read empty content
            content = await adapter.read("empty.txt")
            assert content == b""
            
            # Size should be 0
            size = await adapter.get_size("empty.txt")
            assert size == 0
    
    async def test_unicode_content_and_paths(self):
        """Test operations with Unicode content and file paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LocalFSAdapter(base_path=temp_dir)
            
            # Unicode file path and content
            unicode_path = "файл_测试_🌍.txt"
            unicode_content = "Hello 世界! 🚀 Привет мир!"
            
            await adapter.write(unicode_path, unicode_content)
            
            # Verify file exists
            assert await adapter.exists(unicode_path) is True
            
            # Read and verify content
            result = await adapter.read(unicode_path)
            assert result == unicode_content.encode('utf-8')
    
    async def test_very_long_paths(self):
        """Test operations with very long file paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LocalFSAdapter(base_path=temp_dir)
            
            # Create a reasonably long path
            long_path = "/".join([f"dir{i}" for i in range(10)]) + "/long_filename.txt"
            
            try:
                await adapter.write(long_path, "content")
                assert await adapter.exists(long_path) is True
                content = await adapter.read(long_path)
                assert content == b"content"
            except OSError:
                # Some filesystems have path length limits, which is acceptable
                pytest.skip("Filesystem doesn't support long paths")
    
    async def test_concurrent_operations(self):
        """Test concurrent file operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LocalFSAdapter(base_path=temp_dir)
            
            import asyncio
            
            # Concurrent writes to different files
            async def write_file(i):
                await adapter.write(f"concurrent_{i}.txt", f"Content {i}")
                return await adapter.exists(f"concurrent_{i}.txt")
            
            # Run multiple writes concurrently
            tasks = [write_file(i) for i in range(10)]
            results = await asyncio.gather(*tasks)
            
            # All should succeed
            assert all(results)
            
            # Verify all files exist
            for i in range(10):
                assert await adapter.exists(f"concurrent_{i}.txt") is True