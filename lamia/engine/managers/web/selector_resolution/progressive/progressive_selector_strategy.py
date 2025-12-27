"""Progressive selector strategy generator for AI-powered element resolution."""

import json
import logging
import re
from typing import List, Dict, Any, Optional
from lamia.interpreter.commands import LLMCommand

logger = logging.getLogger(__name__)


class ProgressiveSelectorStrategy:
    """
    Generates progressive selector strategies from natural language descriptions.
    
    Produces a list of selectors ordered from most specific to most generic,
    with validation rules for each strategy.
    """
    
    def __init__(self, llm_manager):
        """Initialize the strategy generator.
        
        Args:
            llm_manager: LLM manager for generating strategies
        """
        self.llm_manager = llm_manager
    
    async def generate_strategies(
        self, 
        description: str
    ) -> List[Dict[str, Any]]:
        """
        Generate progressive selector strategies using LLM.
        
        Args:
            description: Natural language description of element(s) to find
            
        Returns:
            List of strategy dicts with:
            - selectors: List of CSS/XPath selectors to try
            - strictness: "strict" | "relaxed" | "generic"
            - description: What this strategy matches
            - validation: Dict with validation rules
            
        Example:
            Input: "review button"
            Output: [
                {
                    "selectors": ["button:contains('Review')"],
                    "strictness": "strict",
                    "description": "Button with exact 'Review' text",
                    "validation": {
                        "count": "exactly_1",
                        "relationship": "none"
                    }
                },
                ...
            ]
        """
        logger.info(f"Generating progressive strategies for: '{description}'")
        
        # Detect strictness from language (default to relaxed per user requirement)
        is_strict = self._has_strict_keywords(description)
        default_strictness = "strict" if is_strict else "relaxed"
        
        # Create prompt
        prompt = self._create_strategy_prompt(description, default_strictness)
        
        # Execute LLM command
        llm_command = LLMCommand(prompt=prompt)
        result = await self.llm_manager.execute(llm_command)
        
        # Parse LLM response into structured strategies
        strategies = self._parse_strategies(result.validated_text, description)
        
        logger.info(f"Generated {len(strategies)} progressive strategies")
        return strategies
    
    def _has_strict_keywords(self, description: str) -> bool:
        """Detect if description requires strict matching.
        
        Args:
            description: Natural language description
            
        Returns:
            True if strict keywords found, False otherwise
        """
        strict_keywords = ['exactly', 'only', 'precisely', 'just', 'must be']
        description_lower = description.lower()
        return any(kw in description_lower for kw in strict_keywords)
    
    def _create_strategy_prompt(self, description: str, default_strictness: str) -> str:
        """Create LLM prompt for strategy generation.
        
        Args:
            description: Natural language description
            default_strictness: Default strictness level ("strict" or "relaxed")
            
        Returns:
            Formatted prompt string
        """
        return f"""Generate a progressive list of CSS/XPath selectors for finding this element:

Description: "{description}"

Return 3-5 selector strategies ordered from MOST SPECIFIC to MOST GENERIC.
Each strategy should try different approaches (text content, attributes, structure, etc.).

For each strategy, provide:
1. selectors: Array of 1-3 selectors to try for this strategy
2. strictness: "{default_strictness}" (use this unless description explicitly requires different)
3. description: Human-readable explanation of what this matches
4. validation: Object with:
   - count: "exactly_N", "at_least_N", or "any" (default: "at_least_1")
   - relationship: "none", "siblings", "common_ancestor" (for multi-element queries)
   - max_ancestor_levels: Number (only if relationship is "common_ancestor", default: 5)

Format as JSON array. Example:

```json
[
  {{
    "selectors": ["button:contains('Submit')", "button[aria-label*='submit' i]"],
    "strictness": "{default_strictness}",
    "description": "Button with 'Submit' text or aria-label",
    "validation": {{
      "count": "exactly_1",
      "relationship": "none"
    }}
  }},
  {{
    "selectors": ["[role='button']:contains('submit')", "input[type='submit']"],
    "strictness": "relaxed",
    "description": "Any button-like element with 'submit'",
    "validation": {{
      "count": "at_least_1",
      "relationship": "none"
    }}
  }}
]
```

IMPORTANT RULES:
- For multi-element queries like "two inputs grouped together", set relationship to "common_ancestor"
- Use "exactly_N" for count only if description says "exactly", "only", or specifies a number
- Default to "at_least_1" for count unless specified
- Progress from specific (exact text, IDs) to generic (partial text, roles, tags)
- Include both CSS and XPath selectors when helpful

Now generate strategies for: "{description}"

Return ONLY the JSON array, no explanation:"""
    
    def _parse_strategies(self, llm_response: str, description: str) -> List[Dict[str, Any]]:
        """Parse LLM JSON response into strategy list.
        
        Args:
            llm_response: Raw LLM response text
            description: Original description (for fallback)
            
        Returns:
            List of strategy dictionaries
        """
        try:
            # Try direct JSON parse
            strategies = json.loads(llm_response)
            if isinstance(strategies, list) and len(strategies) > 0:
                return self._validate_strategies(strategies)
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON from markdown code blocks
        match = re.search(r'```json\s*(\[.*?\])\s*```', llm_response, re.DOTALL)
        if match:
            try:
                strategies = json.loads(match.group(1))
                if isinstance(strategies, list) and len(strategies) > 0:
                    return self._validate_strategies(strategies)
            except json.JSONDecodeError:
                pass
        
        # Try extracting any JSON array
        match = re.search(r'\[.*?\]', llm_response, re.DOTALL)
        if match:
            try:
                strategies = json.loads(match.group(0))
                if isinstance(strategies, list) and len(strategies) > 0:
                    return self._validate_strategies(strategies)
            except json.JSONDecodeError:
                pass
        
        # Fallback: create basic strategy
        logger.warning(f"Failed to parse LLM strategies, using fallback for: '{description}'")
        return self._create_fallback_strategies(description)
    
    def _validate_strategies(self, strategies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and normalize strategy structures.
        
        Args:
            strategies: Raw strategy list from LLM
            
        Returns:
            Validated and normalized strategies
        """
        validated = []
        
        for strategy in strategies:
            # Ensure required fields
            if 'selectors' not in strategy:
                continue
            
            # Normalize selectors to list
            if isinstance(strategy['selectors'], str):
                strategy['selectors'] = [strategy['selectors']]
            
            # Set defaults
            strategy.setdefault('strictness', 'relaxed')
            strategy.setdefault('description', 'Element match')
            strategy.setdefault('validation', {})
            strategy['validation'].setdefault('count', 'at_least_1')
            strategy['validation'].setdefault('relationship', 'none')
            
            if strategy['validation']['relationship'] == 'common_ancestor':
                strategy['validation'].setdefault('max_ancestor_levels', 5)
            
            validated.append(strategy)
        
        return validated
    
    def _create_fallback_strategies(self, description: str) -> List[Dict[str, Any]]:
        """Create basic fallback strategies when LLM fails.
        
        Args:
            description: Natural language description
            
        Returns:
            Basic strategy list
        """
        # Extract potential keywords
        words = description.lower().split()
        
        # Simple heuristics
        strategies = []
        
        # Strategy 1: Try as text content
        strategies.append({
            "selectors": [f"*:contains('{description}')"],
            "strictness": "relaxed",
            "description": f"Any element containing '{description}'",
            "validation": {
                "count": "at_least_1",
                "relationship": "none"
            }
        })
        
        # Strategy 2: Try common element types
        if any(word in words for word in ['button', 'click', 'submit']):
            strategies.insert(0, {
                "selectors": [
                    f"button:contains('{description}')",
                    f"[role='button']:contains('{description}')",
                    "button, [role='button']"
                ],
                "strictness": "relaxed",
                "description": "Button element",
                "validation": {
                    "count": "at_least_1",
                    "relationship": "none"
                }
            })
        
        if any(word in words for word in ['input', 'field', 'text']):
            strategies.insert(0, {
                "selectors": [
                    "input[type='text']",
                    "input:not([type='hidden'])",
                    "textarea"
                ],
                "strictness": "relaxed",
                "description": "Input field",
                "validation": {
                    "count": "at_least_1",
                    "relationship": "none"
                }
            })
        
        return strategies

