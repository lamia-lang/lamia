"""AST analyzer for detecting used action namespaces in .hu files."""

import ast
import asyncio
import logging
from typing import Set, Dict, Any
from lamia.types import HTML, JSON, CSV, XML, YAML, Markdown
from lamia.validation.validators.file_validators.file_structure.html_structure_validator import HTMLStructureValidator
from lamia.validation.validators.file_validators.file_structure.json_structure_validator import JSONStructureValidator
from lamia.engine.managers.web.web_manager import WebManager
from lamia.engine.factories.validator_factory import ValidatorFactory
from lamia.interpreter.command_types import CommandType

logger = logging.getLogger(__name__)


async def _get_current_page_content(lamia_instance):
    """Get current page content from the global browser adapter managed by Lamia engine.
    
    This reuses the existing browser instance instead of creating new ones.
    
    Args:
        lamia_instance: The Lamia instance from execution context
        
    Returns:
        str: Current page HTML content
        
    Raises:
        Exception: If no browser content can be retrieved
    """
    try:
        # Get the engine from lamia instance
        engine = lamia_instance._engine
        
        # Get the existing web manager from the manager factory (singleton pattern)
        from lamia.interpreter.command_types import CommandType
        web_manager = engine.manager_factory.get_manager(CommandType.WEB)
        
        # Access the browser manager's cached browser adapter
        browser_manager = web_manager.browser_manager
        
        if browser_manager._browser_adapter:
            # Use the existing global browser adapter
            adapter = browser_manager._browser_adapter
            
            # Handle RetryingBrowserAdapter wrapper - use the retry-aware method
            if hasattr(adapter, 'get_page_source'):
                # This is a retrying adapter, use its method which handles retries
                current_content = await adapter.get_page_source()
            else:
                # Fallback: direct access to underlying adapter
                if hasattr(adapter, 'adapter'):
                    actual_adapter = adapter.adapter
                else:
                    actual_adapter = adapter
                current_content = actual_adapter.driver.page_source
        else:
            # No active browser adapter - this means no browser operations have been performed yet
            raise Exception("No active browser adapter found. Ensure web operations have been performed before validation.")
        
        return current_content
        
    except Exception as e:
        logger.error(f"Could not get browser content: {e}")
        raise Exception(f"Failed to retrieve current page content: {e}")


async def _wait_for_page_stabilization(lamia_instance, max_wait_time=300, stability_window=30):
    """Wait for the page to stabilize before validation.
    
    This function polls the page repeatedly until:
    1. The page content stops changing (stability window)
    2. The URL stabilizes (no more redirects)
    
    The validator will handle checking if expected elements exist.
    
    Args:
        lamia_instance: The Lamia instance from execution context
        max_wait_time: Maximum time to wait for stabilization (seconds)
        stability_window: Time window to consider page stable (seconds)
        
    Returns:
        str: Stabilized page HTML content
        
    Raises:
        Exception: If page doesn't stabilize within max_wait_time
    """
    import asyncio
    import time
    import hashlib
    
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
            current_content = await _get_current_page_content(lamia_instance)
            current_url = await _get_current_url(lamia_instance)
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
        return await _get_current_page_content(lamia_instance)
    except Exception as e:
        raise Exception(f"Page stabilization failed and cannot retrieve content: {e}")


async def _get_current_url(lamia_instance):
    """Get current page URL from the browser adapter."""
    try:
        engine = lamia_instance._engine
        from lamia.interpreter.command_types import CommandType
        web_manager = engine.manager_factory.get_manager(CommandType.WEB)
        browser_manager = web_manager.browser_manager
        
        if browser_manager._browser_adapter:
            adapter = browser_manager._browser_adapter
            if hasattr(adapter, 'get_current_url'):
                return await adapter.get_current_url()
            elif hasattr(adapter, 'adapter') and hasattr(adapter.adapter, 'get_current_url'):
                return await adapter.adapter.get_current_url()
            else:
                # Fallback for selenium
                return adapter.driver.current_url if hasattr(adapter, 'driver') else "unknown"
        else:
            return "unknown"
    except Exception as e:
        logger.warning(f"Could not get current URL: {e}")
        return "unknown"




def create_session_validator(lamia_instance):
    """Create a session validator function that validates current content against any return type.
    
    Args:
        lamia_instance: The Lamia instance to use for validation
        
    Returns:
        A validator function that can validate current page content against return types
    """
    async def validate_session_result(return_type):
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
        import asyncio
        import time
        
        try:
            logger.info("Starting session validation with page stabilization...")
            
            # Wait for page to stabilize before validation
            stable_content = await _wait_for_page_stabilization(lamia_instance)
            
            # Use Lamia's validator factory for proper validation
            validator_factory = ValidatorFactory()
            # Use WEB command type for session validation since it's web-based content
            validator = validator_factory.get_validator(CommandType.WEB, return_type);
            
            # Validate the stabilized content against the model
            logger.info("Validating stabilized page content...")
            validation_result = await validator.validate(stable_content)
    
            if not validation_result.is_valid:
                # Session validation failed - script must stop here
                raise Exception(f"Session validation failed: {validation_result.error_message}")

            logger.info("Session validation successful!")
            return validation_result.result_type
            
        except Exception as e:
            raise
    
    return validate_session_result


class ActionNamespaceAnalyzer(ast.NodeVisitor):
    """Analyzes AST to detect which action namespaces are used."""
    
    def __init__(self):
        self.used_namespaces: Set[str] = set()
        self.used_types: Set[str] = set()
        
    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Visit attribute access like web.click(), http.get()."""
        if isinstance(node.value, ast.Name):
            namespace = node.value.id
            # Check if it's one of our action namespaces
            if namespace in ['web', 'http', 'file', 'db', 'email']:
                self.used_namespaces.add(namespace)
        
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name) -> None:
        """Visit name references like HTML, JSON, etc."""
        # Check if it's one of our validation types
        if node.id in ['HTML', 'JSON', 'CSV', 'XML', 'YAML', 'Markdown']:
            self.used_types.add(node.id)
        # Check if it's one of our command types (needed for transformed code)
        elif node.id in ['WebCommand', 'WebActionType', 'LLMCommand', 'FileCommand']:
            self.used_types.add(node.id)
        # Check if it's one of our session functions
        elif node.id in ['session']:
            self.used_namespaces.add('session')
        
        self.generic_visit(node)
    
    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Visit subscript access like HTML[Model], JSON[Schema]."""
        if isinstance(node.value, ast.Name):
            type_name = node.value.id
            if type_name in ['HTML', 'JSON', 'CSV', 'XML', 'YAML', 'Markdown']:
                self.used_types.add(type_name)
        
        self.generic_visit(node)


def analyze_hybrid_file(code: str) -> Dict[str, Any]:
    """Analyze .hu file code and return needed imports.
    
    Args:
        code: The .hu file source code
        
    Returns:
        Dictionary with 'namespaces' and 'types' that need to be injected
    """
    try:
        tree = ast.parse(code)
        analyzer = ActionNamespaceAnalyzer()
        analyzer.visit(tree)
        
        return {
            'namespaces': analyzer.used_namespaces,
            'types': analyzer.used_types
        }
    except SyntaxError as e:
        # If AST parsing fails, inject everything as fallback
        return {
            'namespaces': {'web', 'http', 'session'},  # Default safe set
            'types': {'HTML', 'JSON', 'CSV', 'XML', 'YAML', 'Markdown'}
        }


def create_execution_globals(used_namespaces: Set[str], used_types: Set[str], lamia_instance=None) -> Dict[str, Any]:
    """Create execution globals dictionary with only needed imports.
    
    Args:
        used_namespaces: Set of namespace names to inject (web, http, etc.)
        used_types: Set of type names to inject (HTML, JSON, etc.)
        lamia_instance: The Lamia instance to use for session validation (optional)
        
    Returns:
        Dictionary ready for exec() global namespace
    """
    execution_globals = {}
    
    # Inject validation types and command types
    type_mapping = {
        'HTML': HTML,
        'JSON': JSON,
        'CSV': CSV,
        'XML': XML,
        'YAML': YAML,
        'Markdown': Markdown
    }
    
    # Add command types for transformed code
    command_mapping = {
        'WebCommand': None,
        'WebActionType': None,
        'LLMCommand': None,
        'FileCommand': None
    }
    
    # Import command types only if needed
    for cmd_type in used_types:
        if cmd_type in command_mapping:
            if cmd_type == 'WebCommand':
                from lamia.interpreter.commands import WebCommand
                command_mapping['WebCommand'] = WebCommand
            elif cmd_type == 'WebActionType':
                from lamia.interpreter.commands import WebActionType
                command_mapping['WebActionType'] = WebActionType
            elif cmd_type == 'LLMCommand':
                from lamia.interpreter.commands import LLMCommand
                command_mapping['LLMCommand'] = LLMCommand
            elif cmd_type == 'FileCommand':
                from lamia.interpreter.commands import FileCommand
                command_mapping['FileCommand'] = FileCommand
    
    for type_name in used_types:
        if type_name in type_mapping:
            execution_globals[type_name] = type_mapping[type_name]
        elif type_name in command_mapping and command_mapping[type_name] is not None:
            execution_globals[type_name] = command_mapping[type_name]
    
    # Inject action namespaces
    if 'web' in used_namespaces:
        from lamia.actions import web
        from lamia.interpreter.commands import WebCommand, WebActionType
        execution_globals['web'] = web
        execution_globals['WebCommand'] = WebCommand
        execution_globals['WebActionType'] = WebActionType
    
    if 'http' in used_namespaces:
        from lamia.actions import http
        execution_globals['http'] = http
        
    if 'file' in used_namespaces:
        from lamia.actions import file
        execution_globals['file'] = file
    
    if 'session' in used_namespaces:
        from lamia.adapters.web.session_blocks import session, SessionSkipException
        import logging
        import asyncio
        execution_globals['session'] = session
        execution_globals['SessionSkipException'] = SessionSkipException
        execution_globals['logger'] = logging.getLogger(__name__)
        execution_globals['asyncio'] = asyncio  # Needed for asyncio.run() in session validation
        
        # Add session validation support
        if lamia_instance:
            execution_globals['validate_session_result'] = create_session_validator(lamia_instance)
        else:
            # Fallback: create a validator that will raise an error if used
            def no_lamia_validator(return_type):
                raise Exception("Session validation requires a Lamia instance but none was provided")
            execution_globals['validate_session_result'] = no_lamia_validator
    
    # Future namespaces can be added here
    # if 'db' in used_namespaces:
    #     from lamia.actions import db
    #     execution_globals['db'] = db
    
    return execution_globals