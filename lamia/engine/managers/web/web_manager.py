"""Web operations manager - dispatches to browser or HTTP managers."""

from lamia.engine.managers import Manager
from lamia.engine.config_provider import ConfigProvider
from lamia.validation.base import ValidationResult, BaseValidator
from lamia.interpreter.command_types import CommandType
from lamia.interpreter.commands import WebCommand, WebActionType
from lamia.internal_types import BrowserAction, BrowserActionType, BrowserActionParams
from .browser_manager import BrowserManager
from .http_manager import HttpManager
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class WebManager(Manager[WebCommand]):
    """Thin dispatcher that routes web commands to specialized managers."""
    
    def __init__(self, config_provider: ConfigProvider, llm_manager=None):
        """Initialize web manager with specialized sub-managers.
        
        Args:
            config_provider: Configuration provider
            llm_manager: LLM manager for AI selector resolution (optional)
        """
        self.config_provider = config_provider
        self.llm_manager = llm_manager
        
        # Initialize specialized managers
        self.browser_manager = BrowserManager(config_provider, web_manager=self)
        self.http_manager = HttpManager(config_provider)
        
        # Generic stuck detection (website-agnostic)
        self.recent_actions = []  # Track recent actions to detect loops
        self.max_recent_actions = 10
        self.stuck_threshold = 3  # Same action repeated this many times = stuck
        
        # Define which actions go to which manager
        self.browser_actions = {
            WebActionType.NAVIGATE,
            WebActionType.CLICK,
            WebActionType.TYPE,
            WebActionType.WAIT,
            WebActionType.GET_TEXT,
            WebActionType.GET_PAGE_SOURCE,
            WebActionType.GET_ELEMENTS,
            WebActionType.GET_INPUT_TYPE,
            WebActionType.GET_OPTIONS,
            WebActionType.GET_ATTRIBUTE,
            WebActionType.SCREENSHOT,
            WebActionType.HOVER,
            WebActionType.SCROLL,
            WebActionType.SELECT,
            WebActionType.SUBMIT,
            WebActionType.IS_VISIBLE,
            WebActionType.IS_ENABLED,
            WebActionType.IS_CHECKED,
        }
        
        self.http_actions = {
            WebActionType.HTTP_REQUEST,
        }
    
    async def execute(self, command: WebCommand, validator: Optional[BaseValidator] = None) -> ValidationResult:
        """Route command to appropriate specialized manager.
        
        Args:
            command: Web command to execute
            validator: Optional validator for response
            
        Returns:
            ValidationResult from the specialized manager
        """
        logger.debug(f"Routing web command: {command.action}")
        
        # Generic stuck detection (works on any website)
        action_signature = self._get_action_signature(command)
        self._check_for_stuck_behavior(action_signature)
        
        if command.action in self.browser_actions:
            logger.debug(f"Routing to BrowserManager: {command.action}")
            result = await self.browser_manager.execute(command, validator)
        elif command.action in self.http_actions:
            logger.debug(f"Routing to HttpManager: {command.action}")
            result = await self.http_manager.execute(command, validator)
        else:
            raise ValueError(f"Unsupported web action: {command.action}")
        
        # Track successful actions for stuck detection
        self._track_action(action_signature)
        
        # Wrap result in ValidationResult if it's not already
        if validator is not None:
            result_preview = self._format_result_preview(result)
            logger.info(f"Validating result in the web_manager: {result_preview}")
            validation_result = await validator.validate(result)
        else:
            result_preview = self._format_result_preview(result)
            logger.info(f"Validator is None, returning result as is: {result_preview}")
            validation_result = ValidationResult(
                is_valid=True,
                result_type=result,
                error_message=None
            )

        return validation_result
    
    @staticmethod
    def _format_result_preview(result: Any) -> str:
        if isinstance(result, list):
            count = len(result)
            if count == 0:
                return "[] (empty)"
            lines = [f"[{count} elements]:"]
            for i, item in enumerate(result):
                lines.append(f"  [{i}] {repr(item)}")
            return "\n".join(lines)
        result_str = str(result) if result is not None else "None"
        if len(result_str) > 500:
            return result_str[:500] + "..."
        return result_str

    def _get_action_signature(self, command: WebCommand) -> str:
        """Create a unique signature for the action to detect repeats.

        When a command is scoped to a specific element handle, its identity
        is included
        """
        parts = [str(command.action)]
        if command.selector:
            parts.append(str(command.selector))
        elif command.value:
            parts.append(str(command.value))
        if command.scope_element_handle is not None:
            parts.append(f"@{id(command.scope_element_handle)}")
        return ":".join(parts)
    
    def _check_for_stuck_behavior(self, action_signature: str) -> None:
        """Check if we're stuck repeating the same action."""
        # Count recent occurrences of this action
        recent_count = self.recent_actions.count(action_signature)
        
        if recent_count >= self.stuck_threshold:
            error_msg = f"Stuck detection: Action '{action_signature}' repeated {recent_count} times. Possible causes: required fields not filled, wrong selectors, page not changing"
            logger.warning(error_msg)
            # Raise exception to stop the stuck behavior
            raise RuntimeError(f"Automation stuck in loop: {error_msg}")
    
    def _track_action(self, action_signature: str) -> None:
        """Track successful action for stuck detection."""
        self.recent_actions.append(action_signature)
        
        # Keep only recent actions to prevent memory bloat
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions.pop(0)
    
    async def close(self):
        """Close all sub-managers and cleanup resources."""
        await self.browser_manager.close()
        await self.http_manager.close()
        logger.info("WebManager closed")