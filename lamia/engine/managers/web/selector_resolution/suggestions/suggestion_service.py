"""AI-powered selector suggestion service for failed selectors."""

import logging
from typing import Optional, List, Tuple
from lamia.interpreter.commands import LLMCommand

logger = logging.getLogger(__name__)


class SelectorSuggestionService:
    """Provides AI-powered suggestions when selectors fail to find elements."""
    
    def __init__(self, llm_manager, get_page_html_func):
        """Initialize the selector suggestion service.
        
        Args:
            llm_manager: LLM manager for AI-powered suggestions
            get_page_html_func: Function to get current page HTML
        """
        self.llm_manager = llm_manager
        self.get_page_html = get_page_html_func
    
    async def suggest_alternative_selectors(
        self,
        failed_selector: str,
        operation_type: str,
        max_suggestions: int = 3
    ) -> List[Tuple[str, str]]:
        """Generate alternative selector suggestions using AI.
        
        Args:
            failed_selector: The selector that failed to find elements
            operation_type: Type of operation (click, type, etc.)
            max_suggestions: Maximum number of suggestions to return
            
        Returns:
            List of (description, selector) tuples with AI suggestions
        """
        logger.info(f"Generating AI suggestions for failed selector: '{failed_selector}'")
        
        try:
            # Get current page HTML
            page_html = await self.get_page_html()
            
            # Create prompt for AI
            prompt = self._create_suggestion_prompt(
                failed_selector=failed_selector,
                page_html=page_html,
                operation_type=operation_type,
                max_suggestions=max_suggestions
            )
            
            # Execute LLM command
            llm_command = LLMCommand(prompt=prompt)
            result = await self.llm_manager.execute(llm_command)
            response = result.validated_text.strip()
            
            if not response:
                logger.warning("LLM returned empty response for selector suggestions")
                return []
            
            # Parse AI response into suggestions
            suggestions = self._parse_suggestions(response, failed_selector)
            
            logger.info(f"Generated {len(suggestions)} alternative selector suggestions")
            return suggestions[:max_suggestions]
            
        except Exception as e:
            logger.error(f"Failed to generate selector suggestions: {e}")
            return []
    
    def _create_suggestion_prompt(
        self,
        failed_selector: str,
        page_html: str,
        operation_type: str,
        max_suggestions: int
    ) -> str:
        """Create prompt for AI to suggest alternative selectors.
        
        Args:
            failed_selector: The selector that failed
            page_html: Current page HTML
            operation_type: Type of operation being performed
            max_suggestions: Maximum number of suggestions
            
        Returns:
            Prompt string for AI
        """
        operation_desc = self._get_operation_description(operation_type)
        
        prompt = f"""The following CSS selector FAILED to find any elements on the page:
FAILED SELECTOR: {failed_selector}

OPERATION: {operation_desc}

PAGE HTML (compact skeleton):
{page_html}

Your task is to analyze the HTML and suggest up to {max_suggestions} alternative CSS selectors that might work.

Look for:
1. Elements with similar attributes, classes, or IDs
2. Elements that match the likely intent of the failed selector
3. Elements appropriate for the operation type ({operation_type})
4. Common selector issues (typos, outdated classes, changed structure)

Return your suggestions in this exact format:
SUGGESTION 1: "Description of what this selector targets" -> css_selector_here
SUGGESTION 2: "Description of what this selector targets" -> css_selector_here
SUGGESTION 3: "Description of what this selector targets" -> css_selector_here

Each suggestion should:
- Start with "SUGGESTION N:" where N is 1, 2, 3, etc.
- Have a description in quotes explaining what element it targets
- Follow with " -> " and then the CSS selector
- Be on a separate line

Example:
SUGGESTION 1: "Primary login button" -> button.btn-primary[type="submit"]
SUGGESTION 2: "Login button by text" -> button:has-text("Log in")

Provide your suggestions now:"""
        
        return prompt
    
    def _get_operation_description(self, operation_type: str) -> str:
        """Get human-readable description of operation type."""
        descriptions = {
            "click": "Finding a clickable element (button, link, etc.)",
            "type_text": "Finding an input field to type text into",
            "select": "Finding a dropdown/select element",
            "hover": "Finding an element to hover over",
            "wait_for": "Finding an element that should become visible",
            "get_text": "Finding an element to extract text from",
            "is_visible": "Finding an element to check visibility",
            "is_enabled": "Finding an element to check if enabled",
        }
        return descriptions.get(operation_type, "Finding an element")
    
    def _parse_suggestions(
        self,
        response: str,
        failed_selector: str
    ) -> List[Tuple[str, str]]:
        """Parse AI response into list of suggestions.
        
        Args:
            response: AI response text
            failed_selector: The original failed selector (to filter duplicates)
            
        Returns:
            List of (description, selector) tuples
        """
        suggestions = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line.startswith('SUGGESTION'):
                continue
            
            # Parse format: SUGGESTION N: "description" -> selector
            try:
                # Split on first " -> " to separate description from selector
                if ' -> ' not in line:
                    continue
                
                desc_part, selector = line.split(' -> ', 1)
                
                # Extract description from quotes
                if '"' in desc_part:
                    # Find text within quotes
                    start_quote = desc_part.index('"')
                    end_quote = desc_part.rindex('"')
                    description = desc_part[start_quote+1:end_quote]
                else:
                    # Fallback: use everything after the colon
                    description = desc_part.split(':', 1)[1].strip()
                
                selector = selector.strip()
                
                # Filter out if it's the same as the failed selector
                if selector.lower() != failed_selector.lower():
                    suggestions.append((description, selector))
                    logger.debug(f"Parsed suggestion: '{description}' -> {selector}")
                else:
                    logger.debug(f"Filtered out duplicate suggestion: {selector}")
                    
            except Exception as e:
                logger.debug(f"Failed to parse suggestion line '{line}': {e}")
                continue
        
        return suggestions

