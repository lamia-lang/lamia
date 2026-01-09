"""Semantic-based selector resolver using intent understanding."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from .semantic_analyzer import SemanticAnalyzer, SemanticSelectorGenerator

logger = logging.getLogger(__name__)


class SemanticSelectorResolver:
    """
    Resolves natural language descriptions using semantic understanding.
    
    Two-stage process:
    1. Understand what the user actually wants (semantic analysis)
    2. Generate selectors based on that understanding
    """
    
    def __init__(self, browser_adapter, llm_manager):
        """Initialize the semantic resolver.
        
        Args:
            browser_adapter: Browser adapter for finding elements
            llm_manager: LLM manager for semantic analysis and selector generation
        """
        self.browser = browser_adapter
        self.semantic_analyzer = SemanticAnalyzer(llm_manager)
        self.selector_generator = SemanticSelectorGenerator(llm_manager)
    
    async def resolve(
        self,
        description: str,
        page_url: str
    ) -> Tuple[str, List[Any]]:
        """
        Resolve description to actual elements using semantic understanding.
        
        Args:
            description: Natural language description of element(s)
            page_url: Current page URL for logging
            
        Returns:
            (selector_used, elements_found)
            
        Raises:
            ValueError: If no selector successfully finds elements
        """
        logger.info(f"Starting semantic resolution for: '{description}'")
        
        # Stage 1: Understand what the user wants semantically
        logger.info("Stage 1: Analyzing semantic intent...")
        semantic_intent = await self.semantic_analyzer.analyze_description(description)
        
        failed_selectors = []
        max_retries = 2
        
        for attempt in range(max_retries):
            if attempt > 0:
                logger.info(f"Stage 2 retry {attempt}: Generating new selectors avoiding {len(failed_selectors)} failed ones")
            else:
                logger.info("Stage 2: Generating selectors based on semantic understanding...")
            
            # Stage 2: Generate selectors based on understanding
            selectors = await self.selector_generator.generate_selectors(
                semantic_intent,
                failed_selectors if attempt > 0 else None
            )
            
            if not selectors:
                raise ValueError(f"Failed to generate selectors for semantic intent: {semantic_intent}")
            
            logger.info(f"Generated {len(selectors)} selectors to try")
            
            # Try each selector
            for i, selector in enumerate(selectors, 1):
                logger.info(f"[{i}/{len(selectors)}] Trying selector: {selector}")
                
                try:
                    # Find elements using proper browser adapter interface
                    from lamia.internal_types import BrowserActionParams
                    params = BrowserActionParams(selector=selector)
                    elements = await self.browser.get_elements(params)
                    
                    if not elements:
                        logger.debug(f"    No elements found")
                        failed_selectors.append(selector)
                        continue
                    
                    logger.info(f"    ✓ Found {len(elements)} element(s)")
                    
                    # Validate against semantic intent
                    if self._validate_semantic_match(elements, semantic_intent):
                        logger.info(f"✓ Successfully resolved with semantic understanding")
                        return selector, elements
                    else:
                        logger.debug(f"    Elements found but don't match semantic intent")
                        failed_selectors.append(selector)
                        continue
                
                except Exception as e:
                    logger.debug(f"    Selector failed: {e}")
                    failed_selectors.append(selector)
                    continue
            
            # If we reach here, all selectors failed this attempt
            logger.warning(f"Attempt {attempt + 1} failed, will retry with different selectors")
        
        # No selector worked
        raise ValueError(
            f"Could not resolve '{description}' using semantic understanding. "
            f"Tried {len(failed_selectors)} selectors across {max_retries} attempts."
        )
    
    def _validate_semantic_match(
        self, 
        elements: List[Any], 
        semantic_intent
    ) -> bool:
        """
        Validate that found elements match the semantic intent.
        
        Args:
            elements: Found elements 
            semantic_intent: Expected semantic intent
            
        Returns:
            True if elements match intent, False otherwise
        """
        if not elements:
            return False
        
        element_count = len(elements)
        
        # Validate count expectation
        if semantic_intent.count_intent == 'single' and element_count > 10:
            # Too many elements for single intent (but allow some tolerance)
            logger.debug(f"Count mismatch: expected single, found {element_count}")
            return False
        elif semantic_intent.count_intent == 'pair' and element_count != 2:
            # For pair, be more strict
            logger.debug(f"Count mismatch: expected pair, found {element_count}")
            return False
        
        # For now, be permissive with other validations
        # Could add more semantic validation here based on element properties
        
        return True