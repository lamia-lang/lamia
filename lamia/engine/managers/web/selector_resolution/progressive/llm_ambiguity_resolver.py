"""LLM-based ambiguity resolver for element selection."""

import logging
from typing import List, Any, Optional, Dict

from pydantic import BaseModel

from lamia.interpreter.commands import LLMCommand
from lamia.validation.base import ValidationResult
from lamia.validation.validators.file_validators.file_structure.json_structure_validator import JSONStructureValidator
from lamia.engine.managers.llm.llm_manager import LLMManager
from .element_ambiguity_resolver import ElementAmbiguityResolver
from .progressive_selector_strategy import ProgressiveSelectorStrategyIntent, ElementCount

logger = logging.getLogger(__name__)


class AmbiguitySelectionModel(BaseModel):
    """Model for LLM ambiguity selection response."""
    selected_indices: List[int]
    reason: Optional[str] = None


class LLMAmbiguityResolver(ElementAmbiguityResolver):
    """
    Resolves ambiguous element matches using LLM analysis.
    
    Presents element summaries to the LLM and asks it to select
    the most appropriate element(s) based on the description and intent.
    """
    
    def __init__(
        self,
        browser_adapter: Any,
        llm_manager: LLMManager,
        max_elements_to_analyze: int = 100
    ):
        """
        Initialize the LLM ambiguity resolver.
        
        Args:
            browser_adapter: Browser adapter for element inspection
            llm_manager: LLM manager for generating selections
            max_elements_to_analyze: Maximum elements to send to LLM
        """
        self.browser = browser_adapter
        self.llm_manager = llm_manager
        self.max_elements_to_analyze = max_elements_to_analyze
        self.ambiguity_json_validator = JSONStructureValidator(model=AmbiguitySelectionModel)
    
    async def resolve(
        self,
        description: str,
        elements: List[Any],
        intent: ProgressiveSelectorStrategyIntent,
        page_url: str,
    ) -> Optional[List[Any]]:
        """
        Resolve ambiguity using LLM analysis.
        
        Args:
            description: Original natural language description
            elements: List of matching element handles
            intent: The parsed intent from the selector strategy
            page_url: Current page URL (unused, kept for interface compatibility)
            
        Returns:
            List of resolved elements, or None if resolution failed
        """
        if len(elements) <= 1:
            return elements
        
        logger.info(f"LLM ambiguity resolver analyzing {len(elements)} elements")
        
        summarized = await self._summarize_elements(elements[:self.max_elements_to_analyze])
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
            logger.debug("LLM ambiguity resolution failed: invalid response")
            return None
        
        selection: AmbiguitySelectionModel = result.result_type  # type: ignore[assignment]
        indices = [idx for idx in selection.selected_indices if 0 <= idx < len(elements)]
        
        if not indices:
            logger.debug("LLM ambiguity resolution returned no valid indices")
            return None
        
        logger.info(f"LLM selected {len(indices)} element(s): indices {indices}")
        return [elements[idx] for idx in indices]
    
    async def _summarize_elements(self, elements: List[Any]) -> List[Dict[str, Any]]:
        """
        Get summary information for each element.
        
        Args:
            elements: List of element handles
            
        Returns:
            List of element summary dictionaries
        """
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

