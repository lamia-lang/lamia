"""Progressive selector strategy generator for AI-powered element resolution."""

import logging
import re
from enum import Enum
from typing import List, Optional, Tuple, Set

from pydantic import BaseModel, field_validator

from lamia.validation.validators.file_validators.file_structure.json_structure_validator import JSONStructureValidator
from lamia.interpreter.commands import LLMCommand
from lamia.engine.managers.llm.llm_manager import LLMManager
from lamia.validation.base import ValidationResult

logger = logging.getLogger(__name__)

# Common HTML tags that can serve as generic fallback selectors
GENERIC_HTML_TAGS: Set[str] = {
    # Interactive elements
    "a", "button", "input", "select", "textarea", "label", "form",
    # Container elements
    "div", "span", "section", "article", "aside", "header", "footer", "main", "nav",
    # List elements
    "ul", "ol", "li", "dl", "dt", "dd",
    # Table elements
    "table", "thead", "tbody", "tfoot", "tr", "th", "td",
    # Text elements
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "code",
    # Media elements
    "img", "video", "audio", "canvas", "svg", "iframe",
    # Other common elements
    "option", "optgroup", "fieldset", "legend", "details", "summary",
}


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

    @field_validator("element_count", mode="before")
    @classmethod
    def _coerce_element_count(cls, v: str) -> str:
        if not v or not v.strip():
            return ElementCount.SINGLE.value
        return v.strip().lower()

    @field_validator("relationship", mode="before")
    @classmethod
    def _coerce_relationship(cls, v: str) -> str:
        if not v or not v.strip():
            return Relationship.NONE.value
        return v.strip().lower()

    @field_validator("strictness", mode="before")
    @classmethod
    def _coerce_strictness(cls, v: str) -> str:
        if not v or not v.strip():
            return Strictness.RELAXED.value
        return v.strip().lower()

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
    
    async def generate(
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
            raise ValueError(f"Failed to generate selectors with progressive strategy for: '{description}'")
        
        typed_result: ProgressiveSelectorStrategyModel = result.result_type  # type: ignore[assignment]

        # Validate that last selector is a generic HTML tag
        validated_selectors = self._ensure_generic_tag_suffix(typed_result.selectors)

        return typed_result.intent, validated_selectors
    
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

DO NOT include any of these failed selectors in your response. Generate completely different selectors. Also, think why they are failed and exlcude new selectors that are likely to fail for the same reason.

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

    def _ensure_generic_tag_suffix(self, selectors: List[str]) -> List[str]:
        """
        Ensure the selector list ends with a generic HTML tag selector.
        
        If the last selector is not a pure HTML tag (e.g., "button", "div", "a"),
        extract the tag from the last selector and append it.
        
        Args:
            selectors: List of selectors from LLM
            
        Returns:
            List of selectors guaranteed to end with a generic tag
        """
        if not selectors:
            return selectors
        
        last_selector = selectors[-1]
        
        # Check if already a generic tag
        if self._is_generic_tag_selector(last_selector):
            logger.debug(f"Last selector '{last_selector}' is already a generic tag")
            return selectors
        
        # Try to extract the tag from the last selector
        extracted_tag = self._extract_tag_from_selector(last_selector)
        
        if extracted_tag and extracted_tag in GENERIC_HTML_TAGS:
            logger.info(f"Appending generic tag '{extracted_tag}' extracted from '{last_selector}'")
            return selectors + [extracted_tag]
        
        # If we couldn't extract a valid tag, log a warning
        logger.warning(
            f"Could not extract a generic HTML tag from selector '{last_selector}'. "
            "Resolution may fail if more specific selectors don't match."
        )
        return selectors
    
    def _is_generic_tag_selector(self, selector: str) -> bool:
        """
        Check if a selector is a pure generic HTML tag (no classes, IDs, attributes).
        
        Args:
            selector: CSS selector or XPath
            
        Returns:
            True if selector is just an HTML tag name
        """
        selector = selector.strip().lower()
        
        # For XPath like "//button" or "//div" (must be exactly //tag, nothing more)
        if selector.startswith("//"):
            # Must be exactly "//tag" with no attributes, predicates, or further path
            xpath_match = re.match(r'^//([a-z][a-z0-9]*)$', selector)
            if xpath_match:
                return xpath_match.group(1) in GENERIC_HTML_TAGS
            return False
        
        # For CSS, must be exactly a tag name (no ., #, [, :, etc.)
        if re.match(r'^[a-z][a-z0-9]*$', selector):
            return selector in GENERIC_HTML_TAGS
        
        return False
    
    def _extract_tag_from_selector(self, selector: str) -> Optional[str]:
        """
        Extract the HTML tag from a CSS selector or XPath.
        
        Args:
            selector: CSS selector or XPath expression
            
        Returns:
            Extracted tag name or None if not found
        """
        selector = selector.strip()
        
        # XPath: //tag, //tag[@attr], //tag[contains(...)]
        xpath_match = re.match(r'^//([a-zA-Z][a-zA-Z0-9]*)', selector)
        if xpath_match:
            return xpath_match.group(1).lower()
        
        # CSS: tag.class, tag#id, tag[attr], tag:pseudo
        css_match = re.match(r'^([a-zA-Z][a-zA-Z0-9]*)', selector)
        if css_match:
            return css_match.group(1).lower()
        
        return None