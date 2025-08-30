"""Interface and implementations for parsing AI responses in selector resolution."""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ResponseParser(ABC):
    """Abstract interface for parsing AI responses in selector resolution."""
    
    @abstractmethod
    def get_full_prompt_template(self, operation_instructions: str, page_html: str, selector: str) -> str:
        """Get the complete prompt template including format instructions.
        
        Args:
            operation_instructions: Operation-specific instructions
            page_html: HTML content of the page
            selector: The natural language selector
            
        Returns:
            Complete prompt string for the AI
        """
        pass
    
    @abstractmethod
    def get_validation_prompt_template(self, operation_instructions: str, page_html: str, selector: str) -> str:
        """Get the validation prompt template (may be same as full prompt).
        
        Args:
            operation_instructions: Operation-specific instructions
            page_html: HTML content of the page  
            selector: The natural language selector
            
        Returns:
            Complete validation prompt string for the AI
        """
        pass
    
    @abstractmethod
    def parse_response(self, response: str, original_selector: str) -> 'ParseResult':
        """Parse AI response into a structured result.
        
        Args:
            response: Raw AI response text
            original_selector: Original selector for context
            
        Returns:
            ParseResult containing either a single selector or ambiguous options
        """
        pass
    
    @abstractmethod
    def is_ambiguous_response(self, response: str) -> bool:
        """Check if the response indicates ambiguity.
        
        Args:
            response: Raw AI response text
            
        Returns:
            True if response indicates multiple matches
        """
        pass


class ParseResult:
    """Result of parsing an AI response."""
    
    def __init__(self, is_ambiguous: bool, selector: Optional[str] = None, options: Optional[List[Tuple[str, str]]] = None):
        """Initialize parse result.
        
        Args:
            is_ambiguous: Whether the result is ambiguous
            selector: Single CSS selector (if not ambiguous)
            options: List of (text, selector) tuples (if ambiguous)
        """
        self.is_ambiguous = is_ambiguous
        self.selector = selector
        self.options = options or []
    
    def __repr__(self):
        if self.is_ambiguous:
            return f"ParseResult(ambiguous, {len(self.options)} options)"
        else:
            return f"ParseResult(single: {self.selector})"


class AmbiguousFormatResponseParser(ResponseParser):
    """Implementation using AMBIGUOUS format for handling multiple matches."""
    
    def get_full_prompt_template(self, operation_instructions: str, page_html: str, selector: str) -> str:
        """Get the complete prompt template including AMBIGUOUS format instructions."""
        return f"""You are a web automation expert. Given the following HTML page and a natural language description of an element, return a response in one of these formats:

{operation_instructions}

CRITICAL RULE: You MUST check for ALL elements that could match the description. If there are 2 or more possible matches, you MUST use AMBIGUOUS format. Do NOT pick just one - always report ambiguity when multiple options exist.

FORMAT 1 - Single match found (ONLY if exactly one element matches):
Return only the CSS selector, no brackets or extra text.

FORMAT 2 - Multiple ambiguous matches found (REQUIRED when 2+ elements match):
AMBIGUOUS
OPTION1: "descriptive_text_1" -> css_selector_1
OPTION2: "descriptive_text_2" -> css_selector_2
...

IMPORTANT: For AMBIGUOUS format, make the option texts DISTINCTIVE and DESCRIPTIVE so users can tell them apart. Each option text MUST be unique enough that if a user used it as a selector, it would find only ONE element. Examples:
- Instead of: "Sign in" and "Sign in" 
- Use: "Sign in with Google" and "Sign in with Apple" and "Sign in button"
- Instead of: "Submit" and "Submit"
- Use: "Submit search form" and "Submit contact form"
- Add context like: "button", "link", "with [service]", "in [location]", etc.

CRITICAL: Each option text you provide MUST be specific enough to uniquely identify ONE element on the page.

NEVER suggest the original failing selector text as one of your options. If the user's selector was "Sign in button", do NOT include "Sign in button" as an option.

Search Strategy:
1. First scan ALL buttons, links, and clickable elements
2. Check text content, aria-labels, and surrounding text
3. Count how many could reasonably match the description
4. If count >= 2, use AMBIGUOUS format immediately

HTML:
{page_html}

Natural language selector: "{selector}"

Step 1: Search for ALL elements containing words like "sign", "login", "signin", etc.
Step 2: Count potential matches for "{selector}"
Step 3: If 2+ matches found, return AMBIGUOUS format. If exactly 1 match, return selector.

Your response:"""

    def get_validation_prompt_template(self, operation_instructions: str, page_html: str, selector: str) -> str:
        """Get the validation prompt template - same as full prompt for consistency."""
        return self.get_full_prompt_template(operation_instructions, page_html, selector)
    
    def parse_response(self, response: str, original_selector: str) -> ParseResult:
        """Parse AI response using AMBIGUOUS format."""
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        
        if not lines:
            raise ValueError("Empty AI response")
        
        # Check if response indicates ambiguity
        if self.is_ambiguous_response(response):
            logger.debug("AI response indicates ambiguity, parsing options")
            
            # Parse AMBIGUOUS response format
            options = []
            for line in lines[1:]:  # Skip "AMBIGUOUS" line
                if ': "' in line and '" ->' in line:
                    # Parse: OPTION1: "exact text" -> selector
                    parts = line.split(': "', 1)
                    if len(parts) == 2:
                        text_and_selector = parts[1]
                        if '" ->' in text_and_selector:
                            text, selector = text_and_selector.split('" ->', 1)
                            options.append((text.strip(), selector.strip()))
            
            return ParseResult(is_ambiguous=True, options=options)
        
        # If not ambiguous, treat first line as the selector
        selector = lines[0]
        
        # Clean up common AI formatting issues
        if selector.startswith('"') and selector.endswith('"'):
            selector = selector[1:-1]
        
        if not selector:
            raise ValueError("AI returned empty selector")
            
        return ParseResult(is_ambiguous=False, selector=selector)
    
    def is_ambiguous_response(self, response: str) -> bool:
        """Check if response starts with AMBIGUOUS."""
        return response.strip().startswith("AMBIGUOUS")
