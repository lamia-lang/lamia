from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass
import inspect

@dataclass
class ValidationResult:
    """Result of a validation check.
    
    Attributes:
        is_valid: Whether the response is valid.
        error_message: Error message if invalid.
        hint: Optional hint for fixing the response.
        raw_text: The original input text to the validator (e.g., LLM output with extra talking).
        validated_text: The valid, extracted part of the response (e.g., document without LLM talking).
        result_type: The validated and resolved type (e.g., parsed Pydantic model or atomic type value).
        info_loss: Optional dict or structure describing info-losing type conversions (e.g., float->int truncation).
    """
    is_valid: bool
    error_message: Optional[str] = None
    hint: Optional[str] = None
    raw_text: Optional[str] = None
    validated_text: Optional[str] = None
    result_type: Optional[Any] = None
    info_loss: Optional[dict] = None

class BaseValidator(ABC):
    """Base class for response validators.
    
    Subclasses should implement both validate_strict (forgiving) and validate_permissive (strict) methods.
    The __call__ method dispatches to the correct method based on the strict flag.
    """
    def __init__(self, strict: bool = True, generate_hints: bool = False):
        self.strict = strict
        self.generate_hints = generate_hints
        cls = self.__class__
        has_validate = cls.validate is not BaseValidator.validate
        has_strict = cls.validate_strict is not BaseValidator.validate_strict
        has_perm = cls.validate_permissive is not BaseValidator.validate_permissive
        if has_validate and (has_strict or has_perm):
            raise TypeError("Implement either validate() OR validate_strict/validate_permissive, not both.")
        if not (has_validate or (has_strict and has_perm)):
            raise TypeError("Must implement either validate() or both validate_strict and validate_permissive.")

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        cls = self.__class__
        # If validate is overridden, use it
        if cls.validate is not BaseValidator.validate:
            raise NotImplementedError("BaseValidator.validate should not be called directly if overridden.")
        # Otherwise, dispatch to strict/permissive
        if self.strict:
            result = await self.validate_strict(response, **kwargs)
        else:
            result = await self.validate_permissive(response, **kwargs)

        result.raw_text = response
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

    def get_reply_hint(self, reply_hint: Optional[str] = None, error: Optional[str] = None) -> Optional[str]:
        """Generate a reply hint when validation fails. Can be extended later for universal format."""
        if self.generate_hints:
            reply_hint = ""
            if reply_hint:
                reply_hint += f"{reply_hint}\n\n"
            reply_hint += self.initial_hint
            return reply_hint
        return None 