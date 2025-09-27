"""Clean session context manager for browser profile management."""

import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)


class SessionSkipException(Exception):
    """Exception raised when session should be skipped due to valid existing state."""
    pass


class SessionContext:
    """Simple session context manager with profile name only."""
    
    def __init__(self, name: str, web_manager=None, probe_url: Optional[str] = None):
        """Initialize session context.
        
        Args:
            name: Browser profile name (e.g., "linkedin_login") 
            web_manager: WebManager instance for validation
            probe_url: Optional URL to probe for logged-in state (e.g., homepage)
        """
        self.name: str = name  # This IS the browser profile name
        self.web_manager = web_manager
        self.probe_url: Optional[str] = probe_url
        self.should_skip: bool = False
    
    def __enter__(self):
        """Enter session context - validate existing session and load cookies if valid."""
        logger.info(f"Starting session context for profile '{self.name}'")

        # Check if we have valid session cookies for this profile
        if self.web_manager:
            try:
                # Use existing BrowserManager validation logic
                browser_manager = self.web_manager.browser_manager
                # Tell browser manager which profile is active now
                try:
                    browser_manager.set_active_profile(self.name)
                except Exception:
                    pass

                # Validate session using optional probe URL (e.g., linkedin.com)
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    is_valid = loop.run_until_complete(
                        browser_manager.validate_session_cookies(self.name, self.probe_url)
                    )
                    loop.close()

                    if is_valid:
                        logger.info(f"Session '{self.name}' valid via probe, skipping execution")
                        self.should_skip = True
                        raise SessionSkipException(f"Session '{self.name}' already valid")
                except Exception as e:
                    logger.debug(f"Session probe validation failed for '{self.name}': {e}")
                    # Continue with execution if validation fails

            except Exception as e:
                logger.debug(f"Cookie validation failed for '{self.name}': {e}")
                # Continue with execution if validation fails

        logger.info(f"Starting session execution for profile '{self.name}'")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit session context - save session if successful."""
        if self.should_skip:
            logger.debug(f"Session '{self.name}' was skipped, no cleanup needed")
        elif exc_type is None and self.web_manager:
            # Session completed successfully, save cookies
            logger.info(f"Session '{self.name}' completed successfully, saving cookies")
            try:
                browser_manager = self.web_manager.browser_manager
                # Save cookies in new event loop
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(browser_manager.save_session_cookies(self.name))
                    loop.close()
                except Exception as e:
                    logger.warning(f"Failed to save cookies for profile '{self.name}': {e}")
                try:
                    browser_manager.set_active_profile(None)
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Failed to save cookies for profile '{self.name}': {e}")
        else:
            logger.warning(f"Session '{self.name}' failed: {exc_val}")

        return False  # Don't suppress exceptions


def create_session_factory(web_manager=None):
    """Create session factory with web_manager injection.
    
    Args:
        web_manager: WebManager instance for session validation
        
    Returns:
        Session factory function
    """
    def session(name: str, probe_url: Optional[str] = None):
        """Create session context with profile name and optional probe URL.
        
        Args:
            name: Browser profile name (e.g., "linkedin_login")
            probe_url: Optional URL to probe for logged-in state
            
        Returns:
            SessionContext manager
        """
        return SessionContext(name=name, web_manager=web_manager, probe_url=probe_url)
    
    return session
