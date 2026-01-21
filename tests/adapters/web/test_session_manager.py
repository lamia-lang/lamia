"""Tests for session manager."""

import json
import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from lamia.adapters.web.session_manager import SessionManager


class TestSessionManagerInitialization:
    """Test SessionManager initialization."""
    
    def test_default_initialization(self):
        """Test default SessionManager initialization."""
        config = {}
        session_manager = SessionManager(config)
        
        assert session_manager.enabled is True
        assert session_manager.session_dir == Path('./.lamia_sessions')
        assert session_manager.session_timeout_hours == 24
        assert session_manager.should_save_cookies is True
        assert session_manager.should_save_local_storage is True
    
    def test_custom_configuration(self):
        """Test SessionManager with custom configuration."""
        config = {
            'enabled': False,
            'session_timeout': 48,
            'save_cookies': False,
            'save_local_storage': False
        }
        session_manager = SessionManager(config)
        
        assert session_manager.enabled is False
        assert session_manager.session_timeout_hours == 48
        assert session_manager.should_save_cookies is False
        assert session_manager.should_save_local_storage is False
    
    @patch('pathlib.Path.mkdir')
    def test_session_directory_creation(self, mock_mkdir):
        """Test that session directory is created when enabled."""
        config = {'enabled': True}
        SessionManager(config)
        
        mock_mkdir.assert_called_once_with(exist_ok=True)
    
    @patch('pathlib.Path.mkdir')
    def test_no_directory_creation_when_disabled(self, mock_mkdir):
        """Test that session directory is not created when disabled."""
        config = {'enabled': False}
        SessionManager(config)
        
        mock_mkdir.assert_not_called()


class TestSessionKeyGeneration:
    """Test session key generation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.session_manager = SessionManager({'enabled': False})  # Disable to avoid directory creation
    
    def test_generate_session_key(self):
        """Test session key generation."""
        key1 = self.session_manager._generate_session_key("user123", "example.com")
        key2 = self.session_manager._generate_session_key("user123", "example.com")
        
        # Same input should produce same key
        assert key1 == key2
        
        # Key should be 12 characters
        assert len(key1) == 12
        
        # Different inputs should produce different keys
        key3 = self.session_manager._generate_session_key("user456", "example.com")
        assert key1 != key3
        
        key4 = self.session_manager._generate_session_key("user123", "different.com")
        assert key1 != key4
    
    def test_case_insensitive_key_generation(self):
        """Test that key generation is case insensitive."""
        key1 = self.session_manager._generate_session_key("User123", "Example.com")
        key2 = self.session_manager._generate_session_key("user123", "example.com")
        key3 = self.session_manager._generate_session_key("USER123", "EXAMPLE.COM")
        
        assert key1 == key2 == key3


class TestProfileSessionDirectories:
    """Test profile session directory management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.session_manager = SessionManager({'enabled': False})
    
    def test_get_profile_session_dir(self):
        """Test getting profile session directory."""
        profile_dir = self.session_manager.get_profile_session_dir("test_profile")
        expected = Path('./.lamia_sessions') / "test_profile"
        
        assert profile_dir == expected
    
    def test_get_cookies_file(self):
        """Test getting cookies file path."""
        cookies_file = self.session_manager.get_cookies_file("test_profile")
        expected = Path('./.lamia_sessions') / "test_profile" / "cookies.json"
        
        assert cookies_file == expected
    
    def test_get_local_storage_file(self):
        """Test getting local storage file path."""
        storage_file = self.session_manager.get_local_storage_file("test_profile")
        expected = Path('./.lamia_sessions') / "test_profile" / "local_storage.json"
        
        assert storage_file == expected


class TestSessionValidation:
    """Test session validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.session_manager = SessionManager({'enabled': True})
        self.temp_dir = Path(tempfile.mkdtemp())
        self.session_manager.session_dir = self.temp_dir
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_session_valid_when_disabled(self):
        """Test that session validation returns False when disabled."""
        disabled_manager = SessionManager({'enabled': False})
        assert not disabled_manager.is_session_valid("any_profile")
    
    def test_session_invalid_when_no_info_file(self):
        """Test that session is invalid when session info file doesn't exist."""
        assert not self.session_manager.is_session_valid("nonexistent_profile")
    
    def test_session_valid_within_timeout(self):
        """Test that session is valid when within timeout period."""
        profile_name = "valid_profile"
        session_dir = self.session_manager.get_profile_session_dir(profile_name)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        session_info = {
            'last_used': datetime.now().isoformat(),
            'profile_name': profile_name
        }
        
        session_info_file = session_dir / "session_info.json"
        with open(session_info_file, 'w') as f:
            json.dump(session_info, f)
        
        assert self.session_manager.is_session_valid(profile_name)
    
    def test_session_invalid_when_expired(self):
        """Test that session is invalid when expired."""
        profile_name = "expired_profile"
        session_dir = self.session_manager.get_profile_session_dir(profile_name)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Create session that expired 25 hours ago (default timeout is 24 hours)
        expired_time = datetime.now() - timedelta(hours=25)
        session_info = {
            'last_used': expired_time.isoformat(),
            'profile_name': profile_name
        }
        
        session_info_file = session_dir / "session_info.json"
        with open(session_info_file, 'w') as f:
            json.dump(session_info, f)
        
        assert not self.session_manager.is_session_valid(profile_name)
    
    def test_session_invalid_with_corrupted_json(self):
        """Test that session is invalid with corrupted JSON."""
        profile_name = "corrupted_profile"
        session_dir = self.session_manager.get_profile_session_dir(profile_name)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        session_info_file = session_dir / "session_info.json"
        with open(session_info_file, 'w') as f:
            f.write("invalid json {")
        
        assert not self.session_manager.is_session_valid(profile_name)


class TestSessionInfoManagement:
    """Test session info saving and updating."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.session_manager = SessionManager({'enabled': True})
        self.temp_dir = Path(tempfile.mkdtemp())
        self.session_manager.session_dir = self.temp_dir
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_save_session_info(self):
        """Test saving session info."""
        profile_name = "test_profile"
        additional_info = {"browser": "chrome", "version": "1.0"}
        
        self.session_manager.save_session_info(profile_name, additional_info)
        
        session_info_file = self.session_manager.get_profile_session_dir(profile_name) / "session_info.json"
        assert session_info_file.exists()
        
        with open(session_info_file, 'r') as f:
            saved_info = json.load(f)
        
        assert saved_info['profile_name'] == profile_name
        assert saved_info['browser'] == "chrome"
        assert saved_info['version'] == "1.0"
        assert 'last_used' in saved_info
        assert 'created' in saved_info
    
    def test_save_session_info_when_disabled(self):
        """Test that session info is not saved when disabled."""
        disabled_manager = SessionManager({'enabled': False})
        disabled_manager.session_dir = self.temp_dir
        
        disabled_manager.save_session_info("test_profile")
        
        session_info_file = self.temp_dir / "test_profile" / "session_info.json"
        assert not session_info_file.exists()
    
    def test_update_last_used(self):
        """Test updating last used timestamp."""
        profile_name = "update_profile"
        
        # Save initial session info
        self.session_manager.save_session_info(profile_name)
        
        session_info_file = self.session_manager.get_profile_session_dir(profile_name) / "session_info.json"
        
        # Get initial timestamp
        with open(session_info_file, 'r') as f:
            initial_info = json.load(f)
        
        initial_time = initial_info['last_used']
        
        # Update last used
        self.session_manager.update_last_used(profile_name)
        
        # Check that timestamp was updated
        with open(session_info_file, 'r') as f:
            updated_info = json.load(f)
        
        assert updated_info['last_used'] != initial_time
    
    def test_update_last_used_nonexistent_file(self):
        """Test updating last used for nonexistent session info file."""
        # Should not raise exception
        self.session_manager.update_last_used("nonexistent_profile")


class TestCookieManagement:
    """Test cookie saving and loading."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.session_manager = SessionManager({'enabled': True, 'save_cookies': True})
        self.temp_dir = Path(tempfile.mkdtemp())
        self.session_manager.session_dir = self.temp_dir
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_save_and_load_cookies(self):
        """Test saving and loading cookies."""
        profile_name = "cookie_profile"
        cookies = [
            {"name": "session_id", "value": "abc123", "domain": "example.com"},
            {"name": "user_pref", "value": "dark_mode", "domain": "example.com"}
        ]
        
        self.session_manager.save_cookies(profile_name, cookies)
        loaded_cookies = self.session_manager.load_cookies(profile_name)
        
        assert loaded_cookies == cookies
    
    def test_load_nonexistent_cookies(self):
        """Test loading cookies when file doesn't exist."""
        loaded_cookies = self.session_manager.load_cookies("nonexistent_profile")
        assert loaded_cookies == []
    
    def test_save_cookies_when_disabled(self):
        """Test that cookies are not saved when disabled."""
        disabled_manager = SessionManager({'enabled': False})
        disabled_manager.session_dir = self.temp_dir
        
        cookies = [{"name": "test", "value": "value"}]
        disabled_manager.save_cookies("test_profile", cookies)
        
        cookies_file = self.temp_dir / "test_profile" / "cookies.json"
        assert not cookies_file.exists()
    
    def test_save_cookies_feature_disabled(self):
        """Test that cookies are not saved when feature is disabled."""
        manager = SessionManager({'enabled': True, 'save_cookies': False})
        manager.session_dir = self.temp_dir
        
        cookies = [{"name": "test", "value": "value"}]
        manager.save_cookies("test_profile", cookies)
        
        cookies_file = self.temp_dir / "test_profile" / "cookies.json"
        assert not cookies_file.exists()


class TestLocalStorageManagement:
    """Test local storage saving and loading."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.session_manager = SessionManager({'enabled': True, 'save_local_storage': True})
        self.temp_dir = Path(tempfile.mkdtemp())
        self.session_manager.session_dir = self.temp_dir
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_save_and_load_local_storage(self):
        """Test saving and loading local storage."""
        profile_name = "storage_profile"
        local_storage = {
            "theme": "dark",
            "language": "en",
            "preferences": '{"notifications": true}'
        }
        
        self.session_manager.save_local_storage(profile_name, local_storage)
        loaded_storage = self.session_manager.load_local_storage(profile_name)
        
        assert loaded_storage == local_storage
    
    def test_load_nonexistent_local_storage(self):
        """Test loading local storage when file doesn't exist."""
        loaded_storage = self.session_manager.load_local_storage("nonexistent_profile")
        assert loaded_storage == {}
    
    def test_save_local_storage_when_disabled(self):
        """Test that local storage is not saved when disabled."""
        disabled_manager = SessionManager({'enabled': False})
        disabled_manager.session_dir = self.temp_dir
        
        storage = {"key": "value"}
        disabled_manager.save_local_storage("test_profile", storage)
        
        storage_file = self.temp_dir / "test_profile" / "local_storage.json"
        assert not storage_file.exists()
    
    def test_save_local_storage_feature_disabled(self):
        """Test that local storage is not saved when feature is disabled."""
        manager = SessionManager({'enabled': True, 'save_local_storage': False})
        manager.session_dir = self.temp_dir
        
        storage = {"key": "value"}
        manager.save_local_storage("test_profile", storage)
        
        storage_file = self.temp_dir / "test_profile" / "local_storage.json"
        assert not storage_file.exists()


class TestSessionCleanup:
    """Test session cleanup functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.session_manager = SessionManager({'enabled': True})
        self.temp_dir = Path(tempfile.mkdtemp())
        self.session_manager.session_dir = self.temp_dir
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_clear_session(self):
        """Test clearing a specific session."""
        profile_name = "clear_profile"
        
        # Create session data
        self.session_manager.save_session_info(profile_name)
        self.session_manager.save_cookies(profile_name, [{"name": "test"}])
        
        profile_dir = self.session_manager.get_profile_session_dir(profile_name)
        assert profile_dir.exists()
        
        # Clear session
        self.session_manager.clear_session(profile_name)
        
        assert not profile_dir.exists()
    
    def test_clear_session_when_disabled(self):
        """Test that session is not cleared when disabled."""
        disabled_manager = SessionManager({'enabled': False})
        
        # Should not raise exception
        disabled_manager.clear_session("any_profile")
    
    def test_clean_expired_sessions(self):
        """Test cleaning expired sessions."""
        # Create valid session
        valid_profile = "valid_session"
        self.session_manager.save_session_info(valid_profile)
        
        # Create expired session
        expired_profile = "expired_session"
        session_dir = self.session_manager.get_profile_session_dir(expired_profile)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        expired_time = datetime.now() - timedelta(hours=25)
        session_info = {
            'last_used': expired_time.isoformat(),
            'profile_name': expired_profile
        }
        
        session_info_file = session_dir / "session_info.json"
        with open(session_info_file, 'w') as f:
            json.dump(session_info, f)
        
        # Clean expired sessions
        self.session_manager.clean_expired_sessions()
        
        # Valid session should still exist
        assert self.session_manager.get_profile_session_dir(valid_profile).exists()
        
        # Expired session should be removed
        assert not self.session_manager.get_profile_session_dir(expired_profile).exists()
    
    def test_clean_expired_sessions_when_disabled(self):
        """Test that expired sessions are not cleaned when disabled."""
        disabled_manager = SessionManager({'enabled': False})
        
        # Should not raise exception
        disabled_manager.clean_expired_sessions()


class TestSessionManagerLogging:
    """Test logging behavior."""
    
    @patch('lamia.adapters.web.session_manager.logger')
    def test_initialization_logging(self, mock_logger):
        """Test that initialization logs appropriately."""
        SessionManager({'enabled': True})
        
        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args[0][0]
        assert "Session persistence enabled" in call_args
    
    @patch('lamia.adapters.web.session_manager.logger')
    def test_cookie_save_logging(self, mock_logger):
        """Test that cookie saving logs appropriately."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = SessionManager({'enabled': True, 'save_cookies': True})
            manager.session_dir = Path(temp_dir)
            
            cookies = [{"name": "test"}]
            manager.save_cookies("test_profile", cookies)
            
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args[0][0]
            assert "Saved 1 cookies" in call_args