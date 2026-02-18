"""Browser overlay manager for visual element selection."""

import logging
import asyncio
import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class BrowserOverlay:
    """
    Manages browser overlay injection and user interaction for visual element picking.
    
    Handles:
    - JavaScript injection for element highlighting
    - User interaction coordination
    - Element selection result processing
    """
    
    def __init__(self, browser_adapter):
        """Initialize overlay manager.
        
        Args:
            browser_adapter: Browser adapter for JavaScript execution
        """
        self.browser = browser_adapter
        self._picker_js = None
        self._selection_result = None
        self._selection_event = None
    
    async def pick_single_element(
        self,
        instruction: str,
        element_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Show overlay for selecting a single element.
        
        Args:
            instruction: User instruction text to display
            element_filter: Optional JavaScript function to filter highlightable elements
            
        Returns:
            Dictionary with selected element information
        """
        logger.info(f"Starting single element picker: {instruction}")
        
        try:
            # Inject picker JavaScript
            await self._inject_picker_js()
            
            # Setup selection callback
            self._selection_event = asyncio.Event()
            self._selection_result = None
            
            # Start picker with options
            options = {
                'instruction': instruction
            }
            
            if element_filter:
                options['elementFilter'] = element_filter
            
            await self._start_picker(options)
            
            # Wait for user selection (no timeout - wait indefinitely)
            await self._selection_event.wait()
            
            if not self._selection_result:
                raise ValueError("No element was selected")
            
            logger.info("Single element selected successfully")
            return {
                'selected_element': self._selection_result,
                'selection_type': 'single'
            }
            
        finally:
            await self._cleanup_picker()
    
    async def pick_container_for_multiple(
        self,
        instruction: str,
        element_filter: Optional[str] = None,
        allow_progressive_expansion: bool = True
    ) -> Dict[str, Any]:
        """
        Show overlay for selecting a container that should contain multiple elements.
        
        Args:
            instruction: User instruction text to display
            element_filter: Optional JavaScript function to filter highlightable elements  
            allow_progressive_expansion: Whether to allow expanding scope if needed
            
        Returns:
            Dictionary with selected container information
        """
        logger.info(f"Starting container picker for multiple elements: {instruction}")
        
        try:
            # Inject picker JavaScript
            await self._inject_picker_js()
            
            # Setup selection callback
            self._selection_event = asyncio.Event()
            self._selection_result = None
            
            # Start picker with container-focused options
            options = {
                'instruction': instruction + "\\n(Select the container/area that contains the elements)"
            }
            
            if element_filter:
                options['elementFilter'] = element_filter
            
            await self._start_picker(options)
            
            # Wait for user selection (no timeout - wait indefinitely)
            await self._selection_event.wait()
            
            if not self._selection_result:
                raise ValueError("No container was selected")
            
            logger.info("Container selected successfully for multiple elements")
            return {
                'selected_element': self._selection_result,
                'selection_type': 'container',
                'allow_progressive_expansion': allow_progressive_expansion
            }
            
        finally:
            await self._cleanup_picker()
    
    async def expand_scope(self, current_element: Dict[str, Any], levels: int = 1) -> Dict[str, Any]:
        """
        Expand selection scope by moving up the DOM tree.
        
        Args:
            current_element: Current selected element info
            levels: Number of parent levels to go up
            
        Returns:
            Information about the expanded scope element
        """
        logger.info(f"Expanding scope by {levels} levels")
        
        current_xpath = current_element.get('xpath', '')
        if not current_xpath:
            raise ValueError("Cannot expand scope - no XPath available")
        
        # Create JavaScript to find parent element
        js_code = f"""
        var currentEl = document.evaluate('{current_xpath}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
        var parentEl = currentEl;
        for (var i = 0; i < {levels}; i++) {{
            if (parentEl && parentEl.parentElement) {{
                parentEl = parentEl.parentElement;
            }} else {{
                break;
            }}
        }}
        
        if (parentEl && parentEl !== currentEl) {{
            // Return parent element info
            window.lamiaHighlighter.getElementInfo(parentEl);
        }} else {{
            null;
        }}
        """
        
        try:
            result = await self.browser.execute_script(js_code)
            if result:
                return result
            else:
                raise ValueError(f"Could not expand scope by {levels} levels")
        except Exception as e:
            logger.error(f"Failed to expand scope: {e}")
            raise ValueError(f"Scope expansion failed: {e}")
    
    async def _inject_picker_js(self) -> None:
        """Inject the picker JavaScript into the current page."""
        
        if self._picker_js is None:
            # Load JavaScript from file
            js_path = Path(__file__).parent / "ui" / "highlighter.js"
            with open(js_path, 'r') as f:
                self._picker_js = f.read()
        
        # Inject the JavaScript
        await self.browser.execute_script(self._picker_js)
        
        # Setup Python callback handlers
        callback_js = """
        window.lamiaElementSelected = function(elementInfo) {
            window.lamiaSelectionResult = elementInfo;
        };
        
        window.lamiaPickerCancelled = function() {
            window.lamiaSelectionResult = null;
            window.lamiaPickerCancelled = true;
        };
        
        window.lamiaSelectionResult = null;
        window.lamiaPickerCancelled = false;
        """
        
        await self.browser.execute_script(callback_js)
        logger.debug("Picker JavaScript injected successfully")
    
    async def _start_picker(self, options: Dict[str, Any]) -> None:
        """Start the visual picker with given options."""
        
        options_json = json.dumps(options)
        js_code = f"window.startLamiaPicker({options_json});"
        
        await self.browser.execute_script(js_code)
        logger.debug("Visual picker started")
        
        # Start polling for selection result
        asyncio.create_task(self._poll_for_selection())
    
    async def _poll_for_selection(self) -> None:
        """Poll for selection result from JavaScript."""
        
        poll_js = """
        var result = {
            result: window.lamiaSelectionResult,
            cancelled: window.lamiaPickerCancelled || false,
            pickerActive: !!window.lamiaHighlighter
        };
        return result;
        """
        
        logger.info("🖱️ Waiting for user selection in browser... (Please click on an element or press ESC to cancel)")
        
        # Optional: Add periodic audio reminder beeps
        beep_counter = 0
        poll_count = 0
        
        while not self._selection_event.is_set():
            try:
                result = await self.browser.execute_script(poll_js)
                poll_count += 1
                
                if result.get('cancelled'):
                    logger.info("Element selection was cancelled by user")
                    self._selection_event.set()
                    break
                
                selection_result = result.get('result')
                if selection_result:
                    logger.info(f"Selection received: {selection_result.get('tagName', '?')} "
                                f"(id={selection_result.get('id', '')}, "
                                f"class={selection_result.get('className', '')[:60]})")
                    self._selection_result = selection_result
                    self._selection_event.set()
                    break
                
                if poll_count % 6 == 0:
                    logger.info(f"Visual picker still waiting for selection... ({poll_count * 5}s elapsed)")

                await asyncio.sleep(5.0)
                
                # Optional periodic beep every 30 seconds (6 x 5 second cycles)
                beep_counter += 1
                if beep_counter >= 6:  # Every 30 seconds
                    beep_counter = 0
                    try:
                        # Play a gentle beep sound via browser audio API
                        await self._play_reminder_beep()
                    except Exception:
                        pass  # Silent fail if audio not available
                
            except Exception as e:
                logger.error(f"Error polling for selection: {e}")
                await asyncio.sleep(0.5)  # Longer wait on error
    
    async def _cleanup_picker(self) -> None:
        """Clean up the picker overlay and JavaScript."""
        
        cleanup_js = """
        if (window.stopLamiaPicker) {
            window.stopLamiaPicker();
        }
        
        // Clear selection state
        window.lamiaSelectionResult = null;
        window.lamiaPickerCancelled = false;
        """
        
        try:
            await self.browser.execute_script(cleanup_js)
            logger.debug("Picker overlay cleaned up")
        except Exception as e:
            logger.warning(f"Error cleaning up picker: {e}")
    
    async def show_user_message(self, title: str, message: str, timeout: int = 5) -> None:
        """Show a message to the user via browser overlay.
        
        Args:
            title: Message title
            message: Message content
            timeout: Auto-hide timeout in seconds
        """
        
        show_message_js = f"""
        var messageDiv = document.createElement('div');
        messageDiv.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #333;
            color: white;
            padding: 20px 30px;
            border-radius: 8px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 16px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
            z-index: 1000001;
            max-width: 400px;
            text-align: center;
        `;
        
        messageDiv.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 10px;">{title}</div>
            <div>{message}</div>
        `;
        
        document.body.appendChild(messageDiv);
        
        setTimeout(function() {{
            if (messageDiv.parentNode) {{
                messageDiv.parentNode.removeChild(messageDiv);
            }}
        }}, {timeout * 1000});
        """
        
        try:
            await self.browser.execute_script(show_message_js)
        except Exception as e:
            logger.warning(f"Failed to show user message: {e}")
    
    async def _play_reminder_beep(self) -> None:
        """Play a gentle reminder beep to indicate visual picker is waiting."""
        
        beep_js = """
        try {
            // Create a gentle beep using Web Audio API
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            // Gentle 800Hz tone for 0.2 seconds
            oscillator.frequency.value = 800;
            oscillator.type = 'sine';
            gainNode.gain.setValueAtTime(0.1, audioContext.currentTime); // Quiet volume
            
            oscillator.start();
            oscillator.stop(audioContext.currentTime + 0.2);
            
            console.log('🔔 Visual picker reminder beep');
        } catch (e) {
            console.log('Audio not available for reminder beep');
        }
        """
        
        try:
            await self.browser.execute_script(beep_js)
        except Exception as e:
            logger.debug(f"Reminder beep failed: {e}")