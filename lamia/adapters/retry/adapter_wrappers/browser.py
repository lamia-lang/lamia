"""Retry wrapper for browser adapters."""

import asyncio
import logging
import os
import re
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
            f"   Full HTML: {html_file}",
            f"   AI-ready skeleton: {html_file.replace('.html', '_skeleton.html')}",
            f"   Prompt: {prompt_file}",
            f""
        ]
        
        # Check if auto-suggestions are enabled
        auto_suggest = self._get_auto_suggest_flag()
        
        if auto_suggest and self.suggestion_service:
            # Auto-execute AI suggestions using skeleton HTML
            try:
                logger.info("Auto-suggestions enabled, calling AI with HTML skeleton...")
                
                # Check skeleton size before sending to AI
                skeleton_size_kb = len(page_html.encode('utf-8')) / 1024
                if skeleton_size_kb > 500:
                    logger.warning(f"HTML skeleton is large ({skeleton_size_kb:.1f}KB), AI may reject or be expensive")
                
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
            skeleton_file_path = html_file.replace('.html', '_skeleton.html')
            error_lines.extend([
                f"💡 To get AI-powered selector suggestions:",
                f"",
                f"   Option 1 - Manual (use any LLM):",
                f"      1. Open skeleton: {skeleton_file_path}",
                f"         (Compact version for AI - faster and cheaper)",
                f"      2. Copy the skeleton HTML content",
                f"      3. Open prompt: {prompt_file}",
                f"      4. Paste both into ChatGPT, Claude, or your preferred LLM",
                f"      5. Get alternative selector suggestions",
                f"",
                f"      Note: Full HTML ({html_file}) available for manual inspection",
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
            Tuple of (html_file_path, prompt_file_path, page_html_skeleton)
        """
        # Create debug directory
        debug_dir = Path('.lamia/selector_failures')
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        html_file = debug_dir / f'failure_{timestamp}.html'
        skeleton_file = debug_dir / f'failure_{timestamp}_skeleton.html'
        prompt_file = debug_dir / f'failure_{timestamp}_prompt.txt'
        
        # Get page HTML
        page_html = None
        html_skeleton = None
        
        try:
            page_html = await self.adapter.get_page_source()
            
            # Save full HTML for user inspection
            html_file.write_text(page_html, encoding='utf-8')
            html_size_kb = len(page_html.encode('utf-8')) / 1024
            logger.debug(f"Saved full HTML to: {html_file} ({html_size_kb:.1f} KB)")
            
            # Create and save compact skeleton for AI
            html_skeleton = self._create_html_skeleton(page_html)
            skeleton_file.write_text(html_skeleton, encoding='utf-8')
            skeleton_size_kb = len(html_skeleton.encode('utf-8')) / 1024
            logger.debug(f"Saved HTML skeleton to: {skeleton_file} ({skeleton_size_kb:.1f} KB, {skeleton_size_kb/html_size_kb*100:.1f}% of original)")
            
        except Exception as e:
            logger.warning(f"Could not save page HTML: {e}")
            error_html = "<html>Error: Could not capture page source</html>"
            html_file.write_text(error_html, encoding='utf-8')
            skeleton_file.write_text(error_html, encoding='utf-8')
            html_skeleton = error_html
        
        # Generate and save prompt (references skeleton file)
        prompt = self._generate_suggestion_prompt(
            failed_selector=failed_selector,
            operation_type=operation_type,
            skeleton_filename=skeleton_file.name
        )
        prompt_file.write_text(prompt, encoding='utf-8')
        logger.debug(f"Saved suggestion prompt to: {prompt_file}")
        
        return str(html_file), str(prompt_file), html_skeleton
    
    def _generate_suggestion_prompt(
        self,
        failed_selector: str,
        operation_type: str,
        skeleton_filename: str = None
    ) -> str:
        """Generate prompt for AI suggestions (saved to file for manual use).
        
        Args:
            failed_selector: The selector that failed
            operation_type: Type of browser operation (click, type, etc.)
            skeleton_filename: Name of the skeleton HTML file
            
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
        
        skeleton_note = f"""
NOTE: Use the companion file '{skeleton_filename}' for AI analysis.
It contains a compact HTML skeleton (structure only, no large content).
The full HTML file is available for manual inspection if needed.
""" if skeleton_filename else ""
        
        return f"""The following CSS selector FAILED to find any elements on the page:

FAILED SELECTOR: {failed_selector}

OPERATION: {operation_desc}

PAGE HTML:{skeleton_note}
(Paste the HTML from the accompanying _skeleton.html file here)

========================================

Your task is to analyze the HTML structure and suggest up to 3 alternative CSS selectors that might work.

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
    
    def _create_html_skeleton(self, html: str, max_text_length: int = 50) -> str:
        """Create a compact HTML skeleton for AI analysis.
        
        Strips out large content while preserving structure, classes, IDs, and attributes
        that are relevant for CSS selectors.
        
        Args:
            html: Full HTML string
            max_text_length: Maximum length of text content to keep
            
        Returns:
            Compact HTML skeleton string (typically 5-20% of original size)
        """
        try:
            # Remove HTML comments (can be huge)
            html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
            
            # Remove large inline scripts (keep tag structure)
            html = re.sub(
                r'<script[^>]*>(.*?)</script>',
                lambda m: f'<script{m.group(0)[7:m.group(0).index(">")]}>/* script removed */</script>' if '>' in m.group(0) else m.group(0),
                html,
                flags=re.DOTALL | re.IGNORECASE
            )
            
            # Remove large inline styles (keep tag structure)
            html = re.sub(
                r'<style[^>]*>(.*?)</style>',
                lambda m: f'<style{m.group(0)[6:m.group(0).index(">")]}>/* styles removed */</style>' if '>' in m.group(0) else m.group(0),
                html,
                flags=re.DOTALL | re.IGNORECASE
            )
            
            # Truncate SVG paths and data (very large)
            html = re.sub(r'<path[^>]*d="[^"]{100,}"', lambda m: m.group(0)[:50] + '..."', html)
            html = re.sub(r'<svg[^>]*>(.*?)</svg>', 
                         lambda m: '<svg' + m.group(0)[4:m.group(0).index('>')+1] + '/* svg content removed */</svg>' if '>' in m.group(0)[:100] else m.group(0),
                         html, flags=re.DOTALL | re.IGNORECASE)
            
            # Truncate very long attribute values (data-* with JSON, etc.)
            html = re.sub(
                r'(\w+)="([^"]{200,})"',
                lambda m: f'{m.group(1)}="{m.group(2)[:100]}..."',
                html
            )
            
            # Truncate text content between tags (keep structure, truncate long text)
            def truncate_text_content(match):
                tag_open = match.group(1)
                text = match.group(2)
                tag_close = match.group(3)
                
                # Skip if it's just whitespace
                if not text.strip():
                    return match.group(0)
                
                # Truncate long text
                if len(text) > max_text_length:
                    text = text[:max_text_length].strip() + '...'
                
                return f'{tag_open}{text}{tag_close}'
            
            # Match text between tags (excluding script/style which we already handled)
            html = re.sub(
                r'(>)([^<]{' + str(max_text_length) + r',})(<)',
                truncate_text_content,
                html
            )
            
            # Add metadata comment
            skeleton_size = len(html.encode('utf-8'))
            header = f"<!-- HTML Skeleton for AI Analysis (size: {skeleton_size/1024:.1f}KB) -->\n"
            header += "<!-- Large content removed: scripts, styles, long text, SVG data -->\n"
            header += "<!-- Structure preserved: tags, classes, IDs, attributes -->\n\n"
            
            return header + html
            
        except Exception as e:
            logger.warning(f"Error creating HTML skeleton: {e}, returning original")
            # Fallback: at least truncate to a reasonable size
            max_chars = 200000  # ~200KB max
            if len(html) > max_chars:
                return html[:max_chars] + "\n\n<!-- HTML truncated due to size -->"
            return html
    
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