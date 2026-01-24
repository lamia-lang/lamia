"""Progressive selector strategy generator for AI-powered element resolution."""

import json
import logging
import re
from typing import List, Dict, Any, Optional
from lamia.interpreter.commands import LLMCommand
from lamia.validation.validators.file_validators.json_validator import JSONValidator

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
        self.json_validator = JSONValidator(strict=False)
    
    async def generate_strategies(
        self, 
        description: str,
        failed_selectors: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate progressive selector strategies using LLM.
        
        Args:
            description: Natural language description of element(s) to find
            failed_selectors: List of selectors that have already failed (to avoid regenerating them)
            
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
        
        # Create prompt
        prompt = self._create_strategy_prompt(description, failed_selectors)
        
        # Execute LLM command
        llm_command = LLMCommand(prompt=prompt)
        result = await self.llm_manager.execute(llm_command)
        
        # Parse LLM response - now includes intent from LLM
        intent, strategies = await self._parse_strategies(result.validated_text, description)
        
        # Enhance strategies with LLM-parsed intent
        enhanced_strategies = self._enhance_strategies_with_intent(strategies, intent)
        
        logger.info(f"Generated {len(enhanced_strategies)} progressive strategies (intent: {intent})")
        return enhanced_strategies
    
    def _parse_intent_fallback(self, description: str) -> Dict[str, Any]:
        """Simple fallback for intent parsing when LLM fails.
        
        Uses minimal heuristics - just checks for plural nouns and relationship keywords.
        
        Args:
            description: Natural language description
            
        Returns:
            Dict with element_count and relationship
        """
        description_lower = description.lower()
        words = description_lower.split()
        
        # Detect plural: word ends in 's' but not 'ss', 'us', 'is', 'ess'
        element_count = "single"
        for word in words:
            if len(word) >= 4 and word.endswith('s') and not word.endswith(('ss', 'us', 'is', 'ess')):
                element_count = "multiple"
                break
        
        # Detect relationship
        relationship = "none"
        if any(kw in description_lower for kw in ['grouped', 'together', 'pair', 'combo']):
            relationship = "grouped"
        elif any(kw in description_lower for kw in ['siblings', 'adjacent', 'next to']):
            relationship = "siblings"
        
        return {
            'element_count': element_count,
            'relationship': relationship,
            'strictness': 'relaxed'
        }
    
    def _enhance_strategies_with_intent(
        self, 
        strategies: List[Dict[str, Any]], 
        intent: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Enhance generated strategies with parsed intent information.
        
        Args:
            strategies: Original strategies from LLM
            intent: Parsed intent with element_count and relationship
            
        Returns:
            Enhanced strategies with better validation rules
        """
        element_count = intent.get('element_count', 'single')
        relationship = intent.get('relationship', 'none')
        strictness = intent.get('strictness', 'relaxed')
        
        for strategy in strategies:
            validation = strategy.setdefault('validation', {})
            strategy.setdefault('strictness', strictness)
            
            # Update validation based on element count intent
            if element_count == 'multiple':
                # User expects multiple elements - don't enforce exactly_1
                if validation.get('count') == 'exactly_1':
                    validation['count'] = 'at_least_1'
            
            # Update relationship based on intent
            if relationship == 'grouped':
                validation['relationship'] = 'common_ancestor'
                validation.setdefault('max_ancestor_levels', 3)
            elif relationship == 'siblings':
                validation['relationship'] = 'siblings'
        
        return strategies
    
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
  - If singular noun or "a/the + singular", it's "single"
- relationship: How are elements related?
  - "grouped" if words like: grouped, together, pair, combo, associated
  - "siblings" if words like: siblings, adjacent, next to, beside
  - "none" otherwise
- strictness: Should selectors be "strict" or "relaxed"?
  - "strict" when the user says "exactly", "only", "precisely", or provides a unique identifier
  - "relaxed" otherwise

STEP 2 - GENERATE STRATEGIES:
Generate 3-5 selector strategies ordered from MOST SPECIFIC to MOST GENERIC.
Each strategy should try different approaches (text content, attributes, structure, etc.).

Return JSON with this structure:
```json
{{
  "intent": {{
    "element_count": "single" or "multiple",
    "relationship": "none" | "grouped" | "siblings",
    "strictness": "strict" | "relaxed"
  }},
  "strategies": [
    {{
      "selectors": ["//button[contains(text(), 'Submit')]", "button[aria-label*='submit' i]"],
      "strictness": "strict",
      "description": "Button with 'Submit' text or aria-label",
      "validation": {{
        "count": "exactly_1",
        "relationship": "none"
      }}
    }},
    ...
  ]
}}
```

STRATEGY RULES:
- Start with very specific selectors (exact text, IDs, specific classes)
- Progress to moderately specific (partial text matches, role attributes)  
- End with generic selectors (element types, broad attributes)
- For multi-element queries, set validation.relationship to "common_ancestor"
- Use "exactly_N" for count only if description says "exactly", "only", or specifies a number
- Default to "at_least_1" for count unless specified
- For text content matching, use XPath: //element[contains(text(), 'text')] NOT element:contains('text')
- For CSS attribute matching, use: [attribute*='value' i] for case-insensitive partial matches
- Mix XPath and CSS selectors for better coverage

Now analyze and generate for: "{description}"

Return ONLY the JSON object, no explanation:"""
    
    async def _parse_strategies(self, llm_response: str, description: str) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Parse LLM JSON response into intent and strategy list.
        
        Args:
            llm_response: Raw LLM response text
            description: Original description (for fallback)
            
        Returns:
            Tuple of (intent dict, list of strategy dictionaries)
        """
        default_intent: Dict[str, Any] = {"element_count": "single", "relationship": "none", "strictness": "relaxed"}
        
        def try_parse_json(json_str: str) -> Optional[Any]:
            """Try parsing JSON with various fixes for common LLM mistakes."""
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                fixed_json = re.sub(r',\s*}', '}', json_str)
                fixed_json = re.sub(r',\s*\]', ']', fixed_json)
                try:
                    return json.loads(fixed_json)
                except json.JSONDecodeError:
                    return None
        
        def extract_intent_and_strategies(data: Any) -> Optional[tuple[Dict[str, Any], List[Dict[str, Any]]]]:
            """Extract intent and strategies from parsed data."""
            if isinstance(data, dict):
                intent = data.get("intent", default_intent)
                strategies = data.get("strategies", [])
                if strategies:
                    return intent, self._validate_strategies(strategies)
            elif isinstance(data, list):
                return default_intent, self._validate_strategies(data)
            return None
        
        # Try Lamia's JSON validator first
        try:
            validation_result = await self.json_validator.validate_permissive(llm_response)
            if validation_result.is_valid and validation_result.validated_text:
                data = try_parse_json(validation_result.validated_text)
                if data:
                    parsed = extract_intent_and_strategies(data)
                    if parsed:
                        return parsed
        except Exception as e:
            logger.debug(f"Lamia JSON validator failed: {e}")
        
        # Try direct JSON parse
        data = try_parse_json(llm_response)
        if data:
            parsed = extract_intent_and_strategies(data)
            if parsed:
                return parsed
        
        # Try extracting JSON from markdown code blocks
        match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', llm_response, re.DOTALL)
        if match:
            data = try_parse_json(match.group(1))
            if data:
                parsed = extract_intent_and_strategies(data)
                if parsed:
                    return parsed
        
        # Try extracting any JSON object or array
        for pattern in (r'\{.*\}', r'\[.*\]'):
            match = re.search(pattern, llm_response, re.DOTALL)
            if match:
                data = try_parse_json(match.group(0))
                if data:
                    parsed = extract_intent_and_strategies(data)
                    if parsed:
                        return parsed
        
        # Fallback: create basic strategy with heuristic intent
        logger.warning(f"Failed to parse LLM strategies, using fallback for: '{description}'")
        fallback_intent = self._parse_intent_fallback(description)
        return fallback_intent, self._create_fallback_strategies(description)
    
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
        """Create intelligent fallback strategies when LLM fails.
        
        Args:
            description: Natural language description
            
        Returns:
            Progressive strategy list based on heuristics
        """
        # Parse intent for fallback generation
        intent = self._parse_intent_fallback(description)
        words = description.lower().split()
        description_lower = description.lower()
        
        strategies: List[Dict[str, Any]] = []
        relationship = intent.get('relationship', 'none')
        element_count = intent.get('element_count', 'single')

        if relationship == 'grouped':
            strategies.append({
                "selectors": [
                    "fieldset",
                    ".form-group, .field-group, .form-field",
                    "[role='group'], [aria-labelledby]"
                ],
                "strictness": "relaxed",
                "description": "Grouped form elements or fieldsets",
                "validation": {
                    "count": "at_least_1",
                    "relationship": "common_ancestor",
                    "max_ancestor_levels": 3
                }
            })

        keywords = [word for word in words if len(word) > 2]
        if keywords:
            first_keyword = keywords[0]
            strategies.append({
                "selectors": [
                    f"//*[contains(text(), '{first_keyword}')]",
                    f"[aria-label*='{first_keyword}' i]",
                    f"[data-testid*='{first_keyword}' i]"
                ],
                "strictness": "relaxed",
                "description": f"Elements containing '{first_keyword}'",
                "validation": {
                    "count": "at_least_1",
                    "relationship": relationship if relationship != 'none' else 'none'
                }
            })

        strategies.append({
            "selectors": [
                "input:not([type='hidden']), textarea, select, button",
                "[role], [aria-label]",
                "*"
            ],
            "strictness": "relaxed",
            "description": "Generic interactive or labeled elements",
            "validation": {
                "count": "at_least_1" if element_count == "multiple" else "at_least_1",
                "relationship": "none"
            }
        })

        return strategies

