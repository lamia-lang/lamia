"""Progressive selector strategy generator for AI-powered element resolution."""

import logging
from enum import Enum
from typing import List, Optional, Tuple, Type

from pydantic import BaseModel

from lamia.validation.validators.file_validators.file_structure.json_structure_validator import JSONStructureValidator
from lamia.interpreter.commands import LLMCommand
from lamia.engine.managers.llm.llm_manager import LLMManager
from lamia.validation.base import ValidationResult

logger = logging.getLogger(__name__)


class ElementCount(str, Enum):
    """Enum for element count intent."""
    SINGLE = "single"
    MULTIPLE = "multiple"


class Relationship(str, Enum):
    """Enum for element relationship type."""
    NONE = "none"
    GROUPED = "grouped"
    SIBLINGS = "siblings"


class Strictness(str, Enum):
    """Enum for selector strictness level."""
    STRICT = "strict"
    RELAXED = "relaxed"


class ProgressiveSelectorStrategyIntent(BaseModel):
    element_count: ElementCount
    relationship: Relationship
    strictness: Strictness

class ProgressiveSelectorStrategyModel(BaseModel):
    intent: ProgressiveSelectorStrategyIntent
    selectors: List[str]


class ProgressiveSelectorStrategy:
    """
    Generates progressive selector strategies from natural language descriptions.
    
    Produces a list of selectors ordered from most specific to most generic,
    with validation rules for each strategy.
    """
    
    def __init__(self, llm_manager: LLMManager):
        """Initialize the strategy generator.
        
        Args:
            llm_manager: LLM manager for generating strategies
        """
        self.llm_manager = llm_manager
        self.progressive_selector_json_validator = JSONStructureValidator(model=ProgressiveSelectorStrategyModel)
    
    async def generate_strategies(
        self, 
        description: str,
        failed_selectors: Optional[List[str]] = None
    ) -> Tuple[ProgressiveSelectorStrategyIntent, List[str]]:
        """
        Generate progressive selector strategies using LLM.
        
        Args:
            description: Natural language description of element(s) to find
            failed_selectors: List of selectors that have already failed (to avoid regenerating them)
            
        Returns:
            Tuple of (intent, selectors) where:
            - intent: ProgressiveSelectorStrategyIntent with element_count, relationship, strictness
            - selectors: List of CSS/XPath selectors to try
        """
        logger.info(f"Generating progressive strategies for: '{description}'")
        
        # Create prompt
        prompt = self._create_strategy_prompt(description, failed_selectors)
        
        # Execute LLM command
        llm_command = LLMCommand(prompt=prompt)
        result: ValidationResult = await self.llm_manager.execute(llm_command, self.progressive_selector_json_validator)
        
        if not result.is_valid:
            raise ValueError(f"Failed to generate progressive strategies for: '{description}'")
        
        typed_result: ProgressiveSelectorStrategyModel = result.result_type  # type: ignore[assignment]

        return typed_result.intent, typed_result.selectors
    
    def _create_strategy_prompt(self, description: str, failed_selectors: Optional[List[str]] = None) -> str:
        """Create LLM prompt for strategy generation.
        
        Args:
            description: Natural language description
            failed_selectors: List of selectors that have already failed
            
        Returns:
            Formatted prompt string
        """
        failed_selectors_text = ""
        if failed_selectors:
            failed_selectors_text = f"""
IMPORTANT: The following selectors have already been tried and FAILED to find any elements:
{failed_selectors}

DO NOT include any of these failed selectors in your response. Generate completely different selectors.

"""
        
        return f"""Analyze this element description and generate progressive CSS/XPath selectors:

Description: "{description}"
{failed_selectors_text}
STEP 1 - ANALYZE INTENT:
First, analyze the description to determine:
- element_count: Is the user looking for "single" or "multiple" elements?
  - Look for plural nouns (cards, buttons, items, fields, inputs, links, rows, etc.)
  - Look for quantifiers (all, many, several, each, every, both, two, three, etc.)
  - If singular noun or "a/the + singular"
- relationship: How are elements related?
  - "grouped" if words like: grouped, together, pair, combo, associated
  - "siblings" if words like: siblings, adjacent, next to, beside
  - "none" otherwise
  NOTE: grouped means they under a common container and can be in different levels, siblings means they are direct children of the same parent or siblings in the same level of the DOM tree.
- strictness: Should selectors be "strict" or "relaxed"?
  - "strict" when the user says "exactly", "only", "precisely", or provides a unique identifier
  - "relaxed" otherwise

STEP 2 - GENERATE POSSIBLE SELECTORS:
Generate 3-5 possible selectors ordered from MOST SPECIFIC to MOST GENERIC up until the suitable HTML tags.
Each selector should try different approaches (text content, attributes, structure, etc.).

STRATEGY RULES:
- Start with very specific selectors (exact text, IDs, specific classes)
- Progress to moderately specific (partial text matches, role attributes)  
- Continue with generic selectors (element types, broad attributes)
- End with tags that will be suitable for the HTML tags.

- For multi-element queries, set validation.relationship to "common_ancestor"
- Use "exactly_N" for count only if description says "exactly", "only", or specifies a number
- Default to "at_least_1" for count unless specified
- For text content matching, use XPath: //element[contains(text(), 'text')] NOT element:contains('text')
- For CSS attribute matching, use: [attribute*='value' i] for case-insensitive partial matches
- Mix XPath and CSS selectors for better coverage

Now analyze and generate for: "{description}"

Return ONLY the JSON object, no explanation:"""