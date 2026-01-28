"""Strategy-based selector resolution system.

# TODO: This package is highly coupled with Selenium, many of the js functions in the execute_script functions are specific to Selenium. We need to fix that.

This package implements a strategy-based approach to finding elements:
1. Generate multiple selector strategies from natural language
2. Try each strategy progressively (specific to generic)
3. Validate element relationships (siblings, common ancestors)
4. Handle ambiguity with LLM-based and optional human-assisted selection

Key benefit: No HTML sent to LLM (significant cost reduction).
"""

from .progressive_selector_strategy import ProgressiveSelectorStrategy
from .strategy_resolver import ProgressiveSelectorResolver
from .relationship_validator import ElementRelationshipValidator
from .element_ambiguity_resolver import ElementAmbiguityResolver
from .llm_ambiguity_resolver import LLMAmbiguityResolver
from .human_assisted_ambiguity_resolver import HumanAssistedAmbiguityResolver

__all__ = [
    'ProgressiveSelectorStrategy',
    'ProgressiveSelectorResolver',
    'ElementRelationshipValidator',
    'ElementAmbiguityResolver',
    'LLMAmbiguityResolver',
    'HumanAssistedAmbiguityResolver',
]
