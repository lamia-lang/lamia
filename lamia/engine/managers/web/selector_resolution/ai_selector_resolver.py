"""AI-powered selector resolution service."""

import logging
from typing import Optional
from lamia.interpreter.commands import LLMCommand
from .selector_parser import SelectorType
from .selector_correctness_validator import SelectorCorrectnessValidator

logger = logging.getLogger(__name__)


class AISelectorResolver:
    """Resolves invalid or natural language selectors using AI model chain."""
    
    def __init__(self, llm_manager):
        """Initialize the AI selector resolver.
        
        Args:
            llm_manager: LLM manager instance for making AI queries
        """
        self.llm_manager = llm_manager
        self.validator = SelectorCorrectnessValidator()
    
    async def resolve(self, selector: str, selector_type: SelectorType, page_context: Optional[str] = None) -> str:
        """Resolve a selector using AI.
        
        Args:
            selector: The original selector that needs resolution
            selector_type: Classification of the selector type
            page_context: Optional HTML content for context (only used for natural language)
            
        Returns:
            A resolved CSS selector string
        """
        logger.info(f"Resolving selector '{selector}' using AI (type: {selector_type.value})")
        
        if selector_type == SelectorType.INVALID_CSS:
            prompt = self._create_fix_css_prompt(selector)
        elif selector_type == SelectorType.INVALID_XPATH:
            prompt = self._create_fix_xpath_prompt(selector)
        elif selector_type == SelectorType.NATURAL_LANGUAGE:
            prompt = self._create_natural_language_prompt(selector, page_context)
        else:
            raise ValueError(f"Unsupported selector type: {selector_type}")
        
        # Execute LLM command with validator
        command = LLMCommand(prompt=prompt)
        result = await self.llm_manager.execute(command, self.validator)
        
        if not result.is_valid:
            raise ValueError(f"AI failed to generate valid selector: {result.validation_error}")
        
        resolved = result.parsed_content
        logger.info(f"Resolved selector: '{selector}' → '{resolved}'")
        return resolved
    
    def _create_fix_css_prompt(self, selector: str) -> str:
        """Create prompt for fixing invalid CSS selector."""
        return f"""Fix this invalid CSS selector to make it syntactically correct:

Invalid CSS selector: {selector}

Return only the corrected CSS selector, nothing else. The selector should:
1. Be valid CSS syntax
2. Preserve the original intent as much as possible
3. Be a single selector (not multiple selectors)

Corrected CSS selector:"""
    
    def _create_fix_xpath_prompt(self, selector: str) -> str:
        """Create prompt for fixing invalid XPath expression."""
        return f"""Fix this invalid XPath expression to make it syntactically correct:

Invalid XPath: {selector}

Return only the corrected XPath expression, nothing else. The expression should:
1. Be valid XPath syntax
2. Preserve the original intent as much as possible
3. Be a single XPath expression

Corrected XPath expression:"""
    
    def _create_natural_language_prompt(self, selector: str, page_context: Optional[str] = None) -> str:
        """Create prompt for resolving natural language description."""
        if page_context:
            return f"""Find a CSS selector for this description on the given HTML page:

Description: {selector}

HTML content:
{page_context}

Return only a single CSS selector that best matches the description, nothing else. The selector should:
1. Be valid CSS syntax
2. Uniquely identify the element described
3. Be as specific as necessary but not overly complex

CSS selector:"""
        else:
            return f"""Convert this natural language description to a CSS selector:

Description: {selector}

Return only a single CSS selector that best matches the description, nothing else. The selector should:
1. Be valid CSS syntax
2. Be a reasonable interpretation of the description
3. Use common patterns for the described element type

CSS selector:"""