from lamia.engine.engine import LamiaEngine
import asyncio
from typing import Any, Optional, List, Dict, Union
import yaml
import logging
import ast
from lamia.engine.llm.llm_manager import MissingAPIKeysError
import weakref

logger = logging.getLogger(__name__)

class Lamia:
    """
    Main user interface for Lamia LLM engine.
    
    This class provides a simple interface for LLM interactions with automatic
    initialization and cleanup.
    
    Args:
        *models: Model names (e.g., 'openai', 'ollama', ...)
        api_keys: Optional dict of API keys (e.g., {'openai': 'sk-...'}).
        validators: Optional list of functions or Lamia validator instances.
        config: Optional config dict or path. If provided, overrides *models.
    """
    
    def __init__(
        self, 
        *models: str, 
        api_keys: Optional[dict] = None, 
        validators: Optional[List[Any]] = None, 
        config: Optional[Union[str, Dict[str, Any]]] = None
    ):
        # Configuration
        self._config_dict = self._build_config(models, api_keys, validators, config)
        
        # Store validators for manual validation
        self._validators = validators if validators is not None else []
        
        # Initialize engine
        self._engine = LamiaEngine(self._config_dict)
        self._initialized = False
        
        # Register a finalizer that makes sure resources are released even if
        # this object becomes part of a reference cycle. We keep a weak
        # reference to *self* so that the Lamia instance can still be
        # garbage-collected. The callback is idempotent, so calling it
        # multiple times (from __del__ or elsewhere) is safe.
        self._finalizer = weakref.finalize(self, Lamia._cleanup, weakref.ref(self))
        
        logger.info("Lamia instance created")

    def _build_config(
        self, 
        models: tuple, 
        api_keys: Optional[dict], 
        validators: Optional[List[Any]], 
        config: Optional[Union[str, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Build configuration from parameters"""
        if config is not None:
            if isinstance(config, str):
                with open(config, 'r') as f:
                    return yaml.safe_load(f)
            elif isinstance(config, dict):
                return config
            else:
                raise ValueError("config must be a dict or a file path")
        
        # Build config from models/api_keys/validators
        config_dict = {
            'default_model': models[0] if models else 'ollama',
            'models': {},
            'validation': {
                'enabled': True,
                'max_retries': 1,
                'fallback_models': list(models[1:]) if len(models) > 1 else [],
                'validators': [{'type': 'html'}] if not validators else validators
            }
        }
        
        # Add model configs
        for model in models:
            config_dict['models'][model] = {'enabled': True}
        
        if api_keys:
            config_dict['api_keys'] = api_keys
            
        return config_dict

    async def _ensure_initialized(self):
        """Ensure engine is initialized"""
        if not self._initialized:
            await self._engine.start()
            self._initialized = True

    def is_python_code(self, code: str) -> bool:
        """
        Check if the input string is likely Python code.
        
        Args:
            code: The input string to check
            
        Returns:
            bool: True if the string is likely Python code
        """
        try:
            ast.parse(code, mode='eval')
            return True
        except:
            pass
        
        try:
            ast.parse(code, mode='exec')
            return True
        except:
            return False

    def run_python_code(self, code: str, mode: str = 'interactive', show_banner: bool = True) -> tuple[bool, Any]:
        """
        Execute Python code or expression.
        
        Args:
            code: The Python code to execute
            mode: 'interactive' or 'file' - controls output behavior
            show_banner: Whether to show result banner
            
        Returns:
            tuple: (success: bool, result: Any)
        """
        # Try to evaluate as expression first
        try:
            expr_ast = ast.parse(code, mode='eval')
            result = eval(compile(expr_ast, '<string>', mode='eval'))
            return True, result
        except:
            pass
        
        # Try to execute as code
        try:
            code_ast = ast.parse(code, mode='exec')
            local_vars = {}
            exec(compile(code_ast, '<string>', mode='exec'), {}, local_vars)
            
            # In interactive mode, return the result of the last expression if present
            if mode == 'interactive' and code_ast.body and isinstance(code_ast.body[-1], ast.Expr):
                last_expr = code_ast.body[-1]
                # Don't return result if the last expression is a print() call
                if not (isinstance(last_expr.value, ast.Call) and getattr(last_expr.value.func, 'id', None) == 'print'):
                    result = eval(compile(ast.Expression(last_expr.value), '<string>', mode='eval'), {}, local_vars)
                    return True, result
            
            return True, None
        except Exception as e:
            return False, e

    async def run_async(
        self, 
        prompt: str, 
        *, 
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None, 
        skip_validators: bool = False
    ) -> str:
        """
        Generate a response, trying Python code first, then LLM.
        
        Args:
            prompt: The input prompt
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            skip_validators: Whether to skip manual validators
            
        Returns:
            str: Generated response text
            
        Raises:
            RuntimeError: If engine fails to start
            MissingAPIKeysError: If API keys are missing
            ValueError: If validator fails
        """
        # Check if this is Python code
        success, result = self.run_python_code(prompt, mode='interactive', show_banner=False)
        if success:
            return str(result) if result is not None else ""
        
        # Ensure engine is initialized
        await self._ensure_initialized()
        
        # Generate LLM response
        response = await self._engine.execute(
            'llm',
            prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Apply manual validators if not skipped
        if not skip_validators and self._validators:
            text = response.text
            for validator in self._validators:
                try:
                    # Try instance method first
                    if hasattr(validator, 'validate') and callable(getattr(validator, 'validate')):
                        valid = validator.validate(text)
                    else:
                        # Fall back to callable
                        valid = validator(text)
                    
                    if not valid:
                        validator_name = getattr(validator, '__name__', validator.__class__.__name__)
                        raise ValueError(f"Validator {validator_name} failed for response: {text}")
                except Exception as e:
                    if isinstance(e, ValueError):
                        raise  # Re-raise validation errors
                    # Log other errors but continue
                    logger.warning(f"Validator error: {e}")
        
        return response.text

    def get_validation_stats(self) -> Optional[Any]:
        """Get validation statistics if the engine is initialized."""
        if self._initialized:
            return self._engine.get_validation_stats()
        return None
    
    def get_recent_validation_results(self, limit: Optional[int] = None) -> Optional[List[Any]]:
        """Get recent validation results if the engine is initialized."""
        if self._initialized:
            return self._engine.get_recent_validation_results(limit)
        return None

    def run(
        self,
        prompt: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        skip_validators: bool = False,
    ) -> str:
        """
        Synchronous helper around run_async.

        Note: cannot be called from inside an active event-loop.
        """
        try:
            return asyncio.run(
                self.run_async(
                    prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    skip_validators=skip_validators,
                )
            )
        except RuntimeError as e:
            # Happens only if there is already a running event loop
            if "running event loop" in str(e):
                raise RuntimeError(
                    "run() cannot be used inside an async context. "
                    "Use 'await lamia.run_async(...)' instead."
                ) from e
            raise

    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_initialized()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._initialized:
            await self._engine.stop()

    def __del__(self):
        """Destructor – ensure engine is stopped.

        Delegates to the same weakref finalizer used for cyclic-GC safe
        cleanup. The finalizer returns ``True`` if it had not yet run.
        """
        try:
            self._finalizer()
        except Exception:
            # Never allow exceptions to propagate from a destructor – they
            # would be ignored and generate warnings.
            pass

    @staticmethod
    def _cleanup(self_ref):
        """Finalizer callback that stops the underlying engine.

        It attempts to shut down the engine in the most appropriate way
        depending on whether an event loop is running. This method is
        safe to call multiple times.
        """
        lamia = self_ref()
        if lamia is None:
            return  # Object already gone

        if not getattr(lamia, "_initialized", False):
            return  # Engine was never started – nothing to do

        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # Schedule the coroutine in the running loop from whichever
                # thread we are in.
                loop.call_soon_threadsafe(lambda: asyncio.create_task(lamia._engine.stop()))
                return
        except RuntimeError:
            # No running event loop – we'll try a synchronous shutdown below.
            pass

        # Fall back to running the coroutine in a new temporary loop.
        try:
            asyncio.run(lamia._engine.stop())
        except Exception:
            # Interpreter shutdown may have torn down asyncio – ignore errors.
            logger.debug("Failed to stop engine during finalization", exc_info=True)