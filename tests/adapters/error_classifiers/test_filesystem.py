"""Comprehensive tests for Filesystem error classifier."""

import pytest
from unittest.mock import Mock
from lamia.adapters.error_classifiers.filesystem import FilesystemErrorClassifier
from lamia.adapters.error_classifiers.base import ErrorClassifier
from lamia.adapters.error_classifiers.categories import ErrorCategory


class TestFilesystemErrorClassifierInterface:
    """Test FilesystemErrorClassifier interface and inheritance."""
    
    def test_inherits_from_error_classifier(self):
        """Test that FilesystemErrorClassifier inherits from ErrorClassifier."""
        classifier = FilesystemErrorClassifier()
        assert isinstance(classifier, ErrorClassifier)
    
    def test_implements_classify_error_method(self):
        """Test that FilesystemErrorClassifier implements classify_error."""
        assert hasattr(FilesystemErrorClassifier, 'classify_error')
        assert callable(FilesystemErrorClassifier.classify_error)
    
    def test_can_instantiate(self):
        """Test that FilesystemErrorClassifier can be instantiated."""
        classifier = FilesystemErrorClassifier()
        assert classifier is not None
        assert isinstance(classifier, FilesystemErrorClassifier)


class TestFilesystemErrorClassifierPermanentExceptionTypes:
    """Test FilesystemErrorClassifier permanent exception type detection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
    def test_permission_error_classification(self):
        """Test that PermissionError is classified as permanent."""
        errors = [
            PermissionError("Access denied"),
            PermissionError("Permission denied to access file"),
            PermissionError("Operation not permitted")
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for error: {error}"
    
    def test_file_not_found_error_classification(self):
        """Test that FileNotFoundError is classified as permanent."""
        errors = [
            FileNotFoundError("File not found"),
            FileNotFoundError("No such file or directory"),
            FileNotFoundError("/path/to/file.txt does not exist")
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for error: {error}"
    
    def test_directory_errors_classification(self):
        """Test that directory-related errors are classified as permanent."""
        errors = [
            NotADirectoryError("Not a directory"),
            IsADirectoryError("Is a directory"),
            NotADirectoryError("/path/to/file is not a directory"),
            IsADirectoryError("/path/to/dir is a directory")
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for error: {error}"


class TestFilesystemErrorClassifierPermanentMessagePatterns:
    """Test FilesystemErrorClassifier permanent error message pattern detection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
    def test_permission_message_patterns(self):
        """Test detection of permission-related error messages."""
        permission_messages = [
            "permission denied to access file",
            "access denied for user",
            "insufficient permissions",
            "operation not permitted for user"
        ]
        
        for message in permission_messages:
            error = OSError(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"
    
    def test_file_not_found_message_patterns(self):
        """Test detection of file not found error messages."""
        not_found_messages = [
            "no such file or directory",
            "file not found on filesystem",
            "cannot find specified file",
            "path does not exist"
        ]
        
        for message in not_found_messages:
            error = IOError(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"
    
    def test_directory_message_patterns(self):
        """Test detection of directory-related error messages."""
        directory_messages = [
            "directory not found on system",
            "not a directory as expected",
            "is a directory, not a file",
            "cannot access directory"
        ]
        
        for message in directory_messages:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"
    
    def test_invalid_path_message_patterns(self):
        """Test detection of invalid path error messages."""
        invalid_path_messages = [
            "invalid path format",
            "path contains invalid characters", 
            "malformed file path",
            "illegal path specification"
        ]
        
        for message in invalid_path_messages:
            error = ValueError(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"
    
    def test_read_only_filesystem_patterns(self):
        """Test detection of read-only filesystem errors."""
        readonly_messages = [
            "read-only filesystem",
            "cannot write to read-only file", 
            "filesystem mounted read-only",
            "write operation on read-only volume"
        ]
        
        for message in readonly_messages:
            error = OSError(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"
    
    def test_permanent_error_case_insensitive(self):
        """Test that permanent error detection is case insensitive."""
        case_variations = [
            "PERMISSION DENIED",
            "Permission Denied",
            "NO SUCH FILE",
            "File Not Found",
            "READ-ONLY FILESYSTEM",
            "Invalid Path"
        ]
        
        for message in case_variations:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for message: {message}"


class TestFilesystemErrorClassifierTransientExceptionTypes:
    """Test FilesystemErrorClassifier transient exception type detection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
    def test_os_error_with_transient_patterns(self):
        """Test that OSError with transient patterns is classified correctly."""
        transient_os_errors = [
            OSError("disk space full"),
            OSError("device busy, try again"),
            OSError("temporary failure"),
            OSError("resource temporarily unavailable")
        ]
        
        for error in transient_os_errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for error: {error}"
    
    def test_io_error_with_transient_patterns(self):
        """Test that IOError with transient patterns is classified correctly."""
        transient_io_errors = [
            IOError("disk quota exceeded"),
            IOError("file lock conflict"),
            IOError("device temporarily unavailable"),
            IOError("resource busy, please retry")
        ]
        
        for error in transient_io_errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for error: {error}"
    
    def test_blocking_io_error_classification(self):
        """Test that BlockingIOError is classified as transient."""
        errors = [
            BlockingIOError("Resource temporarily unavailable"),
            BlockingIOError("Operation would block"),
            BlockingIOError("Try again later")
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for error: {error}"
    
    def test_os_error_with_permanent_patterns(self):
        """Test that OSError with permanent patterns is classified as permanent."""
        permanent_os_errors = [
            OSError("permission denied"),
            OSError("no such file or directory"),
            OSError("not a directory"),
            OSError("operation not permitted")
        ]
        
        for error in permanent_os_errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for error: {error}"


class TestFilesystemErrorClassifierTransientMessagePatterns:
    """Test FilesystemErrorClassifier transient error message pattern detection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
    def test_disk_space_patterns(self):
        """Test detection of disk space related errors."""
        disk_space_messages = [
            "disk space insufficient",
            "no space left on device",
            "disk full error occurred",
            "storage capacity exceeded"
        ]
        
        for message in disk_space_messages:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_file_lock_patterns(self):
        """Test detection of file lock related errors."""
        lock_messages = [
            "file is locked by another process",
            "resource lock conflict",
            "file busy, cannot access",
            "lock acquisition failed"
        ]
        
        for message in lock_messages:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_temporary_resource_patterns(self):
        """Test detection of temporary resource errors."""
        resource_messages = [
            "temporary resource unavailable", 
            "resource busy, try again",
            "temporary failure, please retry",
            "resource allocation failed"
        ]
        
        for message in resource_messages:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_quota_patterns(self):
        """Test detection of quota-related errors."""
        quota_messages = [
            "disk quota exceeded for user",
            "user quota limit reached", 
            "file quota exceeded",
            "inode quota exceeded"
        ]
        
        for message in quota_messages:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_device_busy_patterns(self):
        """Test detection of device busy errors."""
        busy_messages = [
            "device or resource busy",
            "filesystem busy, cannot unmount",
            "disk busy with another operation",
            "device temporarily busy"
        ]
        
        for message in busy_messages:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"
    
    def test_transient_error_case_insensitive(self):
        """Test that transient error detection is case insensitive."""
        case_variations = [
            "DISK SPACE FULL",
            "Disk Space Full",
            "FILE LOCK CONFLICT", 
            "Resource Temporarily Unavailable",
            "QUOTA EXCEEDED",
            "Device Busy"
        ]
        
        for message in case_variations:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for message: {message}"


class TestFilesystemErrorClassifierPlatformSpecificErrors:
    """Test FilesystemErrorClassifier with platform-specific filesystem errors."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
    def test_windows_filesystem_errors(self):
        """Test classification of Windows-specific filesystem errors."""
        windows_errors = [
            ("Access is denied", ErrorCategory.PERMANENT),
            ("The system cannot find the file specified", ErrorCategory.PERMANENT),
            ("The disk is full", ErrorCategory.TRANSIENT),
            ("Sharing violation", ErrorCategory.TRANSIENT),
            ("The filename, directory name, or volume label syntax is incorrect", ErrorCategory.PERMANENT)
        ]
        
        for message, expected_category in windows_errors:
            error = OSError(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for Windows error: {message}"
    
    def test_unix_filesystem_errors(self):
        """Test classification of Unix/Linux-specific filesystem errors."""
        unix_errors = [
            ("Permission denied", ErrorCategory.PERMANENT),
            ("No such file or directory", ErrorCategory.PERMANENT), 
            ("Device or resource busy", ErrorCategory.TRANSIENT),
            ("No space left on device", ErrorCategory.TRANSIENT),
            ("Too many open files", ErrorCategory.TRANSIENT)
        ]
        
        for message, expected_category in unix_errors:
            error = OSError(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for Unix error: {message}"
    
    def test_macos_filesystem_errors(self):
        """Test classification of macOS-specific filesystem errors."""
        macos_errors = [
            ("Operation not permitted", ErrorCategory.PERMANENT),
            ("Resource fork access denied", ErrorCategory.PERMANENT),
            ("Volume is read-only", ErrorCategory.PERMANENT),
            ("File is locked", ErrorCategory.TRANSIENT)
        ]
        
        for message, expected_category in macos_errors:
            error = OSError(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for macOS error: {message}"


class TestFilesystemErrorClassifierNetworkFilesystems:
    """Test FilesystemErrorClassifier with network filesystem errors."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
    def test_nfs_errors(self):
        """Test classification of NFS (Network File System) errors."""
        nfs_errors = [
            ("NFS server not responding", ErrorCategory.TRANSIENT),
            ("Stale file handle", ErrorCategory.TRANSIENT),
            ("NFS: directory not empty", ErrorCategory.PERMANENT),
            ("Permission denied by NFS server", ErrorCategory.PERMANENT)
        ]
        
        for message, expected_category in nfs_errors:
            error = OSError(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for NFS error: {message}"
    
    def test_smb_cifs_errors(self):
        """Test classification of SMB/CIFS network filesystem errors."""
        smb_errors = [
            ("SMB connection lost", ErrorCategory.TRANSIENT),
            ("CIFS share not accessible", ErrorCategory.TRANSIENT),
            ("Access denied to network share", ErrorCategory.PERMANENT),
            ("Network path not found", ErrorCategory.PERMANENT)
        ]
        
        for message, expected_category in smb_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for SMB/CIFS error: {message}"
    
    def test_cloud_filesystem_errors(self):
        """Test classification of cloud filesystem errors."""
        cloud_errors = [
            ("S3 bucket access denied", ErrorCategory.PERMANENT),
            ("Azure blob not found", ErrorCategory.PERMANENT),
            ("GCS temporary service unavailable", ErrorCategory.TRANSIENT),
            ("Cloud storage quota exceeded", ErrorCategory.TRANSIENT)
        ]
        
        for message, expected_category in cloud_errors:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for cloud storage error: {message}"


class TestFilesystemErrorClassifierDefaultBehavior:
    """Test FilesystemErrorClassifier default behavior and decision priority."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
    def test_permanent_takes_priority_over_transient(self):
        """Test that permanent classification takes priority over transient."""
        # Error with both permanent and transient indicators
        mixed_error = OSError("permission denied - disk space full")
        result = self.classifier.classify_error(mixed_error)
        assert result == ErrorCategory.PERMANENT  # Should prioritize permanent
    
    def test_exception_type_takes_priority_over_message(self):
        """Test that exception type takes priority over message patterns."""
        # PermissionError with transient-like message
        error = PermissionError("temporary resource unavailable")
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT  # Exception type wins
    
    def test_default_classification_for_unknown_errors(self):
        """Test default classification for unknown filesystem errors."""
        unknown_errors = [
            Exception("Unknown filesystem error"),
            Exception("Mysterious file operation failure"),
            ValueError("Non-filesystem related error"),
            RuntimeError("Generic runtime error")
        ]
        
        for error in unknown_errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT  # Should default to transient (conservative)
    
    def test_no_rate_limiting_classification(self):
        """Test that filesystem errors don't classify as RATE_LIMIT."""
        # Filesystem operations typically don't have rate limiting
        potential_rate_limit_messages = [
            "too many file operations",
            "operation rate exceeded",
            "throttling filesystem access"
        ]
        
        for message in potential_rate_limit_messages:
            error = Exception(message)
            result = self.classifier.classify_error(error)
            # Should be permanent or transient, never rate limit
            assert result in [ErrorCategory.PERMANENT, ErrorCategory.TRANSIENT]
    
    def test_classification_consistency(self):
        """Test that classification is consistent for the same error."""
        error = FileNotFoundError("File not found")
        
        # Should return same result multiple times
        result1 = self.classifier.classify_error(error)
        result2 = self.classifier.classify_error(error)
        result3 = self.classifier.classify_error(error)
        
        assert result1 == result2 == result3
        assert result1 == ErrorCategory.PERMANENT


class TestFilesystemErrorClassifierEdgeCases:
    """Test FilesystemErrorClassifier edge cases and error handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
    def test_empty_error_message(self):
        """Test handling of errors with empty messages."""
        empty_errors = [
            OSError(""),
            IOError(""),
            FileNotFoundError(""),
            PermissionError("")
        ]
        
        for error in empty_errors:
            result = self.classifier.classify_error(error)
            # Should classify based on exception type, not message
            if isinstance(error, (FileNotFoundError, PermissionError)):
                assert result == ErrorCategory.PERMANENT
            else:
                assert result == ErrorCategory.TRANSIENT
    
    def test_none_error_handling(self):
        """Test handling of None error."""
        try:
            result = self.classifier.classify_error(None)
            assert result == ErrorCategory.TRANSIENT
        except (TypeError, AttributeError):
            # Acceptable if implementation doesn't handle None
            pass
    
    def test_unicode_error_messages(self):
        """Test handling of Unicode error messages."""
        unicode_errors = [
            OSError("\u6587\u4ef6\u672a\u627e\u5230 (file not found)"),
            PermissionError("\u8bbf\u95ee\u88ab\u62d2\u7edd (access denied)"),
            IOError("\u78c1\u76d8\u7a7a\u95f4\u4e0d\u8db3 (disk space insufficient)")
        ]
        
        expected = [ErrorCategory.PERMANENT, ErrorCategory.PERMANENT, ErrorCategory.TRANSIENT]
        
        for error, expected_category in zip(unicode_errors, expected):
            result = self.classifier.classify_error(error)
            assert result == expected_category
    
    def test_nested_exception_handling(self):
        """Test handling of nested/chained exceptions."""
        # Simulate a nested exception scenario
        try:
            raise FileNotFoundError("Original file not found")
        except FileNotFoundError as e:
            nested_error = OSError("Failed to handle file operation")
        
        result = self.classifier.classify_error(nested_error)
        assert isinstance(result, ErrorCategory)
    
    def test_custom_exception_types(self):
        """Test handling of custom filesystem exception types."""
        class CustomFilesystemError(OSError):
            def __init__(self, message, error_code=None):
                super().__init__(message)
                self.error_code = error_code
        
        class CustomPermissionError(PermissionError):
            pass
        
        errors = [
            CustomFilesystemError("disk space full", error_code=28),
            CustomPermissionError("custom permission denied")
        ]
        
        expected = [ErrorCategory.TRANSIENT, ErrorCategory.PERMANENT]
        
        for error, expected_category in zip(errors, expected):
            result = self.classifier.classify_error(error)
            assert result == expected_category
    
    def test_very_long_error_messages(self):
        """Test handling of very long error messages."""
        long_message = "permission denied " * 1000
        error = PermissionError(long_message)
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT
    
    def test_error_message_with_paths(self):
        """Test handling of error messages containing file paths."""
        path_errors = [
            OSError("Permission denied: '/usr/local/bin/myfile.txt'"),
            FileNotFoundError("No such file: '/home/user/documents/file.doc'"),
            IOError("Disk full writing to: '/var/log/application.log'")
        ]
        
        expected = [ErrorCategory.PERMANENT, ErrorCategory.PERMANENT, ErrorCategory.TRANSIENT]
        
        for error, expected_category in zip(path_errors, expected):
            result = self.classifier.classify_error(error)
            assert result == expected_category


class TestFilesystemErrorClassifierIntegrationScenarios:
    """Test FilesystemErrorClassifier with realistic integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
    def test_file_copy_operation_errors(self):
        """Test classification of file copy operation errors."""
        copy_errors = [
            (PermissionError("Permission denied copying file"), ErrorCategory.PERMANENT),
            (FileNotFoundError("Source file not found"), ErrorCategory.PERMANENT),
            (OSError("No space left on device during copy"), ErrorCategory.TRANSIENT),
            (IOError("Disk quota exceeded during copy"), ErrorCategory.TRANSIENT)
        ]
        
        for error, expected_category in copy_errors:
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for copy error: {error}"
    
    def test_database_file_operation_errors(self):
        """Test classification of database file operation errors."""
        db_errors = [
            (OSError("Database file is locked"), ErrorCategory.TRANSIENT),
            (PermissionError("Cannot write to database directory"), ErrorCategory.PERMANENT),
            (IOError("Database disk image is malformed"), ErrorCategory.PERMANENT),
            (OSError("Temporary database failure"), ErrorCategory.TRANSIENT)
        ]
        
        for error, expected_category in db_errors:
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for database error: {error}"
    
    def test_log_file_rotation_errors(self):
        """Test classification of log file rotation errors."""
        log_errors = [
            (OSError("Cannot rotate log: disk space full"), ErrorCategory.TRANSIENT),
            (PermissionError("Log directory not writable"), ErrorCategory.PERMANENT),
            (IOError("Log file busy, cannot rotate"), ErrorCategory.TRANSIENT),
            (FileNotFoundError("Log directory does not exist"), ErrorCategory.PERMANENT)
        ]
        
        for error, expected_category in log_errors:
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for log rotation error: {error}"
    
    def test_backup_operation_errors(self):
        """Test classification of backup operation errors."""
        backup_errors = [
            (OSError("Backup destination full"), ErrorCategory.TRANSIENT),
            (PermissionError("Cannot access backup directory"), ErrorCategory.PERMANENT),
            (IOError("Network backup location unavailable"), ErrorCategory.TRANSIENT),
            (FileNotFoundError("Backup source files missing"), ErrorCategory.PERMANENT)
        ]
        
        for error, expected_category in backup_errors:
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for backup error: {error}"