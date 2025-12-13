"""Web operations manager - dispatches to browser or HTTP managers."""

import rsa
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
        self.browser_manager = BrowserManager(config_provider)
        self.http_manager = HttpManager(config_provider)
        
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
        
        if command.action in self.browser_actions:
            logger.debug(f"Routing to BrowserManager: {command.action}")
            result = await self.browser_manager.execute(command, validator)
        elif command.action in self.http_actions:
            logger.debug(f"Routing to HttpManager: {command.action}")
            result = await self.http_manager.execute(command, validator)
        else:
            raise ValueError(f"Unsupported web action: {command.action}")
        
        # Wrap result in ValidationResult if it's not already
        if validator is not None:
            logger.info(f"Validating result in the web_manager: {result[0:1000] + '...' if result else 'None'}")
            validation_result = await validator.validate(result)
        else:
            logger.info(f"Validator is None, returning result as is: {result}")
            validation_result = ValidationResult(
                is_valid=True,
                result_type=result,
                error_message=None
            )

        return validation_result
    
    async def close(self):
        """Close all sub-managers and cleanup resources."""
        await self.browser_manager.close()
        await self.http_manager.close()
        logger.info("WebManager closed")