"""Tests for ElementRelationshipValidator."""

import pytest
from unittest.mock import Mock, AsyncMock

from lamia.engine.managers.web.selector_resolution.progressive.relationship_validator import ElementRelationshipValidator
from lamia.engine.managers.web.selector_resolution.progressive.progressive_selector_strategy import ElementCount


@pytest.fixture
def mock_browser_adapter():
    """Create a mock browser adapter."""
    browser = Mock()
    browser.get_elements = AsyncMock(return_value=[])
    browser.execute_script = AsyncMock(return_value=None)
    return browser


class TestRelationshipValidator:

    def test_init(self, mock_browser_adapter):
        """Test basic initialization."""
        validator = ElementRelationshipValidator(mock_browser_adapter)

        assert validator.browser == mock_browser_adapter

    def test_validate_count_single(self, mock_browser_adapter):
        """SINGLE count allows multiple matches — ambiguity resolution handles that."""
        validator = ElementRelationshipValidator(mock_browser_adapter)

        elements = [Mock()]
        is_valid, _ = validator._validate_count(elements, ElementCount.SINGLE)
        assert is_valid is True

        elements = [Mock(), Mock()]
        is_valid, _ = validator._validate_count(elements, ElementCount.SINGLE)
        assert is_valid is True

    def test_validate_count_multiple(self, mock_browser_adapter):
        """Test multiple count validation."""
        validator = ElementRelationshipValidator(mock_browser_adapter)

        elements = [Mock(), Mock()]
        is_valid, _ = validator._validate_count(elements, ElementCount.MULTIPLE)
        assert is_valid is True

        elements = [Mock()]
        is_valid, reason = validator._validate_count(elements, ElementCount.MULTIPLE)
        assert is_valid is False
        assert reason is not None
        assert "expected multiple elements" in reason.lower()


class TestSiblings:
    """Comprehensive tests for _are_siblings method."""
    
    # Edge Cases - Element Count
    
    async def test_are_siblings_empty_list(self, mock_browser_adapter):
        """Test with empty list - should return True."""
        validator = ElementRelationshipValidator(mock_browser_adapter)
        
        result = await validator._are_siblings([])
        
        assert result is True
        # execute_script should never be called
        mock_browser_adapter.execute_script.assert_not_called()
    
    async def test_are_siblings_single_element(self, mock_browser_adapter):
        """Test with single element - should return True without checking."""
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock()]
        
        result = await validator._are_siblings(elements)
        
        assert result is True
        # execute_script should never be called
        mock_browser_adapter.execute_script.assert_not_called()
    
    # Happy Path - Two Elements
    
    async def test_are_siblings_two_elements_same_parent(self, mock_browser_adapter):
        """Test two elements with same parent - should return True."""
        parent1 = Mock()
        parent2 = Mock()
        
        # Setup: first call returns parent1, second returns parent2, third returns True (same parent)
        mock_browser_adapter.execute_script.side_effect = [
            parent1,  # First element's parent
            parent2,  # Second element's parent
            True      # Comparison: parent1 === parent2
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._are_siblings(elements)
        
        assert result is True
        assert mock_browser_adapter.execute_script.call_count == 3
    
    async def test_are_siblings_two_elements_different_parent(self, mock_browser_adapter):
        """Test two elements with different parents - should return False."""
        parent1 = Mock()
        parent2 = Mock()
        
        mock_browser_adapter.execute_script.side_effect = [
            parent1,  # First element's parent
            parent2,  # Second element's parent
            False     # Comparison: parent1 === parent2 (different)
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._are_siblings(elements)
        
        assert result is False
        assert mock_browser_adapter.execute_script.call_count == 3
    
    # Multiple Elements
    
    async def test_are_siblings_three_elements_all_same_parent(self, mock_browser_adapter):
        """Test three elements all with same parent - should return True."""
        parent = Mock()
        
        mock_browser_adapter.execute_script.side_effect = [
            parent,  # elem[0]'s parent
            parent,  # elem[1]'s parent
            True,    # parent === parent (elem[1])
            parent,  # elem[2]'s parent
            True     # parent === parent (elem[2])
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock(), Mock()]
        
        result = await validator._are_siblings(elements)
        
        assert result is True
        assert mock_browser_adapter.execute_script.call_count == 5
    
    async def test_are_siblings_three_elements_second_different_parent(self, mock_browser_adapter):
        """Test three elements, second has different parent - should return False early."""
        parent1 = Mock()
        parent2 = Mock()
        
        mock_browser_adapter.execute_script.side_effect = [
            parent1,  # elem[0]'s parent
            parent2,  # elem[1]'s parent (different)
            False     # parent1 === parent2 (False - stops here)
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock(), Mock()]
        
        result = await validator._are_siblings(elements)
        
        assert result is False
        # Should stop early, not check third element
        assert mock_browser_adapter.execute_script.call_count == 3
    
    # Edge Cases - No Parent
    
    async def test_are_siblings_first_element_no_parent(self, mock_browser_adapter):
        """Test when first element has no parent - should return False."""
        mock_browser_adapter.execute_script.side_effect = [
            None  # First element has no parent
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._are_siblings(elements)
        
        assert result is False
        # Should stop immediately after first parent check
        assert mock_browser_adapter.execute_script.call_count == 1
    
    async def test_are_siblings_second_element_no_parent(self, mock_browser_adapter):
        """Test when second element has no parent - should return False."""
        parent1 = Mock()
        
        mock_browser_adapter.execute_script.side_effect = [
            parent1,  # First element's parent
            None      # Second element has no parent
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._are_siblings(elements)
        
        assert result is False
        assert mock_browser_adapter.execute_script.call_count == 2
    
    # Exception Handling
    
    async def test_are_siblings_exception_on_first_parent(self, mock_browser_adapter):
        """Test exception when getting first parent - should return False."""
        mock_browser_adapter.execute_script.side_effect = Exception("JS execution failed")
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._are_siblings(elements)
        
        assert result is False
    
    async def test_are_siblings_exception_on_second_parent(self, mock_browser_adapter):
        """Test exception when getting second parent - should return False."""
        parent1 = Mock()
        
        mock_browser_adapter.execute_script.side_effect = [
            parent1,  # First succeeds
            Exception("JS execution failed")  # Second fails
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._are_siblings(elements)
        
        assert result is False
    
    async def test_are_siblings_exception_on_comparison(self, mock_browser_adapter):
        """Test exception during parent comparison - should return False."""
        parent1 = Mock()
        parent2 = Mock()
        
        mock_browser_adapter.execute_script.side_effect = [
            parent1,  # First parent
            parent2,  # Second parent
            Exception("JS comparison failed")  # Comparison fails
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._are_siblings(elements)
        
        assert result is False
    
    # Complex Scenarios
    
    async def test_are_siblings_five_elements_all_siblings(self, mock_browser_adapter):
        """Test with many elements, all siblings."""
        parent = Mock()
        
        # First parent + 4 more parent checks + 4 comparisons
        mock_browser_adapter.execute_script.side_effect = [
            parent, parent, True,  # elem[0], elem[1] check
            parent, True,          # elem[2] check
            parent, True,          # elem[3] check
            parent, True           # elem[4] check
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock() for _ in range(5)]
        
        result = await validator._are_siblings(elements)
        
        assert result is True
    
    async def test_are_siblings_five_elements_fourth_different(self, mock_browser_adapter):
        """Test with many elements, fourth has different parent - stops early."""
        parent1 = Mock()
        parent2 = Mock()
        
        mock_browser_adapter.execute_script.side_effect = [
            parent1, parent1, True,  # elem[0], elem[1] check - OK
            parent1, True,           # elem[2] check - OK
            parent2, False           # elem[3] check - DIFFERENT (stops)
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock() for _ in range(5)]
        
        result = await validator._are_siblings(elements)
        
        assert result is False
        # Should stop at fourth element, not check fifth
        assert mock_browser_adapter.execute_script.call_count == 7


class TestFindCommonAncestor:
    """Comprehensive tests for _find_common_ancestor method."""
    
    # Edge Cases - Element Count
    
    async def test_find_common_ancestor_empty_list(self, mock_browser_adapter):
        """Test with empty list - should raise ValueError."""
        validator = ElementRelationshipValidator(mock_browser_adapter)
        
        with pytest.raises(ValueError):
            await validator._find_common_ancestor([])

    async def test_find_common_ancestor_empty_with_one_element(self, mock_browser_adapter):
        """Test with empty list with one element - should raise ValueError."""
        validator = ElementRelationshipValidator(mock_browser_adapter)
        
        with pytest.raises(ValueError):
            await validator._find_common_ancestor([Mock()])
    
    # Two Elements - Common Ancestor at Level 1
    
    async def test_find_common_ancestor_two_elements_immediate_parent(self, mock_browser_adapter):
        """Test two elements with common ancestor at level 1 (immediate parent)."""
        element1 = Mock()
        element2 = Mock()
        parent = Mock()
        
        async def execute_script_side_effect(script, *args):
            if script.strip() == "return arguments[0].parentElement":
                if args and args[0] is element1:
                    return parent
                return None
            if script.strip() == "return arguments[0].contains(arguments[1])":
                if args == (parent, element2):
                    return True
            return None
        
        mock_browser_adapter.execute_script.side_effect = execute_script_side_effect
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [element1, element2]
        
        result = await validator._find_common_ancestor(elements, max_levels=5)
        
        assert result == parent
        assert mock_browser_adapter.execute_script.call_count == 3
    
    async def test_find_common_ancestor_two_elements_at_level_2(self, mock_browser_adapter):
        """Test two elements with common ancestor at level 2."""
        ancestor1 = Mock()
        ancestor2 = Mock()
        element1 = Mock()
        element2 = Mock()
        
        async def execute_script_side_effect(script, *args):
            if script.strip() == "return arguments[0].parentElement":
                if args and args[0] is element1:
                    return ancestor1
                if args and args[0] is ancestor1:
                    return ancestor2
                return None
            if script.strip() == "return arguments[0].contains(arguments[1])":
                if args == (ancestor1, element2):
                    return False
                if args == (ancestor2, element2):
                    return True
            return None
        
        mock_browser_adapter.execute_script.side_effect = execute_script_side_effect
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [element1, element2]
        
        result = await validator._find_common_ancestor(elements, max_levels=5)
        
        assert result == ancestor2
    
    async def test_find_common_ancestor_two_elements_at_level_3(self, mock_browser_adapter):
        """Test two elements with common ancestor at level 3."""
        ancestor1 = Mock()
        ancestor2 = Mock()
        ancestor3 = Mock()
        element1 = Mock()
        element2 = Mock()
        
        async def execute_script_side_effect(script, *args):
            if script.strip() == "return arguments[0].parentElement":
                if args and args[0] is element1:
                    return ancestor1
                if args and args[0] is ancestor1:
                    return ancestor2
                if args and args[0] is ancestor2:
                    return ancestor3
                return None
            if script.strip() == "return arguments[0].contains(arguments[1])":
                if args == (ancestor1, element2):
                    return False
                if args == (ancestor2, element2):
                    return False
                if args == (ancestor3, element2):
                    return True
            return None
        
        mock_browser_adapter.execute_script.side_effect = execute_script_side_effect
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [element1, element2]
        
        result = await validator._find_common_ancestor(elements, max_levels=5)
        
        assert result == ancestor3
    
    # Two Elements - No Common Ancestor
    
    async def test_find_common_ancestor_two_elements_no_common(self, mock_browser_adapter):
        """Test two elements with no common ancestor within max_levels."""
        ancestor1 = Mock()
        ancestor2 = Mock()
        ancestor3 = Mock()
        
        mock_browser_adapter.execute_script.side_effect = [
            ancestor1,  # Level 1
            ancestor2,  # Level 2
            ancestor3,  # Level 3
            False,      # ancestor1.contains(elem[1]) - no
            False,      # ancestor2.contains(elem[1]) - no
            False       # ancestor3.contains(elem[1]) - no
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._find_common_ancestor(elements, max_levels=3)
        
        assert result is None
    
    async def test_find_common_ancestor_reaches_document_root(self, mock_browser_adapter):
        """Test when traversal reaches document root (None parent)."""
        ancestor1 = Mock()
        ancestor2 = Mock()
        
        mock_browser_adapter.execute_script.side_effect = [
            ancestor1,  # Level 1
            ancestor2,  # Level 2
            None,       # Level 3 - no more parents (document root)
            False,      # ancestor1.contains(elem[1]) - no
            False       # ancestor2.contains(elem[1]) - no
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._find_common_ancestor(elements, max_levels=5)
        
        assert result is None
        # Should only traverse 2 levels (stops at None)
        assert mock_browser_adapter.execute_script.call_count == 5
    
    # Three Elements
    
    async def test_find_common_ancestor_three_elements_at_level_1(self, mock_browser_adapter):
        """Test three elements with common ancestor at level 1."""
        element1 = Mock()
        element2 = Mock()
        element3 = Mock()
        parent = Mock()
        
        async def execute_script_side_effect(script, *args):
            if script.strip() == "return arguments[0].parentElement":
                if args and args[0] is element1:
                    return parent
                return None
            if script.strip() == "return arguments[0].contains(arguments[1])":
                if args == (parent, element2):
                    return True
                if args == (parent, element3):
                    return True
            return None
        
        mock_browser_adapter.execute_script.side_effect = execute_script_side_effect
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [element1, element2, element3]
        
        result = await validator._find_common_ancestor(elements, max_levels=5)
        
        assert result == parent
        assert mock_browser_adapter.execute_script.call_count == 4
    
    async def test_find_common_ancestor_three_elements_second_not_contained(self, mock_browser_adapter):
        """Test three elements, second not in first ancestor - checks next level."""
        ancestor1 = Mock() # Level 1
        ancestor2 = Mock() # Level 2
        element1 = Mock()
        element2 = Mock()
        element3 = Mock()
        
        async def execute_script_side_effect(script, *args):
            if script.strip() == "return arguments[0].parentElement":
                if args and args[0] is element1:
                    return ancestor1
                if args and args[0] is ancestor1:
                    return ancestor2
                return None
            if script.strip() == "return arguments[0].contains(arguments[1])":
                if args == (ancestor1, element2):
                    return False
                if args == (ancestor1, element3):
                    return True
                if args == (ancestor2, element2):
                    return True
                if args == (ancestor2, element3):
                    return True
            return None
        
        mock_browser_adapter.execute_script.side_effect = execute_script_side_effect
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [element1, element2, element3]
        
        result = await validator._find_common_ancestor(elements, max_levels=5)
        
        assert result == ancestor2
    
    async def test_find_common_ancestor_five_elements_at_level_2(self, mock_browser_adapter):
        """Test five elements with common ancestor at level 2."""
        ancestor1 = Mock() # Level 1
        ancestor2 = Mock() # Level 2
        element1 = Mock()
        element2 = Mock()
        element3 = Mock()
        element4 = Mock()
        element5 = Mock()
        
        async def execute_script_side_effect(script, *args):
            if script.strip() == "return arguments[0].parentElement":
                if args and args[0] is element1:
                    return ancestor1
                if args and args[0] is ancestor1:
                    return ancestor2
                return None
            if script.strip() == "return arguments[0].contains(arguments[1])":
                if args == (ancestor1, element2):
                    return False
                if args == (ancestor1, element3):
                    return False
                if args == (ancestor1, element4):
                    return False
                if args == (ancestor1, element5):
                    return False
                if args == (ancestor2, element2):
                    return True
                if args == (ancestor2, element3):
                    return True
                if args == (ancestor2, element4):
                    return True
                if args == (ancestor2, element5):
                    return True
            return None
        
        mock_browser_adapter.execute_script.side_effect = execute_script_side_effect
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [element1, element2, element3, element4, element5]
        
        result = await validator._find_common_ancestor(elements, max_levels=5)
        
        assert result == ancestor2
    
    # max_levels Boundary
    
    async def test_find_common_ancestor_max_levels_1(self, mock_browser_adapter):
        """Test with max_levels=1 - only checks immediate parent."""
        parent = Mock()
        
        mock_browser_adapter.execute_script.side_effect = [
            parent,  # elem[0].parentElement (level 1)
            False    # parent.contains(elem[1]) - no
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._find_common_ancestor(elements, max_levels=1)
        
        assert result is None
        assert mock_browser_adapter.execute_script.call_count == 2
    
    async def test_find_common_ancestor_max_levels_0(self, mock_browser_adapter):
        """Test with max_levels=0 - no ancestors checked."""
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._find_common_ancestor(elements, max_levels=0)
        
        assert result is None
        # Should not traverse any ancestors
        mock_browser_adapter.execute_script.assert_not_called()
    
    async def test_find_common_ancestor_respects_max_levels(self, mock_browser_adapter):
        """Test that search stops at max_levels."""
        ancestor1 = Mock()
        ancestor2 = Mock()
        
        # Set up 2 levels, but common ancestor would be at level 3 (not reached)
        mock_browser_adapter.execute_script.side_effect = [
            ancestor1,  # Level 1
            ancestor2,  # Level 2
            # No level 3 because max_levels=2
            False,      # ancestor1.contains(elem[1]) - no
            False       # ancestor2.contains(elem[1]) - no
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._find_common_ancestor(elements, max_levels=2)
        
        assert result is None
        assert mock_browser_adapter.execute_script.call_count == 4
    
    # Exception Handling
    
    async def test_find_common_ancestor_exception_during_traversal(self, mock_browser_adapter):
        """Test exception while traversing ancestors - returns None."""
        ancestor1 = Mock()
        
        mock_browser_adapter.execute_script.side_effect = [
            ancestor1,                      # Level 1 succeeds
            Exception("Traversal failed")   # Level 2 fails
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._find_common_ancestor(elements, max_levels=5)
        
        assert result is None
    
    async def test_find_common_ancestor_exception_during_containment_check(self, mock_browser_adapter):
        """Test exception during containment check - continues to next ancestor."""
        
        ancestor1 = Mock()
        ancestor2 = Mock()
        element1 = Mock()
        element2 = Mock()

        async def execute_script_side_effect(script, *args):
            if script.strip() == "return arguments[0].parentElement":
                if args and args[0] is element1:
                    return ancestor1
                if args and args[0] is ancestor1:
                    return ancestor2
                return None
            if script.strip() == "return arguments[0].contains(arguments[1])":
                if args == (ancestor1, element2):
                    raise Exception("Contains check failed")
            return None

        mock_browser_adapter.execute_script.side_effect = execute_script_side_effect
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [element1, element2]
        
        result = await validator._find_common_ancestor(elements, max_levels=5)
        
        assert result is None
    
    # Complex Scenarios
    
    async def test_find_common_ancestor_deep_hierarchy(self, mock_browser_adapter):
        """Test finding ancestor at maximum depth."""
        ancestors = [Mock() for _ in range(5)]
        
        # Build side_effect: 5 ancestors, then checks for each
        side_effects = ancestors.copy()  # Traversal
        side_effects.extend([False, False, False, False, True])  # Only level 5 contains elem[1]
        
        mock_browser_adapter.execute_script.side_effect = side_effects
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._find_common_ancestor(elements, max_levels=5)
        
        assert result == ancestors[4]  # The 5th ancestor
    
    async def test_find_common_ancestor_first_element_orphan(self, mock_browser_adapter):
        """Test when first element has no parent - returns None immediately."""
        mock_browser_adapter.execute_script.side_effect = [
            None  # elem[0] has no parent
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock()]
        
        result = await validator._find_common_ancestor(elements, max_levels=5)
        
        assert result is None
        # Should stop after first parent check
        assert mock_browser_adapter.execute_script.call_count == 1
    
    async def test_find_common_ancestor_all_checks_fail_multiple_elements(self, mock_browser_adapter):
        """Test when no ancestor contains all elements - exhaustive search."""
        ancestor1 = Mock()
        ancestor2 = Mock()
        ancestor3 = Mock()
        
        mock_browser_adapter.execute_script.side_effect = [
            ancestor1,  # Level 1
            ancestor2,  # Level 2
            ancestor3,  # Level 3
            True, False,  # ancestor1: contains elem[1], NOT elem[2]
            True, False,  # ancestor2: contains elem[1], NOT elem[2]
            True, False   # ancestor3: contains elem[1], NOT elem[2]
        ]
        
        validator = ElementRelationshipValidator(mock_browser_adapter)
        elements = [Mock(), Mock(), Mock()]
        
        result = await validator._find_common_ancestor(elements, max_levels=3)
        
        assert result is None
        # 3 ancestors + 2 checks per ancestor = 9 calls
        assert mock_browser_adapter.execute_script.call_count == 9

