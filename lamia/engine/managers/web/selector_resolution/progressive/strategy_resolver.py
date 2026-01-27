"""Progressive selector resolver that tries strategies from specific to generic."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from .progressive_selector_strategy import ProgressiveSelectorStrategy
from .relationship_validator import ElementRelationshipValidator
from .ambiguity_resolver import AmbiguityResolver
from dataclasses import dataclass
from pydantic import BaseModel
from lamia.adapters.web.browser.base import BrowserActionParams
from lamia.validation.validators.file_validators.file_structure.json_structure_validator import JSONStructureValidator
from lamia.engine.managers.web.selector_resolution.progressive.progressive_selector_strategy import ProgressiveSelectorStrategyModel, ProgressiveSelectorStrategyIntent, ElementCount   

logger = logging.getLogger(__name__)


@dataclass
class ResolutionOutcome:
    selector: Optional[str]
    elements: List[Any]
    had_matches: bool

    @property
    def is_success(self) -> bool:
        return self.selector is not None and len(self.elements) > 0


class AmbiguitySelectionModel(BaseModel):
    selected_indices: List[int]
    reason: Optional[str] = None


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
        self.llm_manager = llm_manager
        self.strategy_gen = ProgressiveSelectorStrategy(llm_manager)
        self.relationship_validator = ElementRelationshipValidator(browser_adapter)
        self.ambiguity_resolver = AmbiguityResolver(browser_adapter, cache)
        self.max_ambiguous_matches = max_ambiguous_matches
        self.ambiguity_json_validator = JSONStructureValidator(model=AmbiguitySelectionModel)
    
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

    def _is_ambiguous(self, elements: List[Any], intent: ProgressiveSelectorStrategyIntent) -> bool:
        actual_count = len(elements)

        if intent.element_count == ElementCount.SINGLE and actual_count > 1:
            return True

        if actual_count > self.max_ambiguous_matches:
            return True

        return False

    async def _resolve_ambiguity(
        self,
        description: str,
        page_url: str,
        elements: List[Any],
        intent: ProgressiveSelectorStrategyIntent,
    ) -> Optional[List[Any]]:
        selected = await self._resolve_ambiguity_with_llm(description, elements, intent)
        if selected:
            return selected

        if intent.element_count == ElementCount.SINGLE and len(elements) <= self.max_ambiguous_matches:
            selected_element = await self.ambiguity_resolver.resolve_ambiguous_match(
                description,
                elements,
                page_url,
                max_display=self.max_ambiguous_matches,
            )
            return [selected_element]

        return None

    async def _resolve_ambiguity_with_llm(
        self,
        description: str,
        elements: List[Any],
        intent: ProgressiveSelectorStrategyIntent,
    ) -> Optional[List[Any]]:
        if len(elements) <= 1:
            return elements

        summarized = await self._summarize_elements(elements[: self.max_ambiguous_matches])
        prompt_lines = []
        for idx, summary in enumerate(summarized):
            prompt_lines.append(
                f"{idx}) tag={summary.get('tag')} text={summary.get('text')} "
                f"id={summary.get('id')} class={summary.get('class_name')} "
                f"role={summary.get('role')} name={summary.get('name')} "
                f"aria={summary.get('aria_label')}"
            )

        count_hint = (
            "Return exactly 1 index."
            if intent.element_count == ElementCount.SINGLE
            else "Return all matching indices."
        )

        prompt = (
            "You are selecting the best matching DOM elements.\n"
            f"Description: \"{description}\"\n"
            f"Intent element_count: {intent.element_count.value}\n"
            f"{count_hint}\n"
            "Elements:\n"
            + "\n".join(prompt_lines)
            + "\nReturn JSON: {\"selected_indices\": [0]} (empty list if none match)."
        )

        llm_command = LLMCommand(prompt=prompt)
        result: ValidationResult = await self.llm_manager.execute(
            llm_command,
            self.ambiguity_json_validator,
        )

        if not result.is_valid:
            return None

        selection: AmbiguitySelectionModel = result.result_type  # type: ignore[assignment]
        indices = [idx for idx in selection.selected_indices if 0 <= idx < len(elements)]
        if not indices:
            return None

        return [elements[idx] for idx in indices]

    async def _summarize_elements(self, elements: List[Any]) -> List[dict]:
        summaries = []
        for element in elements:
            summary = await self.browser.execute_script(
                """
                const el = arguments[0];
                const text = (el.innerText || '').trim().slice(0, 120);
                return {
                  tag: el.tagName ? el.tagName.toLowerCase() : null,
                  id: el.id || null,
                  class_name: el.className || null,
                  role: el.getAttribute('role'),
                  name: el.getAttribute('name'),
                  aria_label: el.getAttribute('aria-label'),
                  text: text || null
                };
                """,
                element,
            )
            summaries.append(summary or {})
        return summaries

