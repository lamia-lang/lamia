"""Session persistence manager for browser automation."""

import json
import os
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages browser session persistence across automation runs."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize session manager with configuration.
        
        Args:
            config: Session persistence configuration from web_config
        """
        self.enabled = config.get('enabled', False)
        # Use script's current directory for session storage (like .lamia_cache)
        self.session_dir = Path('./.lamia_sessions')
        self.session_timeout_hours = config.get('session_timeout', 24)
        self.save_cookies = config.get('save_cookies', True)
        self.save_local_storage = config.get('save_local_storage', True)
        
        # Create session directory if it doesn't exist
        if self.enabled:
            self.session_dir.mkdir(exist_ok=True)
            logger.info(f"Session persistence enabled. Session dir: {self.session_dir}")
    
    def _generate_session_key(self, username: str, domain: str) -> str:
        """Generate a unique session key based on username and domain."""
        # Create a hash of username + domain for privacy and uniqueness
        key_string = f"{username.lower()}@{domain.lower()}"
        return hashlib.md5(key_string.encode()).hexdigest()[:12]
    
    def get_profile_session_dir(self, profile_name: str) -> Path:
        """Get session directory for a specific profile."""
        return self.session_dir / profile_name
    
    def is_session_valid(self, profile_name: str) -> bool:
        """Check if a stored session is still valid."""
        if not self.enabled:
            return False
            
        session_dir = self.get_profile_session_dir(profile_name)
        session_info_file = session_dir / "session_info.json"
        
        if not session_info_file.exists():
            return False
        
        try:
            with open(session_info_file, 'r') as f:
                session_info = json.load(f)
            
            last_used = datetime.fromisoformat(session_info['last_used'])
            expiry_time = last_used + timedelta(hours=self.session_timeout_hours)
            
            if datetime.now() > expiry_time:
                logger.info(f"Session for profile '{profile_name}' has expired")
                return False
            
            logger.info(f"Valid session found for profile '{profile_name}'")
            return True
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Invalid session info for profile '{profile_name}': {e}")
            return False
    
    def save_session_info(self, profile_name: str, additional_info: Optional[Dict] = None):
        """Save session metadata."""
        if not self.enabled:
            return
            
        session_dir = self.get_profile_session_dir(profile_name)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        session_info = {
            'last_used': datetime.now().isoformat(),
            'profile_name': profile_name,
            'created': datetime.now().isoformat()
        }
        
        if additional_info:
            session_info.update(additional_info)
        
        session_info_file = session_dir / "session_info.json"
        with open(session_info_file, 'w') as f:
            json.dump(session_info, f, indent=2)
        
        logger.info(f"Saved session info for profile '{profile_name}'")
    
    def update_last_used(self, profile_name: str):
        """Update the last used timestamp for a session."""
        if not self.enabled:
            return
            
        session_dir = self.get_profile_session_dir(profile_name)
        session_info_file = session_dir / "session_info.json"
        
        if session_info_file.exists():
            try:
                with open(session_info_file, 'r') as f:
                    session_info = json.load(f)
                
                session_info['last_used'] = datetime.now().isoformat()
                
                with open(session_info_file, 'w') as f:
                    json.dump(session_info, f, indent=2)
                    
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to update last_used for profile '{profile_name}': {e}")
    
    def clean_expired_sessions(self):
        """Remove expired session directories."""
        if not self.enabled or not self.session_dir.exists():
            return
        
        for profile_dir in self.session_dir.iterdir():
            if profile_dir.is_dir():
                profile_name = profile_dir.name
                if not self.is_session_valid(profile_name):
                    try:
                        import shutil
                        shutil.rmtree(profile_dir)
                        logger.info(f"Cleaned expired session for profile '{profile_name}'")
                    except OSError as e:
                        logger.warning(f"Failed to clean session for profile '{profile_name}': {e}")
    
    def get_cookies_file(self, profile_name: str) -> Path:
        """Get path to cookies file for a profile."""
        return self.get_profile_session_dir(profile_name) / "cookies.json"
    
    def get_local_storage_file(self, profile_name: str) -> Path:
        """Get path to local storage file for a profile."""
        return self.get_profile_session_dir(profile_name) / "local_storage.json"
    
    def save_cookies(self, profile_name: str, cookies: List[Dict]):
        """Save cookies to file."""
        if not self.enabled or not self.save_cookies:
            return
        
        cookies_file = self.get_cookies_file(profile_name)
        cookies_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(cookies_file, 'w') as f:
                json.dump(cookies, f, indent=2)
            logger.info(f"Saved {len(cookies)} cookies for profile '{profile_name}'")
        except IOError as e:
            logger.warning(f"Failed to save cookies for profile '{profile_name}': {e}")
    
    def load_cookies(self, profile_name: str) -> List[Dict]:
        """Load cookies from file."""
        if not self.enabled or not self.save_cookies:
            return []
        
        cookies_file = self.get_cookies_file(profile_name)
        if not cookies_file.exists():
            return []
        
        try:
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)
            logger.info(f"Loaded {len(cookies)} cookies for profile '{profile_name}'")
            return cookies
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cookies for profile '{profile_name}': {e}")
            return []
    
    def save_local_storage(self, profile_name: str, local_storage: Dict):
        """Save local storage to file."""
        if not self.enabled or not self.save_local_storage:
            return
        
        storage_file = self.get_local_storage_file(profile_name)
        storage_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(storage_file, 'w') as f:
                json.dump(local_storage, f, indent=2)
            logger.info(f"Saved local storage for profile '{profile_name}'")
        except IOError as e:
            logger.warning(f"Failed to save local storage for profile '{profile_name}': {e}")
    
    def load_local_storage(self, profile_name: str) -> Dict:
        """Load local storage from file."""
        if not self.enabled or not self.save_local_storage:
            return {}
        
        storage_file = self.get_local_storage_file(profile_name)
        if not storage_file.exists():
            return {}
        
        try:
            with open(storage_file, 'r') as f:
                local_storage = json.load(f)
            logger.info(f"Loaded local storage for profile '{profile_name}'")
            return local_storage
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load local storage for profile '{profile_name}': {e}")
            return {}
    
    def get_profile_config(self, profile_name: str) -> Optional[Dict]:
        """Get configuration for a specific user profile."""
        return self.user_profiles.get(profile_name)
    
    def clear_session(self, profile_name: str):
        """Clear all session data for a profile."""
        if not self.enabled:
            return
        
        session_dir = self.get_profile_session_dir(profile_name)
        if session_dir.exists():
            try:
                import shutil
                shutil.rmtree(session_dir)
                logger.info(f"Cleared session for profile '{profile_name}'")
            except OSError as e:
                logger.warning(f"Failed to clear session for profile '{profile_name}': {e}")
