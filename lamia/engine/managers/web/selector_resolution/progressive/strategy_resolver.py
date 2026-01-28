"""Progressive selector resolver that tries strategies from specific to generic."""

import logging
from typing import List, Any, Optional, Tuple
from dataclasses import dataclass

from lamia.adapters.web.browser.base import BrowserActionParams
from lamia.engine.config_provider import ConfigProvider
from lamia.engine.managers.llm.llm_manager import LLMManager
from .progressive_selector_strategy import (
    ProgressiveSelectorStrategy,
    ProgressiveSelectorStrategyIntent,
    ElementCount,
)
from .relationship_validator import ElementRelationshipValidator
from .element_ambiguity_resolver import ElementAmbiguityResolver
from .llm_ambiguity_resolver import LLMAmbiguityResolver
from .human_assisted_ambiguity_resolver import HumanAssistedAmbiguityResolver

logger = logging.getLogger(__name__)


@dataclass
class ResolutionOutcome:
    selector: Optional[str]
    elements: List[Any]
    had_matches: bool

    @property
    def is_success(self) -> bool:
        return self.selector is not None and len(self.elements) > 0


class ProgressiveSelectorResolver:
    """
    Resolves natural language descriptions to elements using progressive strategies.
    
    Tries selectors from most specific to most generic, validating relationships
    and handling ambiguity with LLM and optionally human input.
    """
    
    def __init__(
        self,
        browser_adapter: Any,
        llm_manager: LLMManager,
        cache: Any,
        config_provider: ConfigProvider,
        max_elements_to_analyze: int = 100
    ):
        """Initialize the progressive resolver.
        
        Args:
            browser_adapter: Browser adapter for finding elements
            llm_manager: LLM manager for generating strategies
            cache: AISelectorCache for caching resolutions
            config_provider: Configuration provider for reading settings
            max_elements_to_analyze: Maximum elements to analyze for ambiguity resolution
        """
        self.browser = browser_adapter
        self.llm_manager = llm_manager
        self.config_provider = config_provider
        self.strategy_gen = ProgressiveSelectorStrategy(llm_manager)
        self.relationship_validator = ElementRelationshipValidator(browser_adapter)
        
        # Initialize ambiguity resolvers
        self._ambiguity_resolvers = self._create_ambiguity_resolvers(
            browser_adapter, llm_manager, cache, max_elements_to_analyze
        )
    
    def _create_ambiguity_resolvers(
        self,
        browser_adapter: Any,
        llm_manager: LLMManager,
        cache: Any,
        max_elements_to_analyze: int
    ) -> List[ElementAmbiguityResolver]:
        """
        Create the list of ambiguity resolvers based on configuration.
        
        Args:
            browser_adapter: Browser adapter for element inspection
            llm_manager: LLM manager for LLM-based resolution
            cache: Cache for storing user selections
            max_elements_to_analyze: Max elements for ambiguity resolution
            
        Returns:
            List of ambiguity resolvers in order of priority
        """
        resolvers: List[ElementAmbiguityResolver] = []
        
        # LLM resolver is always first
        resolvers.append(LLMAmbiguityResolver(
            browser_adapter=browser_adapter,
            llm_manager=llm_manager,
            max_elements_to_analyze=max_elements_to_analyze
        ))
        
        # Human resolver is added only if human_in_loop is enabled
        if self._is_human_in_loop_enabled():
            resolvers.append(HumanAssistedAmbiguityResolver(
                browser_adapter=browser_adapter,
                cache=cache,
                max_display=max_elements_to_analyze
            ))
        
        return resolvers
    
    def _is_human_in_loop_enabled(self) -> bool:
        """Check if human-in-loop mode is enabled in config."""

        return self.config_provider.is_human_in_loop_enabled()
    
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
        
        failed_selectors: List[str] = []
        max_retries = 2

        for retry_attempt in range(max_retries):
            if retry_attempt > 0:
                logger.info(
                    f"Retry attempt {retry_attempt} with {len(failed_selectors)} failed selectors to avoid"
                )

            intent, selectors = await self.strategy_gen.generate(
                description,
                failed_selectors if retry_attempt > 0 else None,
            )

            if not selectors:
                raise ValueError(f"Failed to get selectors for: '{description}'")

            outcome = await self._try_selectors(
                description,
                page_url,
                intent,
                selectors,
                failed_selectors,
                step_name="progressive",
            )
            if outcome.is_success:
                if outcome.selector is None:
                    raise ValueError("Selector resolution failed with missing selector")
                return outcome.selector, outcome.elements

        raise ValueError(f"Could not resolve '{description}' after {max_retries} attempts")
    
    async def _find_elements(self, selector: str) -> List[Any]:
        """
        Find elements using selector.
        
        Args:
            selector: CSS or XPath selector
            
        Returns:
            List of element handles
        """
        try:
            params = BrowserActionParams(selector=selector)
            elements = await self.browser.get_elements(params)
            return elements or []
        except Exception as e:
            logger.debug(f"Failed to find elements with '{selector}': {e}")
            return []

    async def _try_selectors(
        self,
        description: str,
        page_url: str,
        intent: ProgressiveSelectorStrategyIntent,
        selectors: List[str],
        failed_selectors: List[str],
        step_name: str,
    ) -> ResolutionOutcome:
        had_matches = False

        if not selectors:
            return ResolutionOutcome(None, [], had_matches)

        logger.info(f"Trying {len(selectors)} {step_name} selectors...")
        for i, selector in enumerate(selectors, 1):
            logger.info(f"[{i}/{len(selectors)}] Trying {step_name} selector: {selector}")

            elements = await self._find_elements(selector)
            if not elements:
                failed_selectors.append(selector)
                continue

            had_matches = True
            is_valid, reason = await self.relationship_validator.validate_strategy_match(
                elements,
                intent,
            )
            if not is_valid:
                logger.debug(f"Validation failed: {reason}")
                failed_selectors.append(selector)
                continue

            if self._is_ambiguous(elements, intent):
                logger.info(f"Found {len(elements)} matches (ambiguous)")
                resolved_elements = await self._resolve_ambiguity(
                    description,
                    page_url,
                    elements,
                    intent,
                )
                if not resolved_elements:
                    failed_selectors.append(selector)
                    continue
                elements = resolved_elements

            logger.info(f"✓ Successfully resolved with {step_name} selector")
            return ResolutionOutcome(selector, elements, had_matches)

        return ResolutionOutcome(None, [], had_matches)

    # TODO: Add support for multiple element intent. Currently, it is supported only for single element intent.
    def _is_ambiguous(self, elements: List[Any], intent: ProgressiveSelectorStrategyIntent) -> bool:
        actual_count = len(elements)

        if intent.element_count == ElementCount.SINGLE and actual_count > 1:
            return True

        return False

    async def _resolve_ambiguity(
        self,
        description: str,
        page_url: str,
        elements: List[Any],
        intent: ProgressiveSelectorStrategyIntent,
    ) -> Optional[List[Any]]:
        """
        Try to resolve ambiguity using configured resolvers.
        
        Iterates through resolvers (LLM first, then human if enabled)
        until one succeeds or all fail.
        
        Args:
            description: Original natural language description
            elements: List of matching element handles
            intent: The parsed intent from the selector strategy
            page_url: Current page URL for caching
            
        Returns:
            List of resolved elements, or None if all resolvers failed
        """
        for resolver in self._ambiguity_resolvers:
            result = await resolver.resolve(
                description=description,
                elements=elements,
                intent=intent,
                page_url=page_url,
            )
            if result:
                return result
        
        return None
