from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelCost:
    """Represents the cost breakdown for a model execution.
    
    Token counts are always available. Monetary costs are optional
    and will be implemented when pricing is added.
    """
    input_tokens: int
    output_tokens: int
    # TODO: Add monetary cost fields when pricing is implemented
    total_cost_usd: float = 0.0
    
    def __add__(self, other: Optional["ModelCost"]) -> "ModelCost":
        if other is None:
            return self
        return ModelCost(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_cost_usd=self.total_cost_usd + other.total_cost_usd
        )
    
    @classmethod
    def zero(cls) -> "ModelCost":
        """Create a zero-cost ModelCost."""
        return cls(input_tokens=0, output_tokens=0, total_cost_usd=0.0)
    
    @property
    def total_tokens(self) -> int:
        """Total number of tokens used."""
        return self.input_tokens + self.output_tokens
    
    def __str__(self) -> str:
        if self.total_cost_usd > 0:
            return f"${self.total_cost_usd:.6f} ({self.input_tokens} input + {self.output_tokens} output tokens)"
        return f"{self.input_tokens} input + {self.output_tokens} output tokens"
