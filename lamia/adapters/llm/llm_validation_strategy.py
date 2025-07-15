from ...engine.interfaces import ValidationStrategy

class LLMValidationStrategy(ValidationStrategy):
    """Handles LLM validation logic."""

    def get_initial_hints(self) -> str:
        """Get combined initial hints from all validators."""
        hints = [v.initial_hint for v in self.validators if hasattr(v, 'initial_hint')]
        return "\n".join(hints) 