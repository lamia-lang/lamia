"""Retry wrapper for browser adapters."""

import logging
from typing import Any, Optional, List
from ..retry_handler import RetryHandler
from ...web.browser.base import BaseBrowserAdapter
from lamia.types import ExternalOperationRetryConfig
from lamia.internal_types import BrowserActionParams
from lamia.types import InputType

logger = logging.getLogger(__name__)


class RetryingBrowserAdapter(BaseBrowserAdapter):
    """Browser adapter with retry capabilities."""
    
    def __init__(
        self,
        adapter: BaseBrowserAdapter,
        retry_config: ExternalOperationRetryConfig,
        collect_stats: bool = True,
    ):
        self.adapter = adapter
        self.retry_handler = RetryHandler(adapter, retry_config, collect_stats=collect_stats)
    
    async def initialize(self) -> None:
        await self.retry_handler.execute(self.adapter.initialize)
    
    async def close(self) -> None:
        await self.retry_handler.execute(self.adapter.close)
    
    async def navigate(self, params: BrowserActionParams) -> None:
        await self.retry_handler.execute(self.adapter.navigate, params)
    
    async def click(self, params: BrowserActionParams) -> None:
        await self.retry_handler.execute(self.adapter.click, params)
    
    async def type_text(self, params: BrowserActionParams) -> None:
        await self.retry_handler.execute(self.adapter.type_text, params)
    
    async def wait_for_element(self, params: BrowserActionParams) -> None:
        await self.retry_handler.execute(self.adapter.wait_for_element, params)
    
    async def get_text(self, params: BrowserActionParams) -> str:
        return await self.retry_handler.execute(self.adapter.get_text, params)
    
    async def get_attribute(self, params: BrowserActionParams) -> str:
        return await self.retry_handler.execute(self.adapter.get_attribute, params)
    
    async def is_visible(self, params: BrowserActionParams) -> bool:
        return await self.retry_handler.execute(self.adapter.is_visible, params)
    
    async def is_enabled(self, params: BrowserActionParams) -> bool:
        return await self.retry_handler.execute(self.adapter.is_enabled, params)
    
    async def hover(self, params: BrowserActionParams) -> None:
        await self.retry_handler.execute(self.adapter.hover, params)
    
    async def scroll(self, params: BrowserActionParams) -> None:
        await self.retry_handler.execute(self.adapter.scroll, params)
    
    async def select_option(self, params: BrowserActionParams) -> None:
        await self.retry_handler.execute(self.adapter.select_option, params)
    
    async def submit_form(self, params: BrowserActionParams) -> None:
        await self.retry_handler.execute(self.adapter.submit_form, params)
    
    async def take_screenshot(self, params: BrowserActionParams) -> str:
        return await self.retry_handler.execute(self.adapter.take_screenshot, params)
    
    async def get_current_url(self) -> str:
        return await self.retry_handler.execute(self.adapter.get_current_url)
    
    async def get_page_source(self) -> str:
        return await self.retry_handler.execute(self.adapter.get_page_source)
    
    async def upload_file(self, params: BrowserActionParams) -> None:
        await self.retry_handler.execute(self.adapter.upload_file, params)
    
    def set_profile(self, profile_name: Optional[str]) -> None:
        self.adapter.set_profile(profile_name)

    async def load_session_state(self) -> None:
        await self.retry_handler.execute(self.adapter.load_session_state)

    async def save_session_state(self) -> None:
        await self.retry_handler.execute(self.adapter.save_session_state)

    async def get_elements(self, params: BrowserActionParams) -> List[Any]:
        return await self.retry_handler.execute(self.adapter.get_elements, params)

    async def execute_script(self, script: str, *args: Any) -> Any:
        return await self.retry_handler.execute(self.adapter.execute_script, script, *args)
