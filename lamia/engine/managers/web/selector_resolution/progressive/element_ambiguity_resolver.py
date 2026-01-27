"""Interface for element ambiguity resolution strategies."""

from abc import ABC, abstractmethod
from typing import List, Any, Optional

from .progressive_selector_strategy import ProgressiveSelectorStrategyIntent


class ElementAmbiguityResolver(ABC):
    """
    Abstract base class for element ambiguity resolution strategies.
    
    Implementations handle cases where multiple elements match a selector
    and the system needs to determine which element(s) the user intended.
    """
    
    @abstractmethod
    async def resolve(
        self,
        description: str,
        elements: List[Any],
        intent: ProgressiveSelectorStrategyIntent,
        page_url: str,
    ) -> Optional[List[Any]]:
        """
        Attempt to resolve ambiguous element matches.
        
        Args:
            description: Original natural language description
            elements: List of matching element handles
            intent: The parsed intent from the selector strategy
            page_url: Current page URL (for caching purposes)
            
        Returns:
            List of resolved elements, or None if resolution failed/skipped
        """
        pass

