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

# Maximum length for attribute values and text content
MAX_ATTRIBUTE_VALUE_LENGTH = 100


class AmbiguitySelectionModel(BaseModel):
    """Model for LLM ambiguity selection response."""
    selected_indices: List[int]
    reason: Optional[str] = None


class LLMAmbiguityResolver(ElementAmbiguityResolver):
    """
    Resolves ambiguous element matches using LLM analysis.
    
    Uses a two-phase approach:
    1. First tries with JSON summaries (all attributes, efficient)
    2. Falls back to outerHTML if JSON approach fails
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
    
    async def resolve_ambiguity(
        self,
        description: str,
        elements: List[Any],
        intent: ProgressiveSelectorStrategyIntent,
        page_url: str,
    ) -> Optional[List[Any]]:
        """
        Resolve ambiguity using LLM analysis with fallback strategy.
        
        First attempts resolution using JSON summaries (all attributes).
        If that fails, falls back to using outerHTML for more context.
        
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
        
        elements_to_analyze = elements[:self.max_elements_to_analyze]
        
        # Phase 1: Try with JSON summaries (all attributes)
        result = await self._resolve_with_json_summaries(
            description, elements_to_analyze, intent
        )
        if result:
            return result
        
        # Phase 2: Fallback to outerHTML for more context
        logger.info("JSON summary resolution failed, trying with outerHTML fallback")
        result = await self._resolve_with_outer_html(
            description, elements_to_analyze, intent
        )
        return result
    
    async def _resolve_with_json_summaries(
        self,
        description: str,
        elements: List[Any],
        intent: ProgressiveSelectorStrategyIntent,
    ) -> Optional[List[Any]]:
        """
        Attempt resolution using JSON element summaries.
        
        Args:
            description: Original natural language description
            elements: List of element handles to analyze
            intent: The parsed intent from the selector strategy
            
        Returns:
            List of resolved elements, or None if resolution failed
        """
        summaries = await self._summarize_elements_json(elements)
        prompt = self._build_json_prompt(description, summaries, intent)
        return await self._execute_llm_selection(prompt, elements, intent)
    
    async def _resolve_with_outer_html(
        self,
        description: str,
        elements: List[Any],
        intent: ProgressiveSelectorStrategyIntent,
    ) -> Optional[List[Any]]:
        """
        Attempt resolution using truncated outerHTML.
        
        Args:
            description: Original natural language description
            elements: List of element handles to analyze
            intent: The parsed intent from the selector strategy
            
        Returns:
            List of resolved elements, or None if resolution failed
        """
        html_snippets = await self._get_outer_html_snippets(elements)
        prompt = self._build_outer_html_prompt(description, html_snippets, intent)
        return await self._execute_llm_selection(prompt, elements, intent)
    
    async def _execute_llm_selection(
        self,
        prompt: str,
        elements: List[Any],
        intent: ProgressiveSelectorStrategyIntent,
    ) -> Optional[List[Any]]:
        """
        Execute LLM selection and return resolved elements.
        
        Args:
            prompt: The prompt to send to LLM
            elements: Original list of elements
            intent: The parsed intent
            
        Returns:
            List of selected elements, or None if selection failed
        """
        llm_command = LLMCommand(prompt=prompt)
        result: ValidationResult = await self.llm_manager.execute(
            llm_command,
            self.ambiguity_json_validator,
        )
        
        if not result.is_valid:
            logger.debug("LLM ambiguity resolution failed: invalid response")
            return None
        
        selection: AmbiguitySelectionModel = result.typed_result  # type: ignore[assignment]
        indices = [idx for idx in selection.selected_indices if 0 <= idx < len(elements)]
        
        if not indices:
            logger.debug("LLM ambiguity resolution returned no valid indices")
            return None
        
        logger.info(f"LLM selected {len(indices)} element(s): indices {indices}")
        return [elements[idx] for idx in indices]
    
    def _build_json_prompt(
        self,
        description: str,
        summaries: List[Dict[str, Any]],
        intent: ProgressiveSelectorStrategyIntent,
    ) -> str:
        """Build prompt for JSON summary based resolution."""
        prompt_lines = []
        for idx, summary in enumerate(summaries):
            attrs_str = ", ".join(
                f"{k}={v}" for k, v in summary.get('attributes', {}).items()
                if v is not None
            )
            prompt_lines.append(
                f"{idx}) tag={summary.get('tag')} text=\"{summary.get('text')}\" "
                f"attrs=[{attrs_str}]"
            )
        
        count_hint = (
            "Return exactly 1 index."
            if intent.element_count == ElementCount.SINGLE
            else "Return all matching indices."
        )
        
        return (
            "You are selecting the best matching DOM elements based on their attributes.\n"
            f"Description: \"{description}\"\n"
            f"Intent element_count: {intent.element_count.value}\n"
            f"{count_hint}\n"
            "Elements:\n"
            + "\n".join(prompt_lines)
            + "\nReturn JSON: {\"selected_indices\": [0]} (empty list if none match)."
        )
    
    def _build_outer_html_prompt(
        self,
        description: str,
        html_snippets: List[str],
        intent: ProgressiveSelectorStrategyIntent,
    ) -> str:
        """Build prompt for outerHTML based resolution."""
        prompt_lines = []
        for idx, html in enumerate(html_snippets):
            prompt_lines.append(f"{idx}) {html}")
        
        count_hint = (
            "Return exactly 1 index."
            if intent.element_count == ElementCount.SINGLE
            else "Return all matching indices."
        )
        
        return (
            "You are selecting the best matching DOM elements based on their HTML.\n"
            f"Description: \"{description}\"\n"
            f"Intent element_count: {intent.element_count.value}\n"
            f"{count_hint}\n"
            "Elements (truncated HTML):\n"
            + "\n".join(prompt_lines)
            + "\nReturn JSON: {\"selected_indices\": [0]} (empty list if none match)."
        )
    
    async def _summarize_elements_json(self, elements: List[Any]) -> List[Dict[str, Any]]:
        """
        Get summary information for each element, capturing ALL attributes.
        
        Args:
            elements: List of element handles
            
        Returns:
            List of element summary dictionaries with all attributes
        """
        summaries = []
        for element in elements:
            summary = await self.browser.execute_script(
                f"""
                const el = arguments[0];
                const text = (el.innerText || '').trim();
                
                // Capture ALL attributes
                const attrs = {{}};
                for (const attr of el.attributes) {{
                    // Truncate long attribute values
                    attrs[attr.name] = attr.value ? attr.value.slice(0, {MAX_ATTRIBUTE_VALUE_LENGTH}) : null;
                }}
                
                return {{
                    tag: el.tagName ? el.tagName.toLowerCase() : null,
                    text: text || null,
                    attributes: attrs
                }};
                """,
                element,
            )
            summaries.append(summary or {"tag": None, "text": None, "attributes": {}})
        return summaries
    
    async def _get_outer_html_snippets(self, elements: List[Any]) -> List[str]:
        """
        Get truncated outerHTML for each element.
        
        Args:
            elements: List of element handles
            
        Returns:
            List of truncated HTML strings
        """
        snippets = []
        for element in elements:
            html = await self.browser.execute_script(
                f"""
                const el = arguments[0];
                const html = el.outerHTML || '';
                return html;
                """,
                element,
            )
            snippets.append(html or "<unknown>")
        return snippets
