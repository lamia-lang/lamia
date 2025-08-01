"""Retry wrapper for browser adapters."""

import asyncio
import logging
from typing import Any
from ..retry_handler import RetryHandler
from ...web.browser.base import BaseBrowserAdapter
from lamia.types import ExternalOperationRetryConfig, BrowserActionParams

logger = logging.getLogger(__name__)


class RetryingBrowserAdapter(BaseBrowserAdapter):
    """Browser adapter with retry capabilities."""
    
    def __init__(
        self,
        adapter: BaseBrowserAdapter,
        retry_config: ExternalOperationRetryConfig,
        collect_stats: bool = True
    ):
        self.adapter = adapter
        self.retry_handler = RetryHandler(adapter, retry_config, collect_stats=collect_stats)
    
    async def initialize(self) -> None:
        """Initialize the underlying adapter with retry."""
        await self.retry_handler.execute(
            self.adapter.initialize,
            operation_name="browser_initialize"
        )
    
    async def close(self) -> None:
        """Close the underlying adapter with retry."""
        await self.retry_handler.execute(
            self.adapter.close,
            operation_name="browser_close"
        )
    
    async def navigate(self, params: BrowserActionParams) -> None:
        """Navigate with retry."""
        await self.retry_handler.execute(
            lambda: self.adapter.navigate(params),
            operation_name="browser_navigate"
        )
    
    async def click(self, params: BrowserActionParams) -> None:
        """Click with retry."""
        await self.retry_handler.execute(
            lambda: self.adapter.click(params),
            operation_name="browser_click"
        )
    
    async def type_text(self, params: BrowserActionParams) -> None:
        """Type text with retry."""
        await self.retry_handler.execute(
            lambda: self.adapter.type_text(params),
            operation_name="browser_type"
        )
    
    async def wait_for_element(self, params: BrowserActionParams) -> None:
        """Wait for element with retry."""
        await self.retry_handler.execute(
            lambda: self.adapter.wait_for_element(params),
            operation_name="browser_wait"
        )
    
    async def get_text(self, params: BrowserActionParams) -> str:
        """Get text with retry."""
        return await self.retry_handler.execute(
            lambda: self.adapter.get_text(params),
            operation_name="browser_get_text"
        )
    
    async def get_attribute(self, params: BrowserActionParams) -> str:
        """Get attribute with retry."""
        return await self.retry_handler.execute(
            lambda: self.adapter.get_attribute(params),
            operation_name="browser_get_attribute"
        )
    
    async def is_visible(self, params: BrowserActionParams) -> bool:
        """Check visibility with retry."""
        return await self.retry_handler.execute(
            lambda: self.adapter.is_visible(params),
            operation_name="browser_is_visible"
        )
    
    async def is_enabled(self, params: BrowserActionParams) -> bool:
        """Check if enabled with retry."""
        return await self.retry_handler.execute(
            lambda: self.adapter.is_enabled(params),
            operation_name="browser_is_enabled"
        )
    
    async def hover(self, params: BrowserActionParams) -> None:
        """Hover with retry."""
        await self.retry_handler.execute(
            lambda: self.adapter.hover(params),
            operation_name="browser_hover"
        )
    
    async def scroll(self, params: BrowserActionParams) -> None:
        """Scroll with retry."""
        await self.retry_handler.execute(
            lambda: self.adapter.scroll(params),
            operation_name="browser_scroll"
        )
    
    async def select_option(self, params: BrowserActionParams) -> None:
        """Select option with retry."""
        await self.retry_handler.execute(
            lambda: self.adapter.select_option(params),
            operation_name="browser_select"
        )
    
    async def submit_form(self, params: BrowserActionParams) -> None:
        """Submit form with retry."""
        await self.retry_handler.execute(
            lambda: self.adapter.submit_form(params),
            operation_name="browser_submit"
        )
    
    async def take_screenshot(self, params: BrowserActionParams) -> str:
        """Take screenshot with retry."""
        return await self.retry_handler.execute(
            lambda: self.adapter.take_screenshot(params),
            operation_name="browser_screenshot"
        )