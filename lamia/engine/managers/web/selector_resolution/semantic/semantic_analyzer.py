"""Semantic analysis for natural language selector descriptions."""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SemanticIntent:
    """Parsed semantic intent from user description."""
    element_types: List[str]  # ['input', 'label', 'button'] 
    element_purpose: str      # 'form_field', 'navigation', 'content'
    relationship: str         # 'grouped', 'paired', 'sequential', 'independent'
    count_intent: str         # 'single', 'multiple', 'pair'
    interaction_type: str     # 'input', 'selection', 'trigger', 'display'
    semantic_roles: List[str] # ['question', 'answer', 'submit', 'cancel']
    keywords: List[str]       # Important words for selector generation


class SemanticAnalyzer:
    """Analyzes natural language descriptions to understand user intent."""
    
    def __init__(self, llm_manager):
        self.llm_manager = llm_manager
    
    async def analyze_description(self, description: str) -> SemanticIntent:
        """Analyze a natural language description to understand semantic intent.
        
        Args:
            description: User's natural language description
            
        Returns:
            SemanticIntent object with parsed understanding
        """
        logger.info(f"Analyzing semantic intent for: '{description}'")
        
        # First, ask LLM to understand the semantic meaning
        understanding = await self._get_semantic_understanding(description)
        
        # Parse the understanding into structured intent
        intent = self._parse_understanding(understanding, description)
        
        logger.info(f"Semantic analysis result: {intent}")
        return intent
    
    async def _get_semantic_understanding(self, description: str) -> str:
        """Ask LLM to explain what the user is looking for semantically."""
        prompt = f"""Analyze this web element description and explain what the user is actually looking for:

Description: "{description}"

Explain in simple terms:
1. What TYPE of web elements are they looking for? (input fields, buttons, links, text, etc.)
2. What PURPOSE do these elements serve? (collecting user input, navigation, displaying info, etc.) 
3. How are the elements RELATED to each other? (grouped together, paired up, in sequence, independent, etc.)
4. How many elements do they expect? (one specific element, multiple elements, a pair, etc.)
5. What will the user DO with these elements? (type text, click, select options, read content, etc.)
6. What are the SEMANTIC ROLES? (question, answer, submit button, cancel, etc.)

Be concise and focus on the INTENT, not literal text matching.

Example:
Input: "login button"
Output: The user wants to find a single clickable button element that serves the purpose of logging into the application. It's an independent element they will click to trigger authentication.

Input: "one question and one answer input field grouped together" 
Output: The user wants to find a pair of input elements that work together as a question-answer unit. One field likely shows/contains a question (could be a label or readonly field), and another field is for the user to type their answer. These elements are spatially grouped together in the form layout.

Now analyze: "{description}"
"""
        
        from lamia.interpreter.commands import LLMCommand
        llm_command = LLMCommand(prompt=prompt)
        result = await self.llm_manager.execute(llm_command)
        
        return result.validated_text.strip()
    
    def _parse_understanding(self, understanding: str, original_description: str) -> SemanticIntent:
        """Parse the LLM understanding into structured semantic intent."""
        understanding_lower = understanding.lower()
        
        # Determine element types based on understanding
        element_types = []
        type_indicators = {
            'input': ['input', 'field', 'textbox', 'text field', 'form field'],
            'button': ['button', 'clickable', 'submit', 'trigger'],
            'label': ['label', 'question', 'text', 'display'],
            'select': ['dropdown', 'select', 'choose', 'options'],
            'link': ['link', 'navigation', 'navigate']
        }
        
        for element_type, indicators in type_indicators.items():
            if any(indicator in understanding_lower for indicator in indicators):
                element_types.append(element_type)
        
        # Determine element purpose
        purpose = 'form_field'  # Default
        if any(word in understanding_lower for word in ['navigate', 'navigation', 'link']):
            purpose = 'navigation'
        elif any(word in understanding_lower for word in ['display', 'show', 'content', 'text']):
            purpose = 'content'
        elif any(word in understanding_lower for word in ['input', 'type', 'enter', 'field']):
            purpose = 'form_field'
        
        # Determine relationship
        relationship = 'independent'  # Default
        if any(word in understanding_lower for word in ['grouped', 'together', 'paired', 'pair']):
            relationship = 'grouped'
        elif any(word in understanding_lower for word in ['sequence', 'sequential', 'order']):
            relationship = 'sequential'
        
        # Determine count intent
        count_intent = 'single'  # Default
        if any(word in understanding_lower for word in ['multiple', 'several', 'many']):
            count_intent = 'multiple'
        elif any(word in understanding_lower for word in ['pair', 'two', 'both']):
            count_intent = 'pair'
        elif any(word in understanding_lower for word in ['one', 'single', 'specific']):
            count_intent = 'single'
        
        # Determine interaction type
        interaction_type = 'input'  # Default
        if any(word in understanding_lower for word in ['click', 'trigger', 'press']):
            interaction_type = 'trigger'
        elif any(word in understanding_lower for word in ['select', 'choose', 'pick']):
            interaction_type = 'selection'
        elif any(word in understanding_lower for word in ['type', 'enter', 'input']):
            interaction_type = 'input'
        elif any(word in understanding_lower for word in ['read', 'display', 'show']):
            interaction_type = 'display'
        
        # Extract semantic roles
        semantic_roles = []
        role_indicators = {
            'question': ['question', 'ask', 'prompt', 'query'],
            'answer': ['answer', 'response', 'reply', 'input'],
            'submit': ['submit', 'send', 'confirm', 'save'],
            'cancel': ['cancel', 'close', 'dismiss', 'back']
        }
        
        for role, indicators in role_indicators.items():
            if any(indicator in understanding_lower for indicator in indicators):
                semantic_roles.append(role)
        
        # Extract keywords (filter out common words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        words = original_description.lower().replace(',', '').replace('.', '').split()
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]
        
        return SemanticIntent(
            element_types=element_types,
            element_purpose=purpose,
            relationship=relationship,
            count_intent=count_intent,
            interaction_type=interaction_type,
            semantic_roles=semantic_roles,
            keywords=keywords
        )


class SemanticSelectorGenerator:
    """Generates selectors based on semantic understanding."""
    
    def __init__(self, llm_manager):
        self.llm_manager = llm_manager
    
    async def generate_selectors(
        self, 
        semantic_intent: SemanticIntent,
        failed_selectors: Optional[List[str]] = None
    ) -> List[str]:
        """Generate CSS/XPath selectors based on semantic intent.
        
        Args:
            semantic_intent: Parsed semantic understanding
            failed_selectors: Previously failed selectors to avoid
            
        Returns:
            List of selectors to try, ordered from specific to generic
        """
        logger.info(f"Generating selectors for semantic intent: {semantic_intent}")
        
        # Create focused prompt based on semantic understanding
        prompt = self._create_semantic_prompt(semantic_intent, failed_selectors)
        
        # Get selectors from LLM
        from lamia.interpreter.commands import LLMCommand
        llm_command = LLMCommand(prompt=prompt)
        result = await self.llm_manager.execute(llm_command)
        
        # Parse simple selector list (no JSON complexity)
        selectors = self._parse_selector_list(result.validated_text)
        
        # Add fallback selectors based on semantic intent
        fallback_selectors = self._generate_fallback_selectors(semantic_intent)
        selectors.extend(fallback_selectors)
        
        # Remove any failed selectors
        if failed_selectors:
            selectors = [s for s in selectors if s not in failed_selectors]
        
        logger.info(f"Generated {len(selectors)} selectors")
        return selectors
    
    def _create_semantic_prompt(
        self, 
        semantic_intent: SemanticIntent, 
        failed_selectors: Optional[List[str]]
    ) -> str:
        """Create a focused prompt based on semantic understanding."""
        
        failed_text = ""
        if failed_selectors:
            failed_text = f"\nDO NOT generate these failed selectors: {failed_selectors}\n"
        
        return f"""Generate CSS and XPath selectors for web elements based on this semantic understanding:

SEMANTIC INTENT:
- Element types: {', '.join(semantic_intent.element_types)}
- Purpose: {semantic_intent.element_purpose}
- Relationship: {semantic_intent.relationship}
- Count expected: {semantic_intent.count_intent}
- User interaction: {semantic_intent.interaction_type}
- Semantic roles: {', '.join(semantic_intent.semantic_roles)}
{failed_text}
IMPORTANT RULES:
- Focus on SEMANTIC MEANING, not literal text matching
- For "question" role: look for labels, readonly inputs, or text near input fields
- For "answer" role: look for editable input fields, textareas
- For "grouped" relationship: use selectors that find related elements in same container
- Return 5-8 selectors ordered from SPECIFIC to GENERIC
- Use XPath for text content: //element[contains(text(), 'text')]  
- Use CSS for attributes: [attribute*='value' i]
- Mix both XPath and CSS approaches

Return ONLY a numbered list of selectors, no explanations:

1. selector1
2. selector2
3. selector3
etc."""
    
    def _parse_selector_list(self, llm_response: str) -> List[str]:
        """Parse simple numbered list of selectors."""
        selectors = []
        lines = llm_response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Remove numbering (1. 2. etc.)
            if re.match(r'^\d+\.\s*', line):
                selector = re.sub(r'^\d+\.\s*', '', line).strip()
                if selector:
                    selectors.append(selector)
            elif line and not line.startswith('#') and not line.startswith('//'):
                # Handle lines without numbering
                selectors.append(line)
        
        return selectors
    
    def _generate_fallback_selectors(self, semantic_intent: SemanticIntent) -> List[str]:
        """Generate fallback selectors based on semantic intent."""
        fallbacks = []
        
        # Based on element types
        if 'input' in semantic_intent.element_types:
            fallbacks.extend([
                "input:not([type='hidden'])",
                "textarea", 
                "[contenteditable='true']"
            ])
        
        if 'button' in semantic_intent.element_types:
            fallbacks.extend([
                "button",
                "[role='button']",
                "input[type='submit']",
                "a[role='button']"
            ])
        
        if 'label' in semantic_intent.element_types:
            fallbacks.extend([
                "label",
                ".label",
                "[for]"
            ])
        
        # Based on relationship
        if semantic_intent.relationship == 'grouped':
            fallbacks.extend([
                ".form-group input, .field input",
                "//div[.//label and .//input]//input",
                "fieldset input"
            ])
        
        # Ultimate fallbacks
        fallbacks.extend([
            "[role], [aria-label]",
            "input, button, select, textarea",
            "*"  # Last resort
        ])
        
        return fallbacks