"""Retry wrapper for browser adapters."""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Callable, Awaitable
from ..retry_handler import RetryHandler
from ...web.browser.base import BaseBrowserAdapter
from lamia.errors import ExternalOperationTransientError, ExternalOperationPermanentError
from lamia.types import ExternalOperationRetryConfig, BrowserActionParams

logger = logging.getLogger(__name__)


class RetryingBrowserAdapter(BaseBrowserAdapter):
    """Browser adapter with retry capabilities and AI-powered selector suggestions."""
    
    def __init__(
        self,
        adapter: BaseBrowserAdapter,
        retry_config: ExternalOperationRetryConfig,
        collect_stats: bool = True,
        suggestion_service: Optional[Any] = None
    ):
        self.adapter = adapter
        self.retry_handler = RetryHandler(adapter, retry_config, collect_stats=collect_stats)
        self.suggestion_service = suggestion_service
    
    async def _execute_with_selector_chain(self, method_name: str, params: BrowserActionParams):
        """Execute adapter method with AI-powered selector resolution and fallback logic."""
        selectors = [params.selector] + (params.fallback_selectors or [])
        
        logger.info(f"Starting selector chain with {len(selectors)} selectors for {method_name}")
        
        found_working_selector = None
        last_error = None
        
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
                last_error = e
                logger.warning(f"Selector '{selector}' failed for {method_name} after retries: {str(e)}")
                if i < len(selectors) - 1:
                    logger.info(f"Continuing to next selector")
                    continue
                else:
                    # All selectors failed - try to get AI suggestions
                    await self._handle_all_selectors_failed(
                        method_name=method_name,
                        selectors=selectors,
                        last_error=e
                    )
            
            except ExternalOperationPermanentError:
                # Permanent errors should not try other selectors, re-raise immediately
                raise
    
    async def _handle_all_selectors_failed(
        self,
        method_name: str,
        selectors: list,
        last_error: ExternalOperationTransientError
    ):
        """Handle case when all selectors failed by saving debug files and optionally calling AI.
        
        Args:
            method_name: Name of the browser method that failed
            selectors: List of all selectors that were tried
            last_error: The last error that occurred
        """
        # Always save debug files for manual analysis
        html_file, prompt_file, page_html = await self._save_debug_files(
            selectors[0], 
            method_name
        )
        
        # Build base error message
        error_lines = [
            f"\n❌ Element not found after all retries",
            f"Operation: {method_name}",
            f"Tried selectors: {', '.join(selectors)}",
            f"",
            f"📁 Debug files saved:",
            f"   HTML: {html_file}",
            f"   Prompt: {prompt_file}",
            f""
        ]
        
        # Check if auto-suggestions are enabled
        auto_suggest = self._get_auto_suggest_flag()
        
        if auto_suggest and self.suggestion_service:
            # Auto-execute AI suggestions
            try:
                logger.info("Auto-suggestions enabled, calling AI...")
                suggestions = await self.suggestion_service.suggest_alternative_selectors(
                    failed_selector=selectors[0],
                    operation_type=method_name,
                    max_suggestions=3
                )
                
                if suggestions:
                    error_lines.extend([
                        f"🤖 AI-Powered Suggestions (auto-generated):",
                        f""
                    ])
                    for i, (description, selector) in enumerate(suggestions, 1):
                        error_lines.append(f"  {i}. {description}")
                        error_lines.append(f"     Selector: {selector}")
                        error_lines.append(f"")
                    error_lines.extend([
                        f"💡 Try replacing your selector with one of the suggestions above.",
                        f""
                    ])
                else:
                    error_lines.extend([
                        f"⚠️  AI could not generate suggestions. Review the debug files manually.",
                        f""
                    ])
                    
            except Exception as e:
                logger.warning(f"Auto-suggestion failed: {e}")
                error_lines.extend([
                    f"⚠️  AI suggestions failed: {str(e)}",
                    f"   Review the debug files manually.",
                    f""
                ])
        else:
            # Show manual instructions
            error_lines.extend([
                f"💡 To get AI-powered selector suggestions:",
                f"",
                f"   Option 1 - Manual (use any LLM):",
                f"      1. Open: {html_file}",
                f"      2. Copy the HTML content",
                f"      3. Open: {prompt_file}",
                f"      4. Paste both into ChatGPT, Claude, or your preferred LLM",
                f"      5. Get alternative selector suggestions",
                f"",
                f"   Option 2 - Automatic starting from the next run (uses your model_chain):",
                f"      Add to config.yaml:",
                f"      web_config:",
                f"        auto_suggest_selectors: true",
                f""
            ])
        
        error_msg = "\n".join(error_lines)
        logger.error(error_msg)
        raise ExternalOperationTransientError(
            error_msg,
            retry_history=last_error.retry_history,
            original_error=last_error.original_error
        )
    
    async def _save_debug_files(
        self,
        failed_selector: str,
        operation_type: str
    ) -> tuple:
        """Save debug files for manual AI analysis.
        
        Returns:
            Tuple of (html_file_path, prompt_file_path, page_html)
        """
        # Create debug directory
        debug_dir = Path('.lamia/selector_failures')
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        html_file = debug_dir / f'failure_{timestamp}.html'
        prompt_file = debug_dir / f'failure_{timestamp}_prompt.txt'
        
        # Get page HTML
        page_html = None
        try:
            page_html = await self.adapter.get_page_source()
            html_file.write_text(page_html, encoding='utf-8')
            logger.debug(f"Saved page HTML to: {html_file}")
        except Exception as e:
            logger.warning(f"Could not save page HTML: {e}")
            html_file.write_text("<html>Error: Could not capture page source</html>", encoding='utf-8')
            page_html = "<html unavailable>"
        
        # Generate and save prompt
        prompt = self._generate_suggestion_prompt(
            failed_selector=failed_selector,
            operation_type=operation_type
        )
        prompt_file.write_text(prompt, encoding='utf-8')
        logger.debug(f"Saved suggestion prompt to: {prompt_file}")
        
        return str(html_file), str(prompt_file), page_html
    
    def _generate_suggestion_prompt(
        self,
        failed_selector: str,
        operation_type: str
    ) -> str:
        """Generate prompt for AI suggestions (saved to file for manual use).
        
        Args:
            failed_selector: The selector that failed
            operation_type: Type of browser operation (click, type, etc.)
            
        Returns:
            Prompt text ready to use with any LLM
        """
        operation_desc = {
            'click': 'Finding a clickable element (button, link, etc.)',
            'type_text': 'Finding an input field to type text into',
            'select': 'Finding a dropdown/select element',
            'hover': 'Finding an element to hover over',
            'wait_for': 'Finding an element that should become visible',
            'get_text': 'Finding an element to extract text from',
        }.get(operation_type, f'Finding an element for {operation_type}')
        
        return f"""The following CSS selector FAILED to find any elements on the page:

FAILED SELECTOR: {failed_selector}

OPERATION: {operation_desc}

PAGE HTML:
(Paste the HTML from the accompanying .html file here)

========================================

Your task is to analyze the HTML and suggest up to 3 alternative CSS selectors that might work.

Look for:
1. Elements with similar attributes, classes, or IDs
2. Elements that match the likely intent of the failed selector
3. Elements appropriate for the operation type ({operation_type})
4. Common selector issues (typos, outdated classes, changed DOM structure)

Return your suggestions in this EXACT format:

SUGGESTION 1: "Description of what this targets" -> css_selector_here
SUGGESTION 2: "Description of what this targets" -> css_selector_here
SUGGESTION 3: "Description of what this targets" -> css_selector_here

Example:
SUGGESTION 1: "Primary login button" -> button.btn-primary[type="submit"]
SUGGESTION 2: "Login button by aria-label" -> button[aria-label="Log in"]
SUGGESTION 3: "First submit button in form" -> form button[type="submit"]:first-child

Please provide your suggestions now:
"""
    
    def _get_auto_suggest_flag(self) -> bool:
        """Check if auto-suggest selectors is enabled in config.
        
        Returns:
            True if auto_suggest_selectors is explicitly set to true, False otherwise
        """
        # Check if suggestion_service was provided (indicates flag is true)
        # This is the most reliable check since BrowserManager only creates
        # the service when auto_suggest_selectors: true
        return self.suggestion_service is not None
    
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