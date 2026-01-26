"""Progressive selector resolver that tries strategies from specific to generic."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from .progressive_selector_strategy import ProgressiveSelectorStrategy
from .relationship_validator import ElementRelationshipValidator
from .ambiguity_resolver import AmbiguityResolver
from .progressive_selector_strategy import ProgressiveSelectorStrategyIntent

logger = logging.getLogger(__name__)


class ProgressiveSelectorResolver:
    """
    Resolves natural language descriptions to elements using progressive strategies.
    
    Tries selectors from most specific to most generic, validating relationships
    and handling ambiguity with user input when needed.
    """
    
    def __init__(
        self,
        browser_adapter,
        llm_manager,
        cache,
        max_ambiguous_matches: int = 10
    ):
        """Initialize the progressive resolver.
        
        Args:
            browser_adapter: Browser adapter for finding elements
            llm_manager: LLM manager for generating strategies
            cache: AISelectorCache for caching resolutions
            max_ambiguous_matches: Max matches before asking user to choose
        """
        self.browser = browser_adapter
        self.strategy_gen = ProgressiveSelectorStrategy(llm_manager)
        self.relationship_validator = ElementRelationshipValidator(browser_adapter)
        self.ambiguity_resolver = AmbiguityResolver(browser_adapter, cache)
        self.max_ambiguous_matches = max_ambiguous_matches
    
    async def resolve(
        self,
        description: str,
        page_url: str
    ) -> Tuple[str, List[Any]]:
        """
        Resolve description to actual elements progressively.
        
        Args:
            description: Natural language description of element(s)
            page_url: Current page URL for caching
            
        Returns:
            (selector_used, elements_found)
            
        Raises:
            ValueError: If no strategy successfully finds elements
        """
        logger.info(f"Starting progressive resolution for: '{description}'")
        
        failed_selectors = []
        max_retries = 2
        
        for retry_attempt in range(max_retries):
            if retry_attempt > 0:
                logger.info(f"Retry attempt {retry_attempt} with {len(failed_selectors)} failed selectors to avoid")
            
            # Generate progressive selectors (with failed selectors if retrying)
            intent, selectors = await self.strategy_gen.generate_strategies(
                description, 
                failed_selectors if retry_attempt > 0 else None
            )
            
            if not selectors:
                raise ValueError(f"Failed to get selectors for: '{description}'")
            
            logger.info(f"The LLM suggested the {len(selectors)} selectors, trying each...")
            
            # Try each strategy from specific to generic  
            selector_success = False
            strictness = intent.strictness
            for i, selector in enumerate(selectors, 1):
                
                logger.info(f"[{i}/{len(selectors)}] Trying {strictness} selector: {selector}")
                
                try:
                    # Try all selectors in this strategy
                    for selector in selectors:
                        logger.debug(f"Trying selector: {selector}")
                        
                        try:
                            # Find elements
                            elements = await self._find_elements(selector)
                            
                            if not elements:
                                logger.debug(f"No elements found with selector: {selector}")
                                failed_selectors.append(selector)
                                continue
                            
                            logger.debug(f"Found {len(elements)} element(s) with selector: {selector}")
                            
                            # Validate relationship
                            is_valid, reason = await self.relationship_validator.validate_strategy_match(
                                elements,
                                intent
                            )
                            
                            if not is_valid:
                                logger.debug(f"Validation failed: {reason}")
                                failed_selectors.append(selector)
                                continue
                            
                            # Check for ambiguity
                            expected_count = strategy.get('validation', {}).get('count', 'at_least_1')
                            
                            if self._is_ambiguous(elements, expected_count):
                                logger.info(f"    Found {len(elements)} matches (ambiguous)")
                                
                                # Ask user to choose
                                selected = await self.ambiguity_resolver.resolve_ambiguous_match(
                                    description,
                                    elements,
                                    page_url,
                                    max_display=self.max_ambiguous_matches
                                )
                                
                                elements = [selected]
                            
                            # Success!
                            logger.info(f"  ✓ Successfully resolved with {strictness} strategy")
                            return selector, elements
                        
                        except Exception as e:
                            logger.debug(f"    Selector failed: {e}")
                            failed_selectors.append(selector)
                            continue
                
                except Exception as e:
                    logger.debug(f"  Strategy {i} failed: {e}")
                    continue
            
            # If we reach here, all strategies failed this attempt
            if not strategy_success:
                logger.warning(f"Retry attempt {retry_attempt + 1} failed, collected {len(failed_selectors)} failed selectors")
                if retry_attempt == max_retries - 1:
                    break  # Last attempt, will raise error below
        
        # No strategy worked
        raise ValueError(
            f"Could not resolve '{description}' - tried {len(strategies)} strategies with "
            f"{sum(len(s.get('selectors', [])) for s in strategies)} total selectors"
        )
    
    async def _find_elements(self, selector: str) -> List[Any]:
        """
        Find elements using selector.
        
        Args:
            selector: CSS or XPath selector
            
        Returns:
            List of element handles
        """
        try:
            # Use proper browser adapter interface
            from lamia.internal_types import BrowserActionParams
            params = BrowserActionParams(selector=selector)
            elements = await self.browser.get_elements(params)
            
            return elements or []
        except Exception as e:
            logger.debug(f"Failed to find elements with '{selector}': {e}")
            return []
    
    def _is_ambiguous(self, elements: List[Any], expected_count: str) -> bool:
        """
        Check if match is ambiguous (more elements than expected).
        
        Args:
            elements: Found elements
            expected_count: Expected count specification
            
        Returns:
            True if ambiguous and user input needed
        """
        actual_count = len(elements)
        
        # If expecting exactly N and found more, it's ambiguous
        if expected_count.startswith('exactly_'):
            try:
                expected = int(expected_count.split('_')[1])
                if actual_count > expected:
                    return True
            except (ValueError, IndexError):
                pass
        
        # If found way more than reasonable (>10), it's ambiguous
        if actual_count > self.max_ambiguous_matches:
            return True
        
        return False

