"""Tests for SelectionValidator."""

import pytest
from unittest.mock import Mock

from lamia.engine.managers.web.selector_resolution.visual_picker.validation import SelectionValidator


class TestSelectionValidatorInitialization:
    """Test SelectionValidator initialization."""

    def test_validator_initialization(self):
        """Test selection validator initialization."""
        validator = SelectionValidator()
        assert validator is not None


class TestSelectionValidatorElementCount:
    """Test SelectionValidator element count validation."""

    def test_validate_no_elements_found(self):
        """Test validation when no elements found."""
        validator = SelectionValidator()
        selected_element = {"tagName": "BUTTON", "attributes": {}, "isVisible": True}

        is_valid, error = validator.validate_selection_for_method(
            "click",
            "submit button",
            selected_element,
            []
        )

        assert is_valid is False
        assert "No elements found" in error

    def test_validate_singular_method_multiple_elements(self):
        """Test validation when singular method finds multiple elements."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "BUTTON",
            "attributes": {},
            "isVisible": True,
            "isClickable": True,
            "description": "submit"
        }

        is_valid, error = validator.validate_selection_for_method(
            "click",
            "submit button",
            selected_element,
            [Mock(), Mock(), Mock()]
        )

        assert is_valid is False
        assert "ambiguous" in error.lower()

    def test_validate_singular_method_single_element(self):
        """Test validation when singular method finds exactly one element."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "BUTTON",
            "attributes": {},
            "isVisible": True,
            "isClickable": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "click",
            "submit button",
            selected_element,
            [Mock()]
        )

        assert is_valid is True
        assert error == ""

    def test_validate_plural_method_multiple_elements(self):
        """Test validation when plural method finds multiple elements."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "DIV",
            "attributes": {},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "get_elements",
            "all items",
            selected_element,
            [Mock(), Mock(), Mock()]
        )

        assert is_valid is True


class TestSelectionValidatorClickMethod:
    """Test SelectionValidator click method validation."""

    def test_validate_click_button_valid(self):
        """Test validating valid button element for click."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "BUTTON",
            "attributes": {},
            "isVisible": True,
            "isClickable": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "click",
            "submit button",
            selected_element,
            [Mock()]
        )

        assert is_valid is True
        assert error == ""

    def test_validate_click_anchor_valid(self):
        """Test validating valid anchor element for click."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "A",
            "attributes": {},
            "isVisible": True,
            "isClickable": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "click",
            "link",
            selected_element,
            [Mock()]
        )

        assert is_valid is True

    def test_validate_click_input_submit_valid(self):
        """Test validating valid submit input for click."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "INPUT",
            "attributes": {"type": "submit"},
            "isVisible": True,
            "isClickable": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "click",
            "submit button",
            selected_element,
            [Mock()]
        )

        assert is_valid is True

    def test_validate_click_input_text_invalid(self):
        """Test validating text input is not clickable."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "INPUT",
            "attributes": {"type": "text"},
            "isVisible": True,
            "isClickable": False
        }

        is_valid, error = validator.validate_selection_for_method(
            "click",
            "input field",
            selected_element,
            [Mock()]
        )

        assert is_valid is False
        assert "clickable" in error.lower()

    def test_validate_click_div_not_clickable(self):
        """Test validating non-clickable div element."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "DIV",
            "attributes": {},
            "isVisible": True,
            "isClickable": False
        }

        is_valid, error = validator.validate_selection_for_method(
            "click",
            "div element",
            selected_element,
            [Mock()]
        )

        assert is_valid is False
        assert "clickable" in error.lower()

    def test_validate_click_with_role_button(self):
        """Test validating element with role=button is clickable."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "DIV",
            "attributes": {"role": "button"},
            "isVisible": True,
            "isClickable": False
        }

        is_valid, error = validator.validate_selection_for_method(
            "click",
            "button div",
            selected_element,
            [Mock()]
        )

        assert is_valid is True

    def test_validate_click_with_is_clickable_flag(self):
        """Test validating element with isClickable flag."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "SPAN",
            "attributes": {},
            "isVisible": True,
            "isClickable": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "click",
            "clickable span",
            selected_element,
            [Mock()]
        )

        assert is_valid is True


class TestSelectionValidatorTypeTextMethod:
    """Test SelectionValidator type_text method validation."""

    def test_validate_type_text_input_text_valid(self):
        """Test validating valid text input element."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "INPUT",
            "attributes": {"type": "text"},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "type_text",
            "username field",
            selected_element,
            [Mock()]
        )

        assert is_valid is True

    def test_validate_type_text_input_email_valid(self):
        """Test validating email input element."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "INPUT",
            "attributes": {"type": "email"},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "type_text",
            "email field",
            selected_element,
            [Mock()]
        )

        assert is_valid is True

    def test_validate_type_text_textarea_valid(self):
        """Test validating textarea element."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "TEXTAREA",
            "attributes": {},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "type_text",
            "comment field",
            selected_element,
            [Mock()]
        )

        assert is_valid is True

    def test_validate_type_text_contenteditable_valid(self):
        """Test validating contenteditable element."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "DIV",
            "attributes": {"contenteditable": "true"},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "type_text",
            "editable div",
            selected_element,
            [Mock()]
        )

        assert is_valid is True

    def test_validate_type_text_input_checkbox_invalid(self):
        """Test validating checkbox input is not valid for type_text."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "INPUT",
            "attributes": {"type": "checkbox"},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "type_text",
            "checkbox",
            selected_element,
            [Mock()]
        )

        assert is_valid is False
        assert "checkbox" in error.lower()

    def test_validate_type_text_div_invalid(self):
        """Test validating non-input div element."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "DIV",
            "attributes": {},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "type_text",
            "div element",
            selected_element,
            [Mock()]
        )

        assert is_valid is False
        assert "text input" in error.lower()


class TestSelectionValidatorSelectOptionMethod:
    """Test SelectionValidator select_option method validation."""

    def test_validate_select_option_select_valid(self):
        """Test validating valid select element."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "SELECT",
            "attributes": {},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "select_option",
            "country dropdown",
            selected_element,
            [Mock()]
        )

        assert is_valid is True

    def test_validate_select_option_with_role_combobox(self):
        """Test validating element with role=combobox."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "DIV",
            "attributes": {"role": "combobox"},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "select_option",
            "custom dropdown",
            selected_element,
            [Mock()]
        )

        assert is_valid is True

    def test_validate_select_option_with_role_listbox(self):
        """Test validating element with role=listbox."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "UL",
            "attributes": {"role": "listbox"},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "select_option",
            "list dropdown",
            selected_element,
            [Mock()]
        )

        assert is_valid is True

    def test_validate_select_option_input_invalid(self):
        """Test validating input element is not valid for select_option."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "INPUT",
            "attributes": {"type": "text"},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "select_option",
            "input field",
            selected_element,
            [Mock()]
        )

        assert is_valid is False
        assert "select dropdown" in error.lower()


class TestSelectionValidatorUploadFileMethod:
    """Test SelectionValidator upload_file method validation."""

    def test_validate_upload_file_input_file_valid(self):
        """Test validating valid file input element."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "INPUT",
            "attributes": {"type": "file"},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "upload_file",
            "file upload",
            selected_element,
            [Mock()]
        )

        assert is_valid is True

    def test_validate_upload_file_input_text_invalid(self):
        """Test validating text input is not valid for upload_file."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "INPUT",
            "attributes": {"type": "text"},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "upload_file",
            "text input",
            selected_element,
            [Mock()]
        )

        assert is_valid is False
        assert "file input" in error.lower()

    def test_validate_upload_file_div_invalid(self):
        """Test validating div element is not valid for upload_file."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "DIV",
            "attributes": {},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "upload_file",
            "div element",
            selected_element,
            [Mock()]
        )

        assert is_valid is False
        assert "file input" in error.lower()


class TestSelectionValidatorHoverMethod:
    """Test SelectionValidator hover method validation."""

    def test_validate_hover_visible_element_valid(self):
        """Test validating visible element for hover."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "BUTTON",
            "attributes": {},
            "isVisible": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "hover",
            "button element",
            selected_element,
            [Mock()]
        )

        assert is_valid is True

    def test_validate_hover_invisible_element_invalid(self):
        """Test validating invisible element for hover."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "BUTTON",
            "attributes": {},
            "isVisible": False
        }

        is_valid, error = validator.validate_selection_for_method(
            "hover",
            "hidden button",
            selected_element,
            [Mock()]
        )

        assert is_valid is False
        assert "visible" in error.lower()


class TestSelectionValidatorVisibility:
    """Test SelectionValidator visibility checks."""

    def test_validate_invisible_element_for_click(self):
        """Test validating invisible element for click."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "BUTTON",
            "attributes": {},
            "isVisible": False,
            "isClickable": True
        }

        is_valid, error = validator.validate_selection_for_method(
            "click",
            "hidden button",
            selected_element,
            [Mock()]
        )

        assert is_valid is False
        assert "visible" in error.lower()

    def test_validate_invisible_element_for_type_text(self):
        """Test validating invisible element for type_text."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "INPUT",
            "attributes": {"type": "text"},
            "isVisible": False
        }

        is_valid, error = validator.validate_selection_for_method(
            "type_text",
            "hidden input",
            selected_element,
            [Mock()]
        )

        assert is_valid is False
        assert "visible" in error.lower()

    def test_validate_invisible_element_for_wait_for_allowed(self):
        """Test that wait_for allows invisible elements."""
        validator = SelectionValidator()
        selected_element = {
            "tagName": "DIV",
            "attributes": {},
            "isVisible": False
        }

        is_valid, error = validator.validate_selection_for_method(
            "wait_for",
            "hidden element",
            selected_element,
            [Mock()]
        )

        assert is_valid is True


class TestSelectionValidatorElementCountWarnings:
    """Test SelectionValidator element count warnings."""

    def test_warn_single_for_plural_description(self):
        """Test warning when description expects multiple but found one."""
        validator = SelectionValidator()

        warnings = validator.validate_element_count_for_description(
            "all the buttons",
            element_count=1,
            is_plural_method=True
        )

        assert len(warnings) >= 1
        assert any("only 1" in w.lower() for w in warnings)

    def test_warn_multiple_for_single_description(self):
        """Test warning when description expects single but found multiple."""
        validator = SelectionValidator()

        warnings = validator.validate_element_count_for_description(
            "the one submit button",
            element_count=5,
            is_plural_method=False
        )

        assert len(warnings) >= 1
        assert any("one" in w.lower() or "single" in w.lower() for w in warnings)

    def test_warn_two_expected_found_different(self):
        """Test warning when description expects two but found different count."""
        validator = SelectionValidator()

        warnings = validator.validate_element_count_for_description(
            "two buttons",
            element_count=3,
            is_plural_method=False
        )

        assert len(warnings) >= 1
        assert any("two" in w.lower() or "pair" in w.lower() for w in warnings)

    def test_warn_multiple_expected_found_one(self):
        """Test warning when description expects multiple but found one."""
        validator = SelectionValidator()

        warnings = validator.validate_element_count_for_description(
            "multiple items",
            element_count=1,
            is_plural_method=False
        )

        assert len(warnings) >= 1
        assert any("multiple" in w.lower() or "only 1" in w.lower() for w in warnings)

    def test_warn_plural_method_found_one(self):
        """Test warning when plural method finds only one element."""
        validator = SelectionValidator()

        warnings = validator.validate_element_count_for_description(
            "items",
            element_count=1,
            is_plural_method=True
        )

        assert len(warnings) >= 1
        assert any("get_elements" in w.lower() or "get_element" in w.lower() for w in warnings)

    def test_warn_singular_method_found_multiple(self):
        """Test warning when singular method finds multiple elements."""
        validator = SelectionValidator()

        warnings = validator.validate_element_count_for_description(
            "button",
            element_count=5,
            is_plural_method=False
        )

        assert len(warnings) >= 1
        assert any("ambiguous" in w.lower() or "singular" in w.lower() for w in warnings)

    def test_no_warnings_for_matching_counts(self):
        """Test no warnings when counts match expectations."""
        validator = SelectionValidator()

        warnings = validator.validate_element_count_for_description(
            "button",
            element_count=1,
            is_plural_method=False
        )

        assert len(warnings) == 0
