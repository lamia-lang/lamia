"""HTTP adapter using requests library."""

from .base import BaseHttpAdapter
from lamia.types import HttpActionParams
import logging
from typing import Any, Optional
import requests
import json

logger = logging.getLogger(__name__)


class RequestsAdapter(BaseHttpAdapter):
    """HTTP adapter using the requests library."""
    
    def __init__(self, timeout: float = 30.0, user_agent: str = "Lamia/1.0"):
        self.session = None
        self.default_timeout = timeout
        self.user_agent = user_agent
        self.initialized = False
    
    async def initialize(self) -> None:
        """Initialize the HTTP adapter."""
        logger.info("RequestsAdapter: Initializing requests session...")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent
        })
        self.initialized = True
        logger.info("RequestsAdapter: Requests session initialized")
    
    async def close(self) -> None:
        """Close the HTTP adapter and cleanup resources."""
        if self.session:
            logger.info("RequestsAdapter: Closing requests session...")
            self.session.close()
            self.session = None
            self.initialized = False
            logger.info("RequestsAdapter: Requests session closed")
    
    def _prepare_request_kwargs(self, params: HttpActionParams) -> dict:
        """Prepare common request arguments."""
        kwargs = {
            'timeout': self.default_timeout,
            'headers': params.headers or {},
            'params': params.params
        }
        
        # Handle data based on type
        if params.data is not None:
            if isinstance(params.data, dict):
                # If it's a dict, send as JSON
                kwargs['json'] = params.data
                kwargs['headers'].setdefault('Content-Type', 'application/json')
            else:
                # Otherwise send as form data or raw data
                kwargs['data'] = params.data
        
        return kwargs
    
    def _handle_response(self, response: requests.Response) -> Any:
        """Handle response and return appropriate data structure."""
        try:
            # Try to parse as JSON first
            return response.json()
        except json.JSONDecodeError:
            # If not JSON, return text content
            return response.text
    
    async def get(self, params: HttpActionParams) -> Any:
        """Send GET request."""
        if not self.initialized:
            raise RuntimeError("RequestsAdapter not initialized")
        
        logger.info(f"RequestsAdapter: GET {params.url}")
        kwargs = self._prepare_request_kwargs(params)
        # Remove data for GET requests
        kwargs.pop('json', None)
        kwargs.pop('data', None)
        
        response = self.session.get(params.url, **kwargs)
        response.raise_for_status()
        return self._handle_response(response)
    
    async def post(self, params: HttpActionParams) -> Any:
        """Send POST request."""
        if not self.initialized:
            raise RuntimeError("RequestsAdapter not initialized")
        
        logger.info(f"RequestsAdapter: POST {params.url}")
        kwargs = self._prepare_request_kwargs(params)
        
        response = self.session.post(params.url, **kwargs)
        response.raise_for_status()
        return self._handle_response(response)
    
    async def put(self, params: HttpActionParams) -> Any:
        """Send PUT request."""
        if not self.initialized:
            raise RuntimeError("RequestsAdapter not initialized")
        
        logger.info(f"RequestsAdapter: PUT {params.url}")
        kwargs = self._prepare_request_kwargs(params)
        
        response = self.session.put(params.url, **kwargs)
        response.raise_for_status()
        return self._handle_response(response)
    
    async def patch(self, params: HttpActionParams) -> Any:
        """Send PATCH request."""
        if not self.initialized:
            raise RuntimeError("RequestsAdapter not initialized")
        
        logger.info(f"RequestsAdapter: PATCH {params.url}")
        kwargs = self._prepare_request_kwargs(params)
        
        response = self.session.patch(params.url, **kwargs)
        response.raise_for_status()
        return self._handle_response(response)
    
    async def delete(self, params: HttpActionParams) -> Any:
        """Send DELETE request."""
        if not self.initialized:
            raise RuntimeError("RequestsAdapter not initialized")
        
        logger.info(f"RequestsAdapter: DELETE {params.url}")
        kwargs = self._prepare_request_kwargs(params)
        # Remove data for DELETE requests (optional)
        kwargs.pop('json', None)
        kwargs.pop('data', None)
        
        response = self.session.delete(params.url, **kwargs)
        response.raise_for_status()
        return self._handle_response(response)
    
    async def head(self, params: HttpActionParams) -> Any:
        """Send HEAD request."""
        if not self.initialized:
            raise RuntimeError("RequestsAdapter not initialized")
        
        logger.info(f"RequestsAdapter: HEAD {params.url}")
        kwargs = self._prepare_request_kwargs(params)
        # Remove data for HEAD requests
        kwargs.pop('json', None)
        kwargs.pop('data', None)
        
        response = self.session.head(params.url, **kwargs)
        response.raise_for_status()
        # HEAD responses don't have body content
        return response.headers
    
    async def options(self, params: HttpActionParams) -> Any:
        """Send OPTIONS request."""
        if not self.initialized:
            raise RuntimeError("RequestsAdapter not initialized")
        
        logger.info(f"RequestsAdapter: OPTIONS {params.url}")
        kwargs = self._prepare_request_kwargs(params)
        # Remove data for OPTIONS requests
        kwargs.pop('json', None)
        kwargs.pop('data', None)
        
        response = self.session.options(params.url, **kwargs)
        response.raise_for_status()
        return response.headers
