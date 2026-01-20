"""Comprehensive tests for Filesystem error classifier using errno codes."""

import errno
import pytest
from lamia.adapters.error_classifiers.filesystem import FilesystemErrorClassifier
from lamia.adapters.error_classifiers.base import ErrorClassifier
from lamia.adapters.error_classifiers.categories import ErrorCategory


def make_os_error(errno_code: int, message: str = "") -> OSError:
    """Create an OSError with a specific errno code."""
    error = OSError(message)
    error.errno = errno_code
    return error


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
    
    def test_file_exists_error_classification(self):
        """Test that FileExistsError is classified as permanent."""
        errors = [
            FileExistsError("File already exists"),
            FileExistsError("/path/to/file already exists"),
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


class TestFilesystemErrorClassifierPermanentErrnoCodes:
    """Test FilesystemErrorClassifier permanent errno code detection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
    def test_enoent_no_such_file(self):
        """Test ENOENT (No such file or directory) is permanent."""
        error = make_os_error(errno.ENOENT, "No such file or directory")
        assert self.classifier.classify_error(error) == ErrorCategory.PERMANENT
    
    def test_eacces_permission_denied(self):
        """Test EACCES (Permission denied) is permanent."""
        error = make_os_error(errno.EACCES, "Permission denied")
        assert self.classifier.classify_error(error) == ErrorCategory.PERMANENT
    
    def test_eperm_operation_not_permitted(self):
        """Test EPERM (Operation not permitted) is permanent."""
        error = make_os_error(errno.EPERM, "Operation not permitted")
        assert self.classifier.classify_error(error) == ErrorCategory.PERMANENT
    
    def test_enotdir_not_a_directory(self):
        """Test ENOTDIR (Not a directory) is permanent."""
        error = make_os_error(errno.ENOTDIR, "Not a directory")
        assert self.classifier.classify_error(error) == ErrorCategory.PERMANENT
    
    def test_eisdir_is_a_directory(self):
        """Test EISDIR (Is a directory) is permanent."""
        error = make_os_error(errno.EISDIR, "Is a directory")
        assert self.classifier.classify_error(error) == ErrorCategory.PERMANENT
    
    def test_eexist_file_exists(self):
        """Test EEXIST (File exists) is permanent."""
        error = make_os_error(errno.EEXIST, "File exists")
        assert self.classifier.classify_error(error) == ErrorCategory.PERMANENT
    
    def test_enotempty_directory_not_empty(self):
        """Test ENOTEMPTY (Directory not empty) is permanent."""
        error = make_os_error(errno.ENOTEMPTY, "Directory not empty")
        assert self.classifier.classify_error(error) == ErrorCategory.PERMANENT
    
    def test_erofs_read_only_filesystem(self):
        """Test EROFS (Read-only filesystem) is permanent."""
        error = make_os_error(errno.EROFS, "Read-only filesystem")
        assert self.classifier.classify_error(error) == ErrorCategory.PERMANENT
    
    def test_enametoolong_filename_too_long(self):
        """Test ENAMETOOLONG (Filename too long) is permanent."""
        error = make_os_error(errno.ENAMETOOLONG, "Filename too long")
        assert self.classifier.classify_error(error) == ErrorCategory.PERMANENT
    
    def test_einval_invalid_argument(self):
        """Test EINVAL (Invalid argument) is permanent."""
        error = make_os_error(errno.EINVAL, "Invalid argument")
        assert self.classifier.classify_error(error) == ErrorCategory.PERMANENT
    
    def test_eloop_too_many_symlinks(self):
        """Test ELOOP (Too many symbolic links) is permanent."""
        error = make_os_error(errno.ELOOP, "Too many symbolic links")
        assert self.classifier.classify_error(error) == ErrorCategory.PERMANENT
    
    def test_exdev_cross_device_link(self):
        """Test EXDEV (Cross-device link) is permanent."""
        error = make_os_error(errno.EXDEV, "Cross-device link")
        assert self.classifier.classify_error(error) == ErrorCategory.PERMANENT


class TestFilesystemErrorClassifierTransientExceptionTypes:
    """Test FilesystemErrorClassifier transient exception type detection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
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
    
    def test_interrupted_error_classification(self):
        """Test that InterruptedError is classified as transient."""
        errors = [
            InterruptedError("Interrupted system call"),
            InterruptedError("System call interrupted"),
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for error: {error}"
    
    def test_timeout_error_classification(self):
        """Test that TimeoutError is classified as transient."""
        errors = [
            TimeoutError("Operation timed out"),
            TimeoutError("Connection timed out"),
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for error: {error}"


class TestFilesystemErrorClassifierTransientErrnoCodes:
    """Test FilesystemErrorClassifier transient errno code detection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
    def test_enospc_no_space_left(self):
        """Test ENOSPC (No space left on device) is transient."""
        error = make_os_error(errno.ENOSPC, "No space left on device")
        assert self.classifier.classify_error(error) == ErrorCategory.TRANSIENT
    
    def test_eagain_try_again(self):
        """Test EAGAIN (Resource temporarily unavailable) is transient."""
        error = make_os_error(errno.EAGAIN, "Resource temporarily unavailable")
        assert self.classifier.classify_error(error) == ErrorCategory.TRANSIENT
    
    def test_ebusy_device_busy(self):
        """Test EBUSY (Device or resource busy) is transient."""
        error = make_os_error(errno.EBUSY, "Device or resource busy")
        assert self.classifier.classify_error(error) == ErrorCategory.TRANSIENT
    
    def test_etxtbsy_text_file_busy(self):
        """Test ETXTBSY (Text file busy) is transient."""
        error = make_os_error(errno.ETXTBSY, "Text file busy")
        assert self.classifier.classify_error(error) == ErrorCategory.TRANSIENT
    
    def test_enolck_no_locks_available(self):
        """Test ENOLCK (No locks available) is transient."""
        error = make_os_error(errno.ENOLCK, "No locks available")
        assert self.classifier.classify_error(error) == ErrorCategory.TRANSIENT
    
    def test_eintr_interrupted_call(self):
        """Test EINTR (Interrupted system call) is transient."""
        error = make_os_error(errno.EINTR, "Interrupted system call")
        assert self.classifier.classify_error(error) == ErrorCategory.TRANSIENT
    
    def test_enomem_out_of_memory(self):
        """Test ENOMEM (Out of memory) is transient."""
        error = make_os_error(errno.ENOMEM, "Cannot allocate memory")
        assert self.classifier.classify_error(error) == ErrorCategory.TRANSIENT
    
    def test_emfile_too_many_open_files(self):
        """Test EMFILE (Too many open files) is transient."""
        error = make_os_error(errno.EMFILE, "Too many open files")
        assert self.classifier.classify_error(error) == ErrorCategory.TRANSIENT
    
    def test_enfile_file_table_overflow(self):
        """Test ENFILE (File table overflow) is transient."""
        error = make_os_error(errno.ENFILE, "File table overflow")
        assert self.classifier.classify_error(error) == ErrorCategory.TRANSIENT
    
    def test_eio_io_error(self):
        """Test EIO (I/O error) is transient."""
        error = make_os_error(errno.EIO, "I/O error")
        assert self.classifier.classify_error(error) == ErrorCategory.TRANSIENT
    
    @pytest.mark.skipif(not hasattr(errno, 'EDQUOT'), reason="EDQUOT not available on this platform")
    def test_edquot_disk_quota_exceeded(self):
        """Test EDQUOT (Disk quota exceeded) is transient."""
        error = make_os_error(errno.EDQUOT, "Disk quota exceeded")
        assert self.classifier.classify_error(error) == ErrorCategory.TRANSIENT


class TestFilesystemErrorClassifierDefaultBehavior:
    """Test FilesystemErrorClassifier default behavior and decision priority."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
    def test_exception_type_takes_priority_over_errno(self):
        """Test that built-in exception types take priority."""
        # PermissionError is permanent regardless of errno
        error = PermissionError("test")
        error.errno = errno.ENOSPC  # Transient errno
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT  # Exception type wins
    
    def test_default_classification_for_unknown_errors(self):
        """Test default classification for unknown errors."""
        unknown_errors = [
            Exception("Unknown error"),
            ValueError("Value error"),
            RuntimeError("Runtime error"),
        ]
        
        for error in unknown_errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT  # Conservative default
    
    def test_os_error_without_errno_is_transient(self):
        """Test that OSError without errno defaults to transient."""
        error = OSError("Some error without errno")
        error.errno = None
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.TRANSIENT
    
    def test_no_rate_limiting_classification(self):
        """Test that filesystem errors don't classify as RATE_LIMIT."""
        errors = [
            PermissionError("test"),
            FileNotFoundError("test"),
            make_os_error(errno.ENOSPC, "test"),
            make_os_error(errno.EBUSY, "test"),
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert result in [ErrorCategory.PERMANENT, ErrorCategory.TRANSIENT]
    
    def test_classification_consistency(self):
        """Test that classification is consistent for the same error."""
        error = FileNotFoundError("File not found")
        
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
            FileNotFoundError(""),
            PermissionError(""),
            make_os_error(errno.ENOENT, ""),
            make_os_error(errno.ENOSPC, ""),
        ]
        
        expected = [
            ErrorCategory.PERMANENT,  # FileNotFoundError
            ErrorCategory.PERMANENT,  # PermissionError
            ErrorCategory.PERMANENT,  # ENOENT
            ErrorCategory.TRANSIENT,  # ENOSPC
        ]
        
        for error, exp in zip(empty_errors, expected):
            result = self.classifier.classify_error(error)
            assert result == exp, f"Failed for error: {error}"
    
    def test_none_error_handling(self):
        """Test handling of None error."""
        try:
            result = self.classifier.classify_error(None)
            assert result == ErrorCategory.TRANSIENT
        except (TypeError, AttributeError):
            pass  # Acceptable if implementation doesn't handle None
    
    def test_nested_exception_handling(self):
        """Test handling of nested/chained exceptions."""
        try:
            raise FileNotFoundError("Original file not found")
        except FileNotFoundError:
            nested_error = OSError("Failed to handle file operation")
        
        result = self.classifier.classify_error(nested_error)
        assert isinstance(result, ErrorCategory)
    
    def test_custom_exception_subclass(self):
        """Test handling of custom exception types that inherit from OS exceptions."""
        class CustomPermissionError(PermissionError):
            pass
        
        class CustomFileNotFoundError(FileNotFoundError):
            pass
        
        errors = [
            CustomPermissionError("custom permission denied"),
            CustomFileNotFoundError("custom file not found"),
        ]
        
        for error in errors:
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT
    
    def test_os_error_subclass_with_errno(self):
        """Test OSError subclass with custom errno."""
        class CustomOSError(OSError):
            pass
        
        error = CustomOSError("test")
        error.errno = errno.ENOENT
        result = self.classifier.classify_error(error)
        assert result == ErrorCategory.PERMANENT
        
        error2 = CustomOSError("test")
        error2.errno = errno.ENOSPC
        result2 = self.classifier.classify_error(error2)
        assert result2 == ErrorCategory.TRANSIENT


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
            (make_os_error(errno.ENOSPC, "No space left on device"), ErrorCategory.TRANSIENT),
            (make_os_error(errno.EBUSY, "File is busy"), ErrorCategory.TRANSIENT),
        ]
        
        for error, expected_category in copy_errors:
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for copy error: {error}"
    
    def test_database_file_operation_errors(self):
        """Test classification of database file operation errors."""
        db_errors = [
            (make_os_error(errno.EBUSY, "Database file is locked"), ErrorCategory.TRANSIENT),
            (PermissionError("Cannot write to database directory"), ErrorCategory.PERMANENT),
            (make_os_error(errno.EROFS, "Read-only filesystem"), ErrorCategory.PERMANENT),
            (make_os_error(errno.EAGAIN, "Try again"), ErrorCategory.TRANSIENT),
        ]
        
        for error, expected_category in db_errors:
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for database error: {error}"
    
    def test_log_file_rotation_errors(self):
        """Test classification of log file rotation errors."""
        log_errors = [
            (make_os_error(errno.ENOSPC, "Cannot rotate log: disk space full"), ErrorCategory.TRANSIENT),
            (PermissionError("Log directory not writable"), ErrorCategory.PERMANENT),
            (make_os_error(errno.ETXTBSY, "Log file busy"), ErrorCategory.TRANSIENT),
            (FileNotFoundError("Log directory does not exist"), ErrorCategory.PERMANENT),
        ]
        
        for error, expected_category in log_errors:
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for log rotation error: {error}"
    
    def test_backup_operation_errors(self):
        """Test classification of backup operation errors."""
        backup_errors = [
            (make_os_error(errno.ENOSPC, "Backup destination full"), ErrorCategory.TRANSIENT),
            (PermissionError("Cannot access backup directory"), ErrorCategory.PERMANENT),
            (make_os_error(errno.EIO, "I/O error on network backup"), ErrorCategory.TRANSIENT),
            (FileNotFoundError("Backup source files missing"), ErrorCategory.PERMANENT),
        ]
        
        for error, expected_category in backup_errors:
            result = self.classifier.classify_error(error)
            assert result == expected_category, f"Failed for backup error: {error}"


class TestFilesystemErrorClassifierAllPermanentErrno:
    """Test all permanent errno codes are handled correctly."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
    def test_all_permanent_errno_codes(self):
        """Test that all documented permanent errno codes return PERMANENT."""
        permanent_codes = [
            (errno.ENOENT, "No such file or directory"),
            (errno.EACCES, "Permission denied"),
            (errno.EPERM, "Operation not permitted"),
            (errno.ENOTDIR, "Not a directory"),
            (errno.EISDIR, "Is a directory"),
            (errno.EEXIST, "File exists"),
            (errno.ENOTEMPTY, "Directory not empty"),
            (errno.EROFS, "Read-only filesystem"),
            (errno.ENAMETOOLONG, "Filename too long"),
            (errno.EINVAL, "Invalid argument"),
            (errno.ELOOP, "Too many symbolic links"),
            (errno.EXDEV, "Cross-device link"),
        ]
        
        for code, message in permanent_codes:
            error = make_os_error(code, message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.PERMANENT, f"Failed for errno {code}: {message}"


class TestFilesystemErrorClassifierAllTransientErrno:
    """Test all transient errno codes are handled correctly."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = FilesystemErrorClassifier()
    
    def test_all_transient_errno_codes(self):
        """Test that all documented transient errno codes return TRANSIENT."""
        transient_codes = [
            (errno.ENOSPC, "No space left on device"),
            (errno.EAGAIN, "Resource temporarily unavailable"),
            (errno.EBUSY, "Device or resource busy"),
            (errno.ETXTBSY, "Text file busy"),
            (errno.ENOLCK, "No locks available"),
            (errno.EINTR, "Interrupted system call"),
            (errno.ENOMEM, "Cannot allocate memory"),
            (errno.EMFILE, "Too many open files"),
            (errno.ENFILE, "File table overflow"),
            (errno.EIO, "I/O error"),
        ]
        
        for code, message in transient_codes:
            error = make_os_error(code, message)
            result = self.classifier.classify_error(error)
            assert result == ErrorCategory.TRANSIENT, f"Failed for errno {code}: {message}"
