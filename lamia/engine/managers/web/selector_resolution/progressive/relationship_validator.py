"""Validator for element relationships and spatial constraints."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from .progressive_selector_strategy import (
    ProgressiveSelectorStrategyIntent,
    Relationship,
    Strictness,
    ElementCount,
)
from lamia.adapters.web.browser.base import BaseBrowserAdapter

logger = logging.getLogger(__name__)


class ElementRelationshipValidator:
    """
    Validates spatial and hierarchical relationships between found elements.
    
    Unlike HTMLStructureValidator (which validates LLM output structure),
    this validates that found elements have expected relationships in the DOM.
    """
    
    def __init__(self, browser_adapter: BaseBrowserAdapter):
        """Initialize the validator.
        
        Args:
            browser_adapter: Browser adapter for DOM queries
        """
        self.browser = browser_adapter
    
    async def validate_strategy_match(
        self,
        found_elements: List[Any],
        intent: ProgressiveSelectorStrategyIntent
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that found elements match strategy expectations.
        
        Args:
            found_elements: List of element handles found by selectors
            selector: Selector used to find the elements
            
        Returns:
            (is_valid, reason_if_invalid)
        """
        if not found_elements:
            return False, "No elements found"
        
        # 1. Validate count
        count_valid, count_reason = self._validate_count(
            found_elements,
            intent.element_count
        )
        if not count_valid:
            return False, count_reason
        
        
        if intent.relationship == Relationship.GROUPED:
            max_levels = 5
            ancestor = await self._find_common_ancestor(found_elements, max_levels)
            
            if not ancestor:
                return False, f"Elements not grouped under common ancestor (searched {max_levels} levels)"
            
            logger.debug(f"Found common ancestor at level <= {max_levels}")
        
        elif intent.relationship == Relationship.SIBLINGS:
            are_siblings = await self._are_siblings(found_elements)
            if not are_siblings:
                return False, "Elements are not siblings"
        
        # 3. Validate strictness (for siblings, check adjacency)
        if intent.strictness == Strictness.STRICT and intent.relationship == Relationship.SIBLINGS:
            are_adjacent = await self._are_adjacent_siblings(found_elements)
            if not are_adjacent:
                return False, "Elements not adjacent siblings (strict mode)"
        
        return True, None
    
    def _validate_count(
        self,
        elements: List[Any],
        element_count_spec: ElementCount
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate element count based on specification.
        
        Args:
            elements: List of found elements
            element_count_spec: Count intent ("single" or "multiple")
            
        Returns:
            (is_valid, reason_if_invalid)
        """
        actual_count = len(elements)
        
        if element_count_spec == ElementCount.SINGLE:
            if actual_count != 1:
                return False, f"Expected 1 element, found {actual_count}"
            return True, None

        if element_count_spec == ElementCount.MULTIPLE:
            if actual_count < 2:
                return False, f"Expected multiple elements, found {actual_count}"
            return True, None

        return True, None
    
    async def _find_common_ancestor(
        self,
        elements: List[Any],
        max_levels: int = 5
    ) -> Optional[Any]:
        """
        Find nearest common ancestor of all elements.
        
        Args:
            elements: List of element handles
            max_levels: Maximum levels to search up the DOM tree
            
        Returns:
            Common ancestor element handle or None
        """
        if len(elements) <= 1:
            raise ValueError("At least two elements are required for the common ancestor search")
        
        # Get ancestors of first element
        first_elem = elements[0]
        ancestors = []
        current = first_elem
        
        try:
            for level in range(max_levels):
                current = await self.browser.execute_script(
                    "return arguments[0].parentElement",
                    current
                )
                if not current:
                    break
                ancestors.append(current)
        except Exception as e:
            logger.warning(f"Failed to traverse all ancestors: {e}. Traversed {len(ancestors)} levels out of {max_levels}.")
        
        # Find first ancestor that contains all other elements
        try:
            for ancestor in ancestors:
                contains_all = True
                for elem in elements[1:]:
                    is_contained = await self.browser.execute_script(
                        "return arguments[0].contains(arguments[1])",
                        ancestor,
                        elem
                    )
                    if not is_contained:
                        contains_all = False
                        break
                
                if contains_all:
                    return ancestor
        except Exception as e:
            logger.error(f"Failed to check containment: {e}")
        
        return None
    
    async def _are_siblings(self, elements: List[Any]) -> bool:
        """
        Check if all elements are siblings (share same parent).
        
        Args:
            elements: List of element handles
            
        Returns:
            True if all elements have the same parent
        """
        if len(elements) <= 1:
            return True
        
        try:
            # Get parent of first element
            first_parent = await self.browser.execute_script(
                "return arguments[0].parentElement",
                elements[0]
            )
            
            if not first_parent:
                return False
            
            # Check if all other elements have the same parent
            for elem in elements[1:]:
                parent = await self.browser.execute_script(
                    "return arguments[0].parentElement",
                    elem
                )
                
                if not parent:
                    return False
                
                are_same = await self.browser.execute_script(
                    "return arguments[0] === arguments[1]",
                    first_parent,
                    parent
                )
                
                if not are_same:
                    return False
            
            return True
        except Exception as e:
            logger.debug(f"Failed to check sibling relationship: {e}")
            return False
    
    async def _are_adjacent_siblings(self, elements: List[Any]) -> bool:
        """
        Check if elements are adjacent siblings (no other elements between them).
        
        Args:
            elements: List of element handles
            
        Returns:
            True if elements are adjacent in DOM order
        """
        if len(elements) <= 1:
            return True
        
        try:
            # Check each consecutive pair
            for i in range(len(elements) - 1):
                current = elements[i]
                next_elem = elements[i + 1]
                
                # Get next sibling of current
                next_sibling = await self.browser.execute_script(
                    "return arguments[0].nextElementSibling",
                    current
                )
                
                if not next_sibling:
                    return False
                
                # Check if next sibling is the expected next element
                are_same = await self.browser.execute_script(
                    "return arguments[0] === arguments[1]",
                    next_sibling,
                    next_elem
                )
                
                if not are_same:
                    return False
            
            return True
        except Exception as e:
            logger.debug(f"Failed to check adjacent siblings: {e}")
            return False

