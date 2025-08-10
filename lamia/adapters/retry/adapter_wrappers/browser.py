"""Retry wrapper for browser adapters."""

import asyncio
import logging
from typing import Any
from ..retry_handler import RetryHandler
from ...web.browser.base import BaseBrowserAdapter
from lamia.errors import ExternalOperationTransientError, ExternalOperationPermanentError
from lamia.types import ExternalOperationRetryConfig, BrowserActionParams

logger = logging.getLogger(__name__)


class RetryingBrowserAdapter(BaseBrowserAdapter):
    """Browser adapter with retry capabilities and universal selector chain logic."""
    
    def __init__(
        self,
        adapter: BaseBrowserAdapter,
        retry_config: ExternalOperationRetryConfig,
        collect_stats: bool = True
    ):
        self.adapter = adapter
        self.retry_handler = RetryHandler(adapter, retry_config, collect_stats=collect_stats)
    
    async def _execute_with_selector_chain(self, method_name: str, params: BrowserActionParams):
        """Execute adapter method with AI-powered selector resolution and fallback logic."""
        selectors = [params.selector] + (params.fallback_selectors or [])
        
        logger.info(f"Starting selector chain with {len(selectors)} selectors for {method_name}")
        
        for i, selector in enumerate(selectors):
            try:
                logger.info(f"Processing selector {i+1}/{len(selectors)}: '{selector}'")
                
                # Create params with current selector (AI resolution happens at BrowserManager level)
                single_selector_params = BrowserActionParams(
                    selector=selector,
                    selector_type=params.selector_type,
                    value=params.value,
                    timeout=params.timeout,
                    wait_condition=params.wait_condition,
                    fallback_selectors=None  # No fallbacks for individual attempts
                )
                
                # Execute with retry logic for transient errors
                adapter_method = getattr(self.adapter, method_name)
                result = await self.retry_handler.execute(
                    lambda: adapter_method(single_selector_params)
                )
                
                logger.info(f"Selector '{selector}' succeeded for {method_name}")
                return result
                
            except ExternalOperationTransientError as e:
                logger.warning(f"Selector '{selector}' failed for {method_name} after retries: {str(e)}")
                if i < len(selectors) - 1:
                    logger.info(f"Continuing to next selector")
                    continue
                else:
                    # All selectors failed
                    error_msg = f"All selectors failed for {method_name}. Tried: {', '.join(selectors)}"
                    logger.error(error_msg)
                    raise ExternalOperationTransientError(error_msg, retry_history=e.retry_history, original_error=e.original_error)
            
            except ExternalOperationPermanentError:
                # Permanent errors should not try other selectors, re-raise immediately
                raise
    
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
        await self._execute_with_selector_chain('click', params)
    
    async def type_text(self, params: BrowserActionParams) -> None:
        """Type text with retry and selector chain fallback."""
        await self._execute_with_selector_chain('type_text', params)
    
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