"""Encoding validation wrapper for the LLM retry loop.

Decorates any content validator with an encoding post-check so the model
can self-correct when it produces characters outside the target encoding.
Zero overhead for the 97%+ of calls that use UTF-8 — the wrapper is only
applied when encoding != utf-8.
"""

from typing import Optional

from lamia.validation.base import BaseValidator, ValidationResult, TrackingContext


class EncodingValidatorWrapper(BaseValidator):
    """Decorates a content validator with an encoding post-check.

    After the inner validator accepts content (format is valid), this wrapper
    tries ``text.encode(target_encoding)``.  On failure the retry loop gets
    a hint telling the model which character was rejected and why.
    """

    def __init__(self, inner: BaseValidator, encoding: str):
        self._inner = inner
        self._encoding = encoding
        # super().__init__ must run AFTER _inner is set because the property
        # setters below delegate to _inner.
        super().__init__(
            strict=inner.strict,
            generate_hints=inner.generate_hints,
            validation_manager=inner.validation_manager,
        )

    async def validate(
        self,
        response: str,
        execution_context: Optional[TrackingContext] = None,
        **kwargs,
    ) -> ValidationResult:
        result = await self._inner.validate(response, execution_context=execution_context, **kwargs)
        if not result.is_valid:
            return result
        text = result.validated_text or response
        try:
            text.encode(self._encoding)
        except UnicodeEncodeError as e:
            char = text[e.start]
            return ValidationResult(
                is_valid=False,
                error_message=(
                    f"Response contains '{char}' (U+{ord(char):04X}) "
                    f"not encodable in {self._encoding}"
                ),
                hint=(
                    f"Rewrite using only {self._encoding}-safe characters. "
                    f"Replace '{char}' with a plain equivalent."
                ),
            )
        return result

    @property
    def name(self) -> str:
        return f"encoding({self._encoding}):{self._inner.name}"

    @property
    def initial_hint(self) -> str:
        return self._inner.initial_hint

    @property
    def strict(self) -> bool:
        return self._inner.strict

    @strict.setter
    def strict(self, value: bool) -> None:
        self._inner.strict = value

    @property
    def generate_hints(self) -> bool:
        return self._inner.generate_hints

    @generate_hints.setter
    def generate_hints(self, value: bool) -> None:
        self._inner.generate_hints = value

    @property
    def validation_manager(self):
        return self._inner.validation_manager

    @validation_manager.setter
    def validation_manager(self, value) -> None:
        self._inner.validation_manager = value

    def prepare_content_for_write(self, existing_content: str, new_content: str) -> str:
        return self._inner.prepare_content_for_write(existing_content, new_content)

    def get_retry_hint(self, error=None, retry_hint=None) -> str:
        return self._inner.get_retry_hint(error=error, retry_hint=retry_hint)
