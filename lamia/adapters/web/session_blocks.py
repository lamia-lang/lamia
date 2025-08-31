"""Session blocks implementation for automatic session persistence."""

import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SessionStorageType(Enum):
    """Types of session storage for different use cases."""
    LOGIN = "login"           # Authentication sessions
    CART = "cart"            # Shopping cart state  
    FORM = "form"            # Form progress/drafts
    WORKFLOW = "workflow"    # Multi-step processes
    PREFERENCES = "prefs"    # User settings
    TOKENS = "tokens"        # API keys, OAuth tokens
    CUSTOM = "custom"        # User-defined


class SessionDetection(Enum):
    """Strategies for detecting session success."""
    URL_CHANGE = "url_change"        # Redirect after success
    ELEMENT_APPEARS = "element"      # Success indicator visible
    ELEMENT_DISAPPEARS = "no_element" # Login form disappears  
    CONTENT_MATCH = "content"        # Specific text appears
    COOKIE_SET = "cookie"            # Auth cookie present
    LOCAL_STORAGE = "storage"        # localStorage key set
    MANUAL = "manual"                # User confirms success


class SessionAction:
    """Represents a recorded action within a session block."""
    
    def __init__(self, action_type: str, args: tuple, kwargs: dict, timestamp: datetime = None):
        self.action_type = action_type
        self.args = args
        self.kwargs = kwargs
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> dict:
        return {
            'action_type': self.action_type,
            'args': self.args,
            'kwargs': self.kwargs,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SessionAction':
        return cls(
            action_type=data['action_type'],
            args=tuple(data['args']),
            kwargs=data['kwargs'],
            timestamp=datetime.fromisoformat(data['timestamp'])
        )


class SessionBlockManager:
    """Manages session blocks and their persistence."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize session block manager.
        
        Args:
            config: Session persistence configuration
        """
        config = config or {}
        self.enabled = config.get('enabled', True)
        self.session_dir = Path('./.lamia_sessions')
        self.session_timeout_hours = config.get('session_timeout', 24)
        
        # Create session directory if it doesn't exist
        if self.enabled:
            self.session_dir.mkdir(exist_ok=True)
            logger.info(f"Session blocks enabled. Session dir: {self.session_dir}")
    
    def _generate_session_key(self, name: str, profile: str = "default") -> str:
        """Generate a unique session key."""
        key_string = f"{name}:{profile}"
        return hashlib.md5(key_string.encode()).hexdigest()[:16]
    
    def _get_session_file(self, name: str, profile: str = "default") -> Path:
        """Get path to session file."""
        session_key = self._generate_session_key(name, profile)
        return self.session_dir / f"{session_key}.json"
    
    def is_session_valid(self, name: str, profile: str = "default") -> bool:
        """Check if a session is valid and not expired."""
        if not self.enabled:
            return False
        
        session_file = self._get_session_file(name, profile)
        if not session_file.exists():
            return False
        
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            last_used = datetime.fromisoformat(session_data['last_used'])
            expiry_time = last_used + timedelta(hours=self.session_timeout_hours)
            
            if datetime.now() > expiry_time:
                logger.info(f"Session '{name}' (profile: {profile}) has expired")
                return False
            
            logger.info(f"Valid session found for '{name}' (profile: {profile})")
            return True
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Invalid session data for '{name}' (profile: {profile}): {e}")
            return False
    
    def save_session(self, name: str, actions: List[SessionAction], 
                    storage_type: SessionStorageType = SessionStorageType.LOGIN,
                    profile: str = "default", metadata: Dict = None):
        """Save a session with its recorded actions."""
        if not self.enabled:
            return
        
        session_file = self._get_session_file(name, profile)
        
        session_data = {
            'name': name,
            'profile': profile,
            'storage_type': storage_type.value,
            'created': datetime.now().isoformat(),
            'last_used': datetime.now().isoformat(),
            'actions': [action.to_dict() for action in actions],
            'metadata': metadata or {}
        }
        
        try:
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            logger.info(f"Saved session '{name}' (profile: {profile}) with {len(actions)} actions")
        except IOError as e:
            logger.error(f"Failed to save session '{name}' (profile: {profile}): {e}")
    
    def load_session(self, name: str, profile: str = "default") -> Optional[List[SessionAction]]:
        """Load recorded actions from a session."""
        if not self.enabled:
            return None
        
        session_file = self._get_session_file(name, profile)
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            actions = [SessionAction.from_dict(action_data) 
                      for action_data in session_data['actions']]
            
            # Update last used time
            session_data['last_used'] = datetime.now().isoformat()
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            logger.info(f"Loaded session '{name}' (profile: {profile}) with {len(actions)} actions")
            return actions
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load session '{name}' (profile: {profile}): {e}")
            return None
    
    def clear_session(self, name: str, profile: str = "default"):
        """Clear a specific session."""
        if not self.enabled:
            return
        
        session_file = self._get_session_file(name, profile)
        if session_file.exists():
            try:
                session_file.unlink()
                logger.info(f"Cleared session '{name}' (profile: {profile})")
            except OSError as e:
                logger.warning(f"Failed to clear session '{name}' (profile: {profile}): {e}")
    
    def clear_expired_sessions(self):
        """Remove all expired sessions."""
        if not self.enabled or not self.session_dir.exists():
            return
        
        for session_file in self.session_dir.glob("*.json"):
            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                
                last_used = datetime.fromisoformat(session_data['last_used'])
                expiry_time = last_used + timedelta(hours=self.session_timeout_hours)
                
                if datetime.now() > expiry_time:
                    session_file.unlink()
                    logger.info(f"Cleaned expired session: {session_file.name}")
                    
            except (json.JSONDecodeError, OSError, KeyError) as e:
                logger.warning(f"Error cleaning session {session_file.name}: {e}")


# Global session block manager instance
_session_manager = None

def get_session_manager() -> SessionBlockManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionBlockManager()
    return _session_manager


# Global recording state
_current_session_context = None
_recorded_actions = []

def get_current_session_context():
    """Get the current session context if any."""
    return _current_session_context

def is_recording():
    """Check if we're currently recording actions."""
    return _current_session_context is not None

def record_action(action_type: str, *args, **kwargs):
    """Record an action if we're in a session context."""
    global _recorded_actions
    if is_recording():
        action = SessionAction(action_type, args, kwargs)
        _recorded_actions.append(action)
        logger.debug(f"Recorded action: {action_type}")


class SessionContext:
    """Context manager for session blocks."""
    
    def __init__(self, 
                 name: str,
                 storage_type: Union[SessionStorageType, str] = SessionStorageType.LOGIN,
                 detection: Union[SessionDetection, str] = SessionDetection.ELEMENT_APPEARS,
                 success_indicators: List[str] = None,
                 failure_indicators: List[str] = None,
                 profile: str = "default",
                 timeout: float = 30.0,
                 retry_on_failure: bool = True):
        """Initialize session context.
        
        Args:
            name: Unique name for this session
            storage_type: Type of session storage
            detection: Strategy for detecting session success
            success_indicators: Selectors that indicate success
            failure_indicators: Selectors that indicate failure  
            profile: User profile name
            timeout: Timeout for session operations
            retry_on_failure: Whether to retry on failure
        """
        self.name = name
        self.storage_type = storage_type if isinstance(storage_type, SessionStorageType) else SessionStorageType(storage_type)
        self.detection = detection if isinstance(detection, SessionDetection) else SessionDetection(detection)
        self.success_indicators = success_indicators or []
        self.failure_indicators = failure_indicators or []
        self.profile = profile
        self.timeout = timeout
        self.retry_on_failure = retry_on_failure
        
        self.session_manager = get_session_manager()
        self.should_skip = False
    
    def __enter__(self):
        """Enter the session context."""
        global _current_session_context, _recorded_actions
        
        # Check if valid session exists
        if self.session_manager.is_session_valid(self.name, self.profile):
            logger.info(f"Valid session found for '{self.name}', skipping execution")
            self.should_skip = True
            return "SKIP"
        
        # Start recording
        logger.info(f"Starting session recording for '{self.name}'")
        _current_session_context = self
        _recorded_actions = []
        return "RECORD"
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the session context."""
        global _current_session_context, _recorded_actions
        
        if self.should_skip:
            return False
        
        try:
            if exc_type is None:
                # Success - save the session
                logger.info(f"Session '{self.name}' completed successfully, saving...")
                self.session_manager.save_session(
                    self.name, 
                    _recorded_actions, 
                    self.storage_type, 
                    self.profile,
                    metadata={
                        'detection': self.detection.value,
                        'success_indicators': self.success_indicators,
                        'failure_indicators': self.failure_indicators
                    }
                )
            else:
                # Failure - optionally clear session or retry
                logger.warning(f"Session '{self.name}' failed: {exc_val}")
                if not self.retry_on_failure:
                    self.session_manager.clear_session(self.name, self.profile)
        finally:
            # Clean up recording state
            _current_session_context = None
            _recorded_actions = []
        
        return False  # Don't suppress exceptions


def session(name: str, **kwargs) -> SessionContext:
    """Create a session context manager.
    
    Args:
        name: Unique name for this session
        **kwargs: Additional session configuration options
    
    Returns:
        SessionContext manager
    
    Example:
        with session("linkedin_login"):
            web.type_text("#username", "user@example.com")
            web.type_text("#password", "password123")
            web.click("#login-button")
    """
    return SessionContext(name, **kwargs)
