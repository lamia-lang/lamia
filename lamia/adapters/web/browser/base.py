from abc import ABC, abstractmethod
from typing import Optional
from lamia.internal_types import BrowserActionParams


DOM_STABLE_MUTATION_QUIET_MS = 500.0

DOM_STABILITY_TRACKER_BOOTSTRAP = r"""
(() => {
  if (window.__lamiaDomTracker) return;

  const tracker = {
    pendingFetches: 0,
    pendingXhrs: 0,
    lastMutationTs: performance.now(),
  };

  const updateMutationTs = () => {
    tracker.lastMutationTs = performance.now();
  };

  const observer = new MutationObserver(updateMutationTs);
  observer.observe(document, { subtree: true, childList: true, attributes: true, characterData: true });

  if (window.fetch) {
    const originalFetch = window.fetch;
    window.fetch = (...args) => {
      tracker.pendingFetches += 1;
      return originalFetch(...args).finally(() => {
        tracker.pendingFetches = Math.max(0, tracker.pendingFetches - 1);
      });
    };
  }

  const OriginalXHR = window.XMLHttpRequest;
  if (OriginalXHR) {
    const PatchedXHR = function (...args) {
      const xhr = new OriginalXHR(...args);
      xhr.addEventListener('loadstart', () => {
        tracker.pendingXhrs += 1;
      });
      const settle = () => {
        tracker.pendingXhrs = Math.max(0, tracker.pendingXhrs - 1);
      };
      xhr.addEventListener('loadend', settle);
      xhr.addEventListener('error', settle);
      xhr.addEventListener('abort', settle);
      return xhr;
    };
    window.XMLHttpRequest = PatchedXHR;
  }

  window.__lamiaDomTracker = tracker;
})();
"""

DOM_STABILITY_CHECK_SCRIPT = r"""
(() => {
  const tracker = window.__lamiaDomTracker;
  const pendingFetches = tracker ? tracker.pendingFetches : 0;
  const pendingXhrs = tracker ? tracker.pendingXhrs : 0;
  const timeSinceMutation = tracker ? performance.now() - tracker.lastMutationTs : Infinity;

  return {
    readyStateComplete: document.readyState === 'complete',
    readyState: document.readyState,
    pendingFetches,
    pendingXhrs,
    timeSinceMutation,
  };
})();
"""

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