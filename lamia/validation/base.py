import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass
from lamia.interpreter.command_types import CommandType
from lamia.engine.validation_manager import ValidationStatsTracker

@dataclass
class TrackingContext:
    """Generic context for tracking execution across different domains."""
    
    data_provider_name: str  # e.g., "openai:gpt-4o", "selenium", "local_fs"
    command_type: CommandType
    metadata: Optional[Dict[str, Union[str, int, float, bool]]] = None  # Domain-specific additional info

@dataclass
class ValidationResult:
    """Result of a validation check.
    
    Attributes:
        is_valid: Whether the response is valid.
        error_message: Error message if invalid.
        hint: Optional hint for fixing the response.
        raw_text: The original input text to the validator (e.g., LLM output with extra talking).
        validated_text: The valid, extracted part of the response (e.g., document without LLM talking).
        typed_result: The validated and resolved type (e.g., parsed Pydantic model or atomic type value).
        info_loss: Optional dict or structure describing info-losing type conversions (e.g., float->int truncation).
        execution_context: Context information about how this result was generated.
    """
    is_valid: bool
    error_message: Optional[str] = None
    hint: Optional[str] = None
    raw_text: Optional[str] = None
    validated_text: Optional[str] = None
    typed_result: Optional[Any] = None
    info_loss: Optional[dict] = None
    execution_context: Optional[TrackingContext] = None

class BaseValidator(ABC):
    """Base class for response validators.
    
    Subclasses should implement both validate_strict (forgiving) and validate_permissive (strict) methods.
    The __call__ method dispatches to the correct method based on the strict flag.
    """
    def __init__(self, strict: bool = True, generate_hints: bool = False, validation_manager: Optional[ValidationStatsTracker] = None):
        self.strict = strict
        self.generate_hints = generate_hints
        self.validation_manager = validation_manager
        cls = self.__class__
        has_validate = cls.validate is not BaseValidator.validate
        has_strict = cls.validate_strict is not BaseValidator.validate_strict
        has_perm = cls.validate_permissive is not BaseValidator.validate_permissive
        if has_validate and (has_strict or has_perm):
            raise TypeError("Implement either validate() OR validate_strict/validate_permissive, not both.")
        if not (has_validate or (has_strict and has_perm)):
            raise TypeError("Must implement either validate() or both validate_strict and validate_permissive.")

    _FENCE_RE = re.compile(r'^```\w*\s*\n?([\s\S]*?)\n?\s*```\s*$')

    @staticmethod
    def strip_markdown_fences(text: str) -> str:
        """Strip markdown code fences (```lang ... ```) that LLMs commonly wrap around responses."""
        m = BaseValidator._FENCE_RE.match(text)
        return m.group(1).strip() if m else text

    async def validate(self, response: str, execution_context: Optional[TrackingContext] = None, **kwargs) -> ValidationResult:
        """Validate response and track intermediate attempts if validation_manager is available.
        
        Args:
            response: The response text to validate
            execution_context: Optional context for tracking (provider name, command type, metadata)
            **kwargs: Additional validation parameters
        """
        cls = self.__class__
        # If validate is overridden, use it
        if cls.validate is not BaseValidator.validate:
            raise NotImplementedError("BaseValidator.validate should not be called directly if overridden.")
        # Otherwise, dispatch to strict/permissive
        if self.strict:
            result = await self.validate_strict(response, **kwargs)
        else:
            result = await self.validate_permissive(response, **kwargs)

        result.raw_text = self.strip_markdown_fences(response.strip()) if isinstance(response, str) else response
        result.execution_context = execution_context
        
        # Track intermediate validation attempt if manager is available
        if self.validation_manager and execution_context:
            self.validation_manager.record_intermediate_validation_attempt(
                provider_name=execution_context.data_provider_name,
                is_successful=result.is_valid
            )
        
        return result

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        raise NotImplementedError("Implement validate_strict for context-aware validators.")

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        raise NotImplementedError("Implement validate_permissive for context-aware validators.")

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the validator for configuration."""
        pass

    @property
    @abstractmethod
    def initial_hint(self) -> str:
        """Initial hint for the LLM prompt, to be aggregated if multiple validators are used."""
        pass

    def get_retry_hint(self, error: Optional[Exception] = None, retry_hint: Optional[str] = None) -> str:        
        if not self.generate_hints:
            return None

        parts = []
        
        if error:
            # Collect all exception messages in the chain
            error_messages = []
            current_error = error
            while current_error is not None:
                error_msg = str(current_error)
                if error_msg:
                    error_messages.append(error_msg)
                # Follow the chain: __cause__ (explicit chaining) or __context__ (implicit chaining)
                current_error = current_error.__cause__ or current_error.__context__
            
            if error_messages:
                # Join all error messages with " -> " to show the chain
                full_error_message = " caused by ".join(error_messages)
                parts.append(f"Error: {full_error_message}")
        
        if retry_hint:
            parts.append(retry_hint)
        
        parts.append(self.initial_hint)
        
        return '\n\n'.join(parts)