"""HTTP client manager for web requests."""

from lamia.engine.config_provider import ConfigProvider
from lamia.validation.base import ValidationResult, BaseValidator
from lamia.types import HttpAction, HttpActionType
from lamia.adapters.web.http.base import BaseHttpAdapter
from lamia.adapters.retry.factory import RetriableAdapterFactory
from lamia.interpreter.commands import WebCommand, WebActionType
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class HttpManager:
    """Manages HTTP operations for web requests."""
    
    def __init__(self, config_provider: ConfigProvider):
        """Initialize HTTP manager.
        
        Args:
            config_provider: Configuration provider
        """
        self.config_provider = config_provider
        
        # Get HTTP configuration
        web_config = config_provider.get_web_config()
        self._http_client = web_config.get("http_client", "requests")
        self._http_options = web_config.get("http_options", {})
        
        # Set defaults
        self._http_options.setdefault("timeout", 30.0)
        self._http_options.setdefault("user_agent", "Lamia/1.0")
    
    async def execute(self, command: WebCommand, validator: Optional[BaseValidator] = None) -> Any:
        """Execute HTTP command.
        
        Args:
            command: Web command containing HTTP action
            validator: Optional validator for response
            
        Returns:
            Result of HTTP action
        """
        # Convert WebCommand to HttpAction
        http_action = self._web_command_to_http_action(command)
        
        # Execute HTTP action
        return await self._execute_http_action(http_action)
    
    def _web_command_to_http_action(self, command: WebCommand) -> HttpAction:
        """Convert WebCommand to HttpAction."""
        if command.action != WebActionType.HTTP_REQUEST:
            raise ValueError(f"Not an HTTP action: {command.action}")
        
        return HttpAction(
            action=HttpActionType.REQUEST,
            url=command.url,
            method=command.method or "GET",
            headers=command.headers or {},
            data=command.data,
            timeout=self._http_options.get("timeout", 30.0)
        )
    
    async def _execute_http_action(self, action: HttpAction) -> Any:
        """Execute HTTP action using appropriate adapter."""
        # Get HTTP adapter (this will create it if needed)
        adapter = await self._get_http_adapter()
        
        # Execute action using adapter
        if action.action == HttpActionType.REQUEST:
            return await adapter.request(
                method=action.method,
                url=action.url,
                headers=action.headers,
                data=action.data,
                timeout=action.timeout
            )
        else:
            raise ValueError(f"Unsupported HTTP action: {action.action}")
    
    async def _get_http_adapter(self) -> BaseHttpAdapter:
        """Get HTTP adapter with retry capabilities."""
        # Import here to avoid circular imports
        from lamia.adapters.web.http.requests_adapter import RequestsAdapter
        
        # Create base adapter
        if self._http_client == "requests":
            base_adapter = RequestsAdapter(
                timeout=self._http_options.get("timeout", 30.0),
                user_agent=self._http_options.get("user_agent", "Lamia/1.0")
            )
        else:
            raise ValueError(f"Unsupported HTTP client: {self._http_client}")
        
        # Wrap with retry capabilities
        retry_adapter = RetriableAdapterFactory.create_adapter(base_adapter)
        
        return retry_adapter
    
    async def close(self):
        """Close HTTP manager and cleanup resources."""
        logger.info("HttpManager closed")