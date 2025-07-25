from dataclasses import dataclass

@dataclass
class ModelCost:
    """Represents the cost breakdown for a model execution."""
    input_tokens: int
    output_tokens: int 
    total_cost_usd: float
    
    def __add__(self, other):
        if other is None:
            return self
        return ModelCost(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_cost_usd=self.total_cost_usd + other.total_cost_usd
        )
    
    def __str__(self):
        return f"${self.total_cost_usd:.6f} ({self.input_tokens} input + {self.output_tokens} output tokens)"