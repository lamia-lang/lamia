"""HTTP client manager for web requests (uses requests library directly)."""

from lamia.engine.config_provider import ConfigProvider
from lamia.validation.base import ValidationResult, BaseValidator
from lamia.interpreter.commands import WebCommand, WebActionType
from typing import Optional, Any, Dict
import logging
import asyncio
import requests

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
        if command.action != WebActionType.HTTP_REQUEST:
            raise ValueError(f"Not an HTTP action: {command.action}")

        method: str = (command.method or "GET").upper()
        url: str = command.url or ""
        if not url:
            raise ValueError("HTTP request requires a URL")

        headers: Optional[Dict[str, str]] = command.headers or {}
        data: Optional[Any] = command.data
        timeout: float = float(self._http_options.get("timeout", 30.0))

        # Perform blocking requests call in a thread to preserve async contract
        response_text = await asyncio.to_thread(
            self._do_request,
            method,
            url,
            headers,
            data,
            timeout,
        )

        return response_text
    
    def _do_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]],
        data: Optional[Any],
        timeout: float,
    ) -> str:
        """Execute an HTTP request using requests and return response text."""
        logger.info(f"HTTP {method} {url}")
        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=data,
            timeout=timeout,
        )
        resp.raise_for_status()
        # Prefer text; callers can validate as needed
        return resp.text
    
    # Legacy adapter-based path removed; direct requests implementation above
    
    # Adapter factory removed; using requests directly
    
    async def close(self):
        """Close HTTP manager and cleanup resources."""
        logger.info("HttpManager closed")