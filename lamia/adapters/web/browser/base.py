from abc import ABC, abstractmethod
from typing import Any, Optional
from lamia.internal_types import BrowserActionParams


class BaseBrowserAdapter(ABC):
    """Abstract base class for browser automation adapters (Selenium, Playwright, etc.)."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the browser adapter."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the browser adapter and cleanup resources."""
        pass
    
    @abstractmethod
    async def navigate(self, params: BrowserActionParams) -> None:
        """Navigate to a URL."""
        pass
    
    @abstractmethod
    async def click(self, params: BrowserActionParams) -> None:
        """Click an element."""
        pass
    
    @abstractmethod
    async def type_text(self, params: BrowserActionParams) -> None:
        """Type text into an element."""
        pass
    
    @abstractmethod
    async def wait_for_element(self, params: BrowserActionParams) -> None:
        """Wait for an element to meet a condition."""
        pass
    
    @abstractmethod
    async def get_text(self, params: BrowserActionParams) -> str:
        """Get text content of an element."""
        pass
    
    @abstractmethod
    async def get_attribute(self, params: BrowserActionParams) -> str:
        """Get attribute value of an element."""
        pass
    
    @abstractmethod
    async def is_visible(self, params: BrowserActionParams) -> bool:
        """Check if an element is visible."""
        pass
    
    @abstractmethod
    async def is_enabled(self, params: BrowserActionParams) -> bool:
        """Check if an element is enabled."""
        pass
    
    @abstractmethod
    async def hover(self, params: BrowserActionParams) -> None:
        """Hover over an element."""
        pass
    
    @abstractmethod
    async def scroll(self, params: BrowserActionParams) -> None:
        """Scroll to an element or by amount."""
        pass
    
    @abstractmethod
    async def select_option(self, params: BrowserActionParams) -> None:
        """Select an option from a dropdown."""
        pass
    
    @abstractmethod
    async def submit_form(self, params: BrowserActionParams) -> None:
        """Submit a form."""
        pass
    
    @abstractmethod
    async def take_screenshot(self, params: BrowserActionParams) -> str:
        """Take a screenshot and return file path."""
        pass


    @abstractmethod
    async def get_current_url(self) -> str:
        """Get the current page URL."""
        pass

    @abstractmethod
    async def get_page_source(self) -> str:
        """Get the current page HTML source."""
        pass

    # --- Session/profile contract ---
    @abstractmethod
    def set_profile(self, profile_name: Optional[str]) -> None:
        """Set active session profile name for persistence operations."""
        pass

    @abstractmethod
    async def load_session_state(self) -> None:
        """Load session state (cookies, localStorage) for current profile."""
        pass

    @abstractmethod
    async def save_session_state(self) -> None:
        """Save session state (cookies, localStorage) for current profile."""
        pass