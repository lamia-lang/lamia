"""Retry wrapper for browser adapters."""

import logging
from typing import Any, Optional
from ..retry_handler import RetryHandler
from ...web.browser.base import BaseBrowserAdapter
from lamia.types import ExternalOperationRetryConfig, BrowserActionParams

logger = logging.getLogger(__name__)


class RetryingBrowserAdapter(BaseBrowserAdapter):
    """Browser adapter with retry capabilities and AI-powered selector suggestions."""
    
    def __init__(
        self,
        adapter: BaseBrowserAdapter,
        retry_config: ExternalOperationRetryConfig,
        collect_stats: bool = True,
    ):
        self.adapter = adapter
        self.retry_handler = RetryHandler(adapter, retry_config, collect_stats=collect_stats)
    
    async def initialize(self) -> None:
        """Initialize the underlying adapter with retry."""
        await self.retry_handler.execute(
            self.adapter.initialize
        )
    
    async def close(self) -> None:
        """Close the underlying adapter with retry."""
        await self.retry_handler.execute(
            self.adapter.close
        )
    
    async def navigate(self, params: BrowserActionParams) -> None:
        """Navigate with retry."""
        await self.retry_handler.execute(
            lambda: self.adapter.navigate(params)
        )
    
    async def click(self, params: BrowserActionParams) -> None:
        """Click with retry and selector chain fallback."""
        await self.retry_handler.execute(
            lambda: self.adapter.click(params)
        )
    
    async def type_text(self, params: BrowserActionParams) -> None:
        """Type text with retry and selector chain fallback."""
        await self.retry_handler.execute(
            lambda: self.adapter.type_text(params)
        )
    
    async def wait_for_element(self, params: BrowserActionParams) -> None:
        """Wait for element with retry."""
        await self.retry_handler.execute(
            lambda: self.adapter.wait_for_element(params),
        )
    
    async def get_text(self, params: BrowserActionParams) -> str:
        """Get text with retry."""
        return await self.retry_handler.execute(
            lambda: self.adapter.get_text(params),
        )
    
    async def get_attribute(self, params: BrowserActionParams) -> str:
        """Get attribute with retry."""
        return await self.retry_handler.execute(
            lambda: self.adapter.get_attribute(params),
        )
    
    async def is_visible(self, params: BrowserActionParams) -> bool:
        """Check visibility with retry."""
        return await self.retry_handler.execute(
            lambda: self.adapter.is_visible(params),
        )
    
    async def is_enabled(self, params: BrowserActionParams) -> bool:
        """Check if enabled with retry."""
        return await self.retry_handler.execute(
            lambda: self.adapter.is_enabled(params),
        )
    
    async def hover(self, params: BrowserActionParams) -> None:
        """Hover with retry."""
        await self.retry_handler.execute(
            lambda: self.adapter.hover(params)
        )
    
    async def scroll(self, params: BrowserActionParams) -> None:
        """Scroll with retry."""
        await self.retry_handler.execute(
            lambda: self.adapter.scroll(params)
        )
    
    async def select_option(self, params: BrowserActionParams) -> None:
        """Select option with retry."""
        await self.retry_handler.execute(
            lambda: self.adapter.select_option(params)
        )
    
    async def submit_form(self, params: BrowserActionParams) -> None:
        """Submit form with retry."""
        await self.retry_handler.execute(
            lambda: self.adapter.submit_form(params)
        )
    
    async def take_screenshot(self, params: BrowserActionParams) -> str:
        """Take screenshot with retry."""
        return await self.retry_handler.execute(
            lambda: self.adapter.take_screenshot(params)
        )
    
    async def get_page_source(self) -> str:
        """Get page source with retry."""
        return await self.retry_handler.execute(
            lambda: self.adapter.get_page_source()
        )
    
    # --- Session/profile contract proxies ---
    def set_profile(self, profile_name: Optional[str]) -> None:
        # Synchronous operation, just forward
        self.adapter.set_profile(profile_name)

    async def load_session_state(self) -> None:
        await self.retry_handler.execute(
            self.adapter.load_session_state
        )

    async def save_session_state(self) -> None:
        await self.retry_handler.execute(
            self.adapter.save_session_state
        )
