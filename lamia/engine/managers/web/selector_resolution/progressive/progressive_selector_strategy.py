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
        
        # Detect strictness from language (default to relaxed per user requirement)
        is_strict = self._has_strict_keywords(description)
        default_strictness = "strict" if is_strict else "relaxed"
        
        # Create prompt
        prompt = self._create_strategy_prompt(description, default_strictness, failed_selectors)
        
        # Execute LLM command
        llm_command = LLMCommand(prompt=prompt)
        result = await self.llm_manager.execute(llm_command)
        
        # Parse LLM response into structured strategies
        strategies = await self._parse_strategies(result.validated_text, description)
        
        # Enhance strategies with intent analysis
        intent = self._parse_web_command_intent(description)
        enhanced_strategies = self._enhance_strategies_with_intent(strategies, intent)
        
        logger.info(f"Generated {len(enhanced_strategies)} progressive strategies")
        return enhanced_strategies
    
    def _parse_web_command_intent(self, description: str) -> Dict[str, Any]:
        """Parse a web command description to understand user intent.
        
        Args:
            description: Natural language description from web command
            
        Returns:
            Dict with:
            - element_count: "single" or "multiple"
            - keywords: List of important keywords
            - element_types: List of suggested HTML element types
            - relationship: "grouped", "siblings", "none"
        """
        description_lower = description.lower()
        words = description_lower.split()
        
        # Analyze element count intent
        multiple_keywords = ['elements', 'fields', 'items', 'buttons', 'inputs', 'links', 'grouped together']
        single_keywords = ['element', 'field', 'button', 'input', 'link', 'one ']
        
        element_count = "single"
        if any(kw in description_lower for kw in multiple_keywords):
            element_count = "multiple"
        elif any(kw in description_lower for kw in single_keywords):
            element_count = "single"
        
        # Detect relationship keywords
        relationship = "none"
        if any(kw in description_lower for kw in ['grouped', 'together', 'pair', 'combo']):
            relationship = "grouped"
        elif any(kw in description_lower for kw in ['siblings', 'adjacent', 'next to']):
            relationship = "siblings"
        
        # Extract HTML element type keywords
        element_type_map = {
            'input': ['input', 'field', 'textbox', 'text box'],
            'button': ['button', 'btn', 'click'],
            'link': ['link', 'anchor', 'href'],
            'label': ['label', 'question', 'prompt'],
            'select': ['dropdown', 'select', 'option'],
            'textarea': ['textarea', 'text area'],
            'checkbox': ['checkbox', 'check'],
            'radio': ['radio', 'option']
        }
        
        element_types = []
        for element_type, keywords in element_type_map.items():
            if any(kw in description_lower for kw in keywords):
                element_types.append(element_type)
        
        # Extract important keywords for selector generation
        important_keywords = [word for word in words if len(word) > 3 and word not in [
            'and', 'the', 'for', 'with', 'that', 'this', 'from', 'into', 'where'
        ]]
        
        return {
            'element_count': element_count,
            'keywords': important_keywords,
            'element_types': element_types,
            'relationship': relationship
        }
    
    def _enhance_strategies_with_intent(
        self, 
        strategies: List[Dict[str, Any]], 
        intent: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Enhance generated strategies with parsed intent information.
        
        Args:
            strategies: Original strategies from LLM
            intent: Parsed intent information
            
        Returns:
            Enhanced strategies with better validation rules
        """
        for strategy in strategies:
            # Update validation based on element count intent
            if intent['element_count'] == 'multiple' and 'count' in strategy.get('validation', {}):
                # User expects multiple elements
                if strategy['validation']['count'] == 'exactly_1':
                    strategy['validation']['count'] = 'at_least_1'
            
            # Update relationship based on intent
            if intent['relationship'] == 'grouped':
                strategy['validation']['relationship'] = 'common_ancestor'
                strategy['validation']['max_ancestor_levels'] = 3  # Tighter grouping
            elif intent['relationship'] == 'siblings':
                strategy['validation']['relationship'] = 'siblings'
        
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
    
    def _create_strategy_prompt(self, description: str, default_strictness: str, failed_selectors: Optional[List[str]] = None) -> str:
        """Create LLM prompt for strategy generation.
        
        Args:
            description: Natural language description
            default_strictness: Default strictness level ("strict" or "relaxed")
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
        
        return f"""Generate a progressive list of CSS/XPath selectors for finding this element:

Description: "{description}"
{failed_selectors_text}
Return 3-5 selector strategies ordered from MOST SPECIFIC to MOST GENERIC.
Each strategy should try different approaches (text content, attributes, structure, etc.).

IMPORTANT STRATEGY PROGRESSION:
1. Start with very specific selectors (exact text, IDs, specific classes)
2. Progress to moderately specific (partial text matches, role attributes)  
3. End with generic selectors (element types, broad attributes)
4. Include progressive refinement - each strategy should cast a wider net than the previous

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
    "selectors": ["//button[contains(text(), 'Submit')]", "button[aria-label*='submit' i]"],
    "strictness": "{default_strictness}",
    "description": "Button with 'Submit' text or aria-label",
    "validation": {{
      "count": "exactly_1",
      "relationship": "none"
    }}
  }},
  {{
    "selectors": ["//*[@role='button' and contains(text(), 'submit')]", "input[type='submit']"],
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
- For text content matching, use XPath: //element[contains(text(), 'text')] NOT element:contains('text')
- For CSS attribute matching, use: [attribute*='value' i] for case-insensitive partial matches
- Mix XPath and CSS selectors for better coverage

Now generate strategies for: "{description}"

Return ONLY the JSON array, no explanation:"""
    
    async def _parse_strategies(self, llm_response: str, description: str) -> List[Dict[str, Any]]:
        """Parse LLM JSON response into strategy list using Lamia's validator.
        
        Args:
            llm_response: Raw LLM response text
            description: Original description (for fallback)
            
        Returns:
            List of strategy dictionaries
        """
        try:
            # Use Lamia's JSON validator for better parsing
            validation_result = await self.json_validator.validate_permissive(llm_response)
            if validation_result.is_valid:
                strategies = validation_result.validated_data
                if isinstance(strategies, list) and len(strategies) > 0:
                    return self._validate_strategies(strategies)
        except Exception as e:
            logger.debug(f"Lamia JSON validator failed: {e}")
        
        # Fallback to manual parsing if validator fails
        def try_parse_json(json_str):
            """Try parsing JSON with various fixes for common LLM mistakes."""
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # Try removing trailing commas
                fixed_json = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas before }
                fixed_json = re.sub(r',\s*\]', ']', fixed_json)  # Remove trailing commas before ]
                try:
                    return json.loads(fixed_json)
                except json.JSONDecodeError:
                    return None
        
        # Try direct JSON parse
        strategies = try_parse_json(llm_response)
        if strategies and isinstance(strategies, list) and len(strategies) > 0:
            return self._validate_strategies(strategies)
        
        # Try extracting JSON from markdown code blocks (json or generic)
        match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', llm_response, re.DOTALL)
        if match:
            strategies = try_parse_json(match.group(1))
            if strategies and isinstance(strategies, list) and len(strategies) > 0:
                return self._validate_strategies(strategies)
        
        # Try extracting any JSON array
        match = re.search(r'\[.*?\]', llm_response, re.DOTALL)
        if match:
            strategies = try_parse_json(match.group(0))
            if strategies and isinstance(strategies, list) and len(strategies) > 0:
                return self._validate_strategies(strategies)
        
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
        """Create intelligent fallback strategies when LLM fails.
        
        Args:
            description: Natural language description
            
        Returns:
            Progressive strategy list based on heuristics
        """
        # Parse intent for fallback generation
        intent = self._parse_web_command_intent(description)
        words = description.lower().split()
        description_lower = description.lower()
        
        strategies = []
        
        # Strategy 0: Special handling for grouped form elements (most specific to least specific)
        if intent['relationship'] == 'grouped' and any(word in description_lower for word in ['question', 'answer', 'input', 'field']):
            # Strategy 0a: Most specific - Application forms (modal contexts, not search filters)
            strategies.append({
                "selectors": [
                    # Application-specific form containers (most reliable)
                    ".jobs-easy-apply-modal fieldset",
                    "[data-test-modal-id='easy-apply-modal'] fieldset", 
                    ".jobs-easy-apply-form-section fieldset",
                    # Application-specific forms with question+answer patterns
                    "//div[contains(@class, 'jobs-easy-apply') and .//label and .//input]",
                    "//form[contains(@class, 'apply') and .//label and .//input]//fieldset",
                    # Modal-scoped fieldsets (exclude search filters by context)
                    ".modal fieldset:not(.reusable-search-filters-trigger-dropdown__container)",
                    "[role='dialog'] fieldset, [aria-modal='true'] fieldset"
                ],
                "strictness": "strict",
                "description": "Question-answer groups in application forms or modals (most specific)",
                "validation": {
                    "count": "at_least_1", 
                    "relationship": "common_ancestor",
                    "max_ancestor_levels": 2
                }
            })
            
            # Strategy 0b: Moderately specific - General form containers
            strategies.append({
                "selectors": [
                    # Generic form containers with question+answer structure 
                    "//div[.//label and .//input and not(contains(@class, 'search'))]:not(//div[contains(@class, 'filter')])",
                    ".form-group, .field-group, .form-item, .form-field",
                    "//fieldset[.//legend and .//input and not(contains(@class, 'search'))]:not(//fieldset[contains(@class, 'filter')])",
                    # XPath alternatives that work in all browsers
                    "//div[.//label or .//span[contains(text(), '?')]][.//input[@type='text' or @type='email' or @type='tel']]"
                ],
                "strictness": "relaxed",
                "description": "Question-answer groups in form containers (moderately specific)",
                "validation": {
                    "count": "at_least_1",
                    "relationship": "common_ancestor", 
                    "max_ancestor_levels": 3
                }
            })
            
            # Strategy 0c: Least specific - Any fieldsets/containers (fallback)
            strategies.append({
                "selectors": [
                    # Generic fallbacks (least preferred) 
                    "fieldset",
                    "div[class*='field']",
                    "div[class*='question']", 
                    "div[class*='form']",
                    "div[class*='input']"
                ],
                "strictness": "relaxed",
                "description": "Any form containers (least specific fallback)",
                "validation": {
                    "count": "at_least_1",
                    "relationship": "common_ancestor",
                    "max_ancestor_levels": 5
                }
            })
        
        # Strategy 1: Element-type specific with text content
        if intent['element_types']:
            for element_type in intent['element_types']:
                if element_type == 'input':
                    strategies.append({
                        "selectors": [
                            f"//input[contains(@placeholder, '{description.split()[0]}')]",
                            f"input[placeholder*='{description.split()[0]}' i]",
                            "input[type='text'], input[type='email'], input[type='tel'], textarea"
                        ],
                        "strictness": "relaxed",
                        "description": f"Input fields related to '{description}'",
                        "validation": {
                            "count": "at_least_1",
                            "relationship": intent['relationship'] if intent['relationship'] != 'none' else 'none'
                        }
                    })
                elif element_type == 'button':
                    strategies.append({
                        "selectors": [
                            f"//button[contains(text(), '{description}')]",
                            f"//*[@role='button' and contains(text(), '{description}')]",
                            f"button, [role='button'], input[type='submit']"
                        ],
                        "strictness": "relaxed", 
                        "description": f"Button elements related to '{description}'",
                        "validation": {
                            "count": "at_least_1",
                            "relationship": "none"
                        }
                    })
        
        # Strategy 2: Text content search with element hints
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
                    "relationship": intent['relationship'] if intent['relationship'] != 'none' else 'none'
                }
            })
        
        # Strategy 3: Generic element types based on intent
        if intent['element_count'] == 'multiple':
            strategies.append({
                "selectors": [
                    "input:not([type='hidden']), textarea, select",
                    "[role='textbox'], [role='combobox'], [contenteditable='true']",
                    "*"  # Ultimate fallback - any element
                ],
                "strictness": "relaxed",
                "description": "Generic interactive form elements",
                "validation": {
                    "count": "at_least_1",  # Be more lenient 
                    "relationship": "none"  # Remove strict grouping requirement
                }
            })
        else:
            strategies.append({
                "selectors": [
                    "input:not([type='hidden']), textarea, select, button",
                    "[role], [aria-label]", 
                    "*"  # Ultimate fallback
                ],
                "strictness": "relaxed",
                "description": "Any form or interactive element",
                "validation": {
                    "count": "at_least_1",
                    "relationship": "none"
                }
            })
        
        # Strategy 4: Absolute fallback - just find any elements
        strategies.append({
            "selectors": [
                "*",  # Match any element
                "body *",  # Any element in body
                "html"  # Last resort
            ],
            "strictness": "relaxed",
            "description": "Absolute fallback - any element on page",
            "validation": {
                "count": "at_least_1",
                "relationship": "none"
            }
        })
        
        # Ensure we have at least one strategy
        if not strategies:
            strategies.append({
                "selectors": [f"//*[contains(text(), '{description}')]"],
                "strictness": "relaxed",
                "description": f"Any element containing '{description}'",
                "validation": {
                    "count": "at_least_1",
                    "relationship": "none"
                }
            })
        
        return strategies

