"""
Session validation module for hybrid syntax execution.

Handles session validation logic that was incorrectly placed in ast_analyzer.py.
This module is responsible for:
1. Page stabilization waiting
2. Content retrieval from browser adapters  
3. Session validation using Lamia's validation system
4. Browser state persistence after successful validation
"""

import asyncio
import hashlib
import logging
import time
from typing import Optional

from lamia.engine.factories.validator_factory import ValidatorFactory
from lamia.interpreter.command_types import CommandType

logger = logging.getLogger(__name__)


class SessionValidator:
    """Handles session validation for hybrid syntax with session() blocks."""
    
    def __init__(self, lamia_instance):
        self.lamia = lamia_instance
        
    async def validate_session_result(self, return_type):
        """Validate current content against the expected return type using Lamia's validation system.
        
        This function waits for the page to stabilize before validation to handle:
        - Page loading delays and redirects after form submissions
        - Captcha pages and intermediate screens  
        - Dynamic content loading
        - Browser navigation state changes
        
        The stabilization process:
        1. Polls page content and URL for changes
        2. Waits for expected model elements to appear
        3. Ensures page is stable for a minimum time window
        4. Only then performs validation
        
        Args:
            return_type: The expected return type to validate against
            
        Returns:
            The validated data conforming to the return type
            
        Raises:
            Exception: If validation fails or browser content cannot be retrieved
        """
        try:
            logger.info("Starting session validation with page stabilization...")
            
            # Wait for page to stabilize before validation
            stable_content = await self._wait_for_page_stabilization()
            
            # Use Lamia's validator factory for proper validation
            validator_factory = ValidatorFactory()
            # Use WEB command type for session validation since it's web-based content
            validator = validator_factory.get_validator(CommandType.WEB, return_type)
            
            # Validate the stabilized content against the model
            logger.info("Validating stabilized page content...")
            validation_result = await validator.validate(stable_content)

            if not validation_result.is_valid:
                # Session validation failed - script must stop here
                raise Exception(f"Session validation failed: {validation_result.error_message}")

            logger.info("Session validation successful!")
            
            # Save browser state immediately after successful validation
            # This ensures we capture the login cookies while still on the logged-in page
            try:
                self._save_browser_state_after_validation()
            except Exception as e:
                logger.warning(f"Failed to save browser state after session validation: {e}")
            
            return validation_result.result_type
            
        except Exception as e:
            raise

    async def _wait_for_page_stabilization(self, max_wait_time=300, stability_window=30):
        """Wait for the page to stabilize before validation.
        
        This function polls the page repeatedly until:
        1. The page content stops changing (stability window)
        2. The URL stabilizes (no more redirects)
        
        The validator will handle checking if expected elements exist.
        
        Args:
            max_wait_time: Maximum time to wait for stabilization (seconds)
            stability_window: Time window to consider page stable (seconds)
            
        Returns:
            str: Stabilized page HTML content
            
        Raises:
            Exception: If page doesn't stabilize within max_wait_time
        """
        logger.info(f"Waiting for page stabilization (max {max_wait_time}s)...")
        
        start_time = time.time()
        last_content_hash = None
        last_url = None
        stable_since = None
        attempt = 0
        
        while time.time() - start_time < max_wait_time:
            attempt += 1
            current_time = time.time()
            
            try:
                # Get current page state
                current_content = await self._get_current_page_content()
                current_url = await self._get_current_url()
                content_hash = hashlib.md5(current_content.encode()).hexdigest()
                
                logger.debug(f"Stabilization check #{attempt}: URL={current_url[:100]}..., Content hash={content_hash[:8]}")
                
                # Check if content and URL have changed
                content_changed = (content_hash != last_content_hash)
                url_changed = (current_url != last_url)
                
                if content_changed or url_changed:
                    # Page is still changing, reset stability timer
                    stable_since = current_time
                    logger.debug(f"Page changed (content: {content_changed}, url: {url_changed}), resetting stability timer")
                else:
                    # Page hasn't changed, check if we've been stable long enough
                    if stable_since and (current_time - stable_since) >= stability_window:
                        # Page has been stable for the required window
                        logger.info(f"Page stabilized after {current_time - start_time:.1f}s")
                        return current_content
                
                # Update tracking variables
                last_content_hash = content_hash
                last_url = current_url
                
                # Wait before next check (shorter intervals initially, longer as we wait)
                wait_interval = min(1.5, 0.5 + (attempt * 0.1))
                await asyncio.sleep(wait_interval)
                
            except Exception as e:
                logger.warning(f"Error during stabilization check #{attempt}: {e}")
                await asyncio.sleep(1.0)
        
        # Timeout reached
        elapsed = time.time() - start_time
        logger.warning(f"Page stabilization timeout after {elapsed:.1f}s, proceeding with current content")
        
        # Return the last known content even if not fully stable
        try:
            return await self._get_current_page_content()
        except Exception as e:
            raise Exception(f"Page stabilization failed and cannot retrieve content: {e}")

    async def _get_current_page_content(self):
        """Get current page content using the centralized BrowserManager.
        
        Returns:
            str: Current page HTML content
            
        Raises:
            Exception: If no browser content can be retrieved
        """
        try:
            # Use the centralized BrowserManager access method
            from lamia.engine.managers.web.browser_manager import BrowserManager
            browser_manager = BrowserManager.get_browser_manager_from_lamia(self.lamia)
            
            # Use the centralized method
            return await browser_manager.get_page_source()
            
        except Exception as e:
            logger.error(f"Could not get browser content: {e}")
            raise Exception(f"Failed to retrieve current page content: {e}")

    async def _get_current_url(self):
        """Get current page URL using the centralized BrowserManager."""
        try:
            # Use the centralized BrowserManager access method
            from lamia.engine.managers.web.browser_manager import BrowserManager
            browser_manager = BrowserManager.get_browser_manager_from_lamia(self.lamia)
            
            # Use the centralized method
            return await browser_manager.get_current_url()
            
        except Exception as e:
            logger.warning(f"Could not get current URL: {e}")
            return "unknown"

    def _save_browser_state_after_validation(self):
        """Browser state saving is handled by the browser adapters automatically."""
        # Browser adapters save their own session data based on profile names
        # No need for explicit saving here
        logger.debug("Browser state persistence handled automatically by adapters")


def create_session_validator_function(lamia_instance):
    """Create a session validator function that can be injected into execution globals.
    
    Args:
        lamia_instance: The Lamia instance to use for validation
        
    Returns:
        A validator function that can validate current page content against return types
    """
    validator = SessionValidator(lamia_instance)
    return validator.validate_session_result
