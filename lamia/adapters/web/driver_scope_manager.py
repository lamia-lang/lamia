"""Scope-based driver lifecycle manager for web automation.

Manages browser driver instances based on execution scope:
- Global scope: One driver for entire .hu file execution
- Function scope: Separate driver per function, cleaned up when function ends
"""

import asyncio
import logging
import weakref
from typing import Dict, Optional, Any
from contextlib import asynccontextmanager

from .browser.base import BaseBrowserAdapter

logger = logging.getLogger(__name__)


class DriverScopeManager:
    """Manages browser driver lifecycles based on execution scope."""
    
    def __init__(self):
        self._global_driver: Optional[BaseBrowserAdapter] = None
        self._function_drivers: Dict[str, BaseBrowserAdapter] = {}
        self._scope_stack: list[str] = []  # Track nested scopes
        self._cleanup_callbacks: Dict[str, list] = {}
        
    async def get_driver(
        self, 
        scope_type: str = 'global',
        scope_id: Optional[str] = None,
        adapter_factory: Optional[callable] = None
    ) -> BaseBrowserAdapter:
        """Get or create a driver for the specified scope.
        
        Args:
            scope_type: 'global' or 'function'
            scope_id: Unique identifier for function scope (function name/hash)
            adapter_factory: Factory function to create new adapter instances
            
        Returns:
            Browser adapter instance for the scope
        """
        if scope_type == 'global':
            if not self._global_driver and adapter_factory:
                logger.info("Creating global scope browser driver")
                self._global_driver = await adapter_factory()
                
            if not self._global_driver:
                raise RuntimeError("No global driver available and no factory provided")
                
            return self._global_driver
            
        elif scope_type == 'function':
            if not scope_id:
                raise ValueError("scope_id required for function scope")
                
            if scope_id not in self._function_drivers and adapter_factory:
                logger.info(f"Creating function scope browser driver for: {scope_id}")
                self._function_drivers[scope_id] = await adapter_factory()
                self._cleanup_callbacks[scope_id] = []
                
            if scope_id not in self._function_drivers:
                raise RuntimeError(f"No driver for function scope '{scope_id}' and no factory provided")
                
            return self._function_drivers[scope_id]
            
        else:
            raise ValueError(f"Unsupported scope type: {scope_type}")
    
    async def enter_scope(self, scope_type: str, scope_id: Optional[str] = None):
        """Enter a new execution scope."""
        if scope_type == 'function' and scope_id:
            self._scope_stack.append(scope_id)
            logger.debug(f"Entered function scope: {scope_id}")
        elif scope_type == 'global':
            logger.debug("Entered global scope")
    
    async def exit_scope(self, scope_type: str, scope_id: Optional[str] = None):
        """Exit execution scope and cleanup resources."""
        if scope_type == 'function' and scope_id:
            if scope_id in self._scope_stack:
                self._scope_stack.remove(scope_id)
            
            # Cleanup function scope driver
            if scope_id in self._function_drivers:
                logger.info(f"Cleaning up function scope driver: {scope_id}")
                driver = self._function_drivers[scope_id]
                await driver.close()
                del self._function_drivers[scope_id]
                
                # Run cleanup callbacks
                for callback in self._cleanup_callbacks.get(scope_id, []):
                    try:
                        await callback()
                    except Exception as e:
                        logger.warning(f"Error in cleanup callback: {e}")
                
                if scope_id in self._cleanup_callbacks:
                    del self._cleanup_callbacks[scope_id]
                    
        elif scope_type == 'global':
            # Don't automatically cleanup global scope - managed externally
            logger.debug("Exited global scope")
    
    @asynccontextmanager
    async def function_scope(self, scope_id: str, adapter_factory: callable):
        """Context manager for function scope driver lifecycle.
        
        Usage:
            async with scope_manager.function_scope("my_function", factory) as driver:
                await driver.navigate(...)
                # Driver automatically closed when exiting context
        """
        await self.enter_scope('function', scope_id)
        try:
            driver = await self.get_driver('function', scope_id, adapter_factory)
            yield driver
        finally:
            await self.exit_scope('function', scope_id)
    
    def add_cleanup_callback(self, scope_id: str, callback: callable):
        """Add cleanup callback for a scope."""
        if scope_id not in self._cleanup_callbacks:
            self._cleanup_callbacks[scope_id] = []
        self._cleanup_callbacks[scope_id].append(callback)
    
    async def cleanup_global_scope(self):
        """Explicitly cleanup global scope driver."""
        if self._global_driver:
            logger.info("Cleaning up global scope driver")
            await self._global_driver.close()
            self._global_driver = None
    
    async def cleanup_all(self):
        """Cleanup all scoped drivers."""
        # Cleanup function scopes
        for scope_id in list(self._function_drivers.keys()):
            await self.exit_scope('function', scope_id)
            
        # Cleanup global scope
        await self.cleanup_global_scope()
        
        # Clear state
        self._scope_stack.clear()
        self._cleanup_callbacks.clear()
    
    def get_current_scope(self) -> Optional[str]:
        """Get the current active function scope ID."""
        return self._scope_stack[-1] if self._scope_stack else None
    
    def is_in_function_scope(self) -> bool:
        """Check if currently in a function scope."""
        return len(self._scope_stack) > 0


# Global instance for the application
_global_scope_manager = DriverScopeManager()


def get_scope_manager() -> DriverScopeManager:
    """Get the global driver scope manager instance."""
    return _global_scope_manager


async def with_driver_scope(scope_type: str = 'global', scope_id: Optional[str] = None):
    """Decorator/context manager for automatic driver scope management."""
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            scope_manager = get_scope_manager()
            
            if scope_type == 'function':
                function_scope_id = scope_id or f"{func.__module__}.{func.__name__}"
                await scope_manager.enter_scope('function', function_scope_id)
                try:
                    return await func(*args, **kwargs)
                finally:
                    await scope_manager.exit_scope('function', function_scope_id)
            else:
                # Global scope - just execute
                return await func(*args, **kwargs)
                
        return wrapper
    return decorator