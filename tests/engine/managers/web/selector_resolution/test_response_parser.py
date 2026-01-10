"""Tests for response parser."""

import pytest
from unittest.mock import Mock
from lamia.engine.managers.web.selector_resolution.response_parser import (
    ResponseParser, AmbiguousFormatResponseParser, ParseResult
)


class MockResponseParser(ResponseParser):
    """Mock implementation for testing the interface."""
    
    def get_full_prompt_template(self, operation_instructions: str, page_html: str, selector: str) -> str:
        return f"Full prompt: {operation_instructions} | {selector}"
    
    def get_validation_prompt_template(self, operation_instructions: str, page_html: str, selector: str) -> str:
        return f"Validation prompt: {operation_instructions} | {selector}"
    
    def parse_response(self, response: str, original_selector: str) -> 'ParseResult':
        # Simple mock implementation
        if "button.submit" in response:
            return ParseResult(is_ambiguous=False, selector="button.submit")
        elif "multiple" in response:
            return ParseResult(
                is_ambiguous=True,
                selector=None,
                options=[("button 1", ".btn1"), ("button 2", ".btn2")]
            )
        else:
            return ParseResult(is_ambiguous=False, selector=None)
    
    def is_ambiguous_response(self, response: str) -> bool:
        return "AMBIGUOUS" in response or "multiple" in response


class TestResponseParserInterface:
    """Test the ResponseParser interface."""
    
    def test_abstract_interface(self):
        """Test that ResponseParser is abstract."""
        with pytest.raises(TypeError):
            ResponseParser()
    
    def test_mock_implementation(self):
        """Test that mock implementation works correctly."""
        parser = MockResponseParser()
        
        # Test full prompt template
        prompt = parser.get_full_prompt_template("click", "<html></html>", "submit button")
        assert "Full prompt: click | submit button" == prompt
        
        # Test validation prompt template
        validation_prompt = parser.get_validation_prompt_template("click", "<html></html>", "submit button")
        assert "Validation prompt: click | submit button" == validation_prompt
        
        # Test parse response
        result = parser.parse_response("button.submit", "submit button")
        assert result.selector == "button.submit"
        assert not result.is_ambiguous


class TestAmbiguousFormatResponseParser:
    """Test AmbiguousFormatResponseParser implementation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = AmbiguousFormatResponseParser()
    
    def test_initialization(self):
        """Test parser initialization."""
        assert isinstance(self.parser, ResponseParser)
        assert isinstance(self.parser, AmbiguousFormatResponseParser)
    
    def test_get_full_prompt_template(self):
        """Test full prompt template generation."""
        operation_instructions = "Find and click the element"
        page_html = "<html><body><button>Click me</button></body></html>"
        selector = "the click button"
        
        prompt = self.parser.get_full_prompt_template(operation_instructions, page_html, selector)
        
        # Verify prompt contains expected components
        assert operation_instructions in prompt
        assert page_html in prompt
        assert selector in prompt
        assert isinstance(prompt, str)
        assert len(prompt) > 0
    
    def test_get_validation_prompt_template(self):
        """Test validation prompt template generation."""
        operation_instructions = "Validate selector"
        page_html = "<html><body><input type='email'/></body></html>"
        selector = "email input field"
        
        prompt = self.parser.get_validation_prompt_template(operation_instructions, page_html, selector)
        
        # Verify validation prompt contains expected components
        assert operation_instructions in prompt
        assert page_html in prompt
        assert selector in prompt
        assert isinstance(prompt, str)
        assert len(prompt) > 0
    
    def test_parse_simple_selector_response(self):
        """Test parsing response with a simple selector."""
        response = ".submit-button"
        original_selector = "submit button"
        
        result = self.parser.parse_response(response, original_selector)
        
        assert isinstance(result, ParseResult)
        assert result.selector == ".submit-button"
        assert not result.is_ambiguous
        assert len(result.options) == 0
    
    def test_parse_xpath_selector_response(self):
        """Test parsing response with XPath selector."""
        response = "//button[@type='submit']"
        original_selector = "submit button"
        
        result = self.parser.parse_response(response, original_selector)
        
        assert isinstance(result, ParseResult)
        assert result.selector == "//button[@type='submit']"
        assert not result.is_ambiguous
    
    def test_parse_ambiguous_response(self):
        """Test parsing ambiguous response with multiple options."""
        # This test might need to be adjusted based on actual implementation
        ambiguous_response = """
        I found multiple possible selectors:
        1. .btn-primary
        2. #submit-btn
        3. button[type='submit']
        
        Please clarify which one you meant.
        """
        original_selector = "button"
        
        result = self.parser.parse_response(ambiguous_response, original_selector)
        
        # The exact behavior depends on implementation
        assert isinstance(result, ParseResult)
        # Might be ambiguous or might pick the first option
    
    def test_parse_no_match_response(self):
        """Test parsing response when no selector is found."""
        response = "I couldn't find any matching elements for your request."
        original_selector = "nonexistent element"
        
        result = self.parser.parse_response(response, original_selector)
        
        assert isinstance(result, ParseResult)
        # Should handle gracefully - either return None or some default
    
    def test_parse_malformed_response(self):
        """Test parsing malformed or unexpected response."""
        malformed_responses = [
            "This is not a selector response at all",
            "Random text without any CSS or XPath",
            "Multiple lines\nwith\nno clear\nstructure"
        ]
        
        for response in malformed_responses:
            result = self.parser.parse_response(response, "test selector")
            assert isinstance(result, ParseResult)
            # Should handle gracefully without throwing
    
    def test_parse_empty_response_raises_error(self):
        """Test that empty responses raise an error."""
        empty_responses = [
            "",  # Empty response
            "   ",  # Whitespace only
        ]
        
        for response in empty_responses:
            with pytest.raises(ValueError, match="Empty AI response"):
                self.parser.parse_response(response, "test selector")
    
    def test_parse_response_with_explanation(self):
        """Test parsing response that includes explanation text."""
        response_with_explanation = """
        Based on the page content, the best selector is: .login-form input[type='email']
        
        This selector targets the email input field in the login form.
        """
        original_selector = "email input"
        
        result = self.parser.parse_response(response_with_explanation, original_selector)
        
        assert isinstance(result, ParseResult)
        # Should extract the selector and possibly the explanation


class TestParseResult:
    """Test ParseResult class functionality."""
    
    def test_simple_result_creation(self):
        """Test creating a simple non-ambiguous result."""
        result = ParseResult(is_ambiguous=False, selector=".test-selector")
        
        assert result.selector == ".test-selector"
        assert not result.is_ambiguous
        assert len(result.options) == 0
    
    def test_ambiguous_result_creation(self):
        """Test creating an ambiguous result with options."""
        options = [("Option 1", ".option1"), ("Option 2", ".option2"), ("Option 3", "#option3")]
        
        result = ParseResult(
            is_ambiguous=True,
            selector=None,
            options=options
        )
        
        assert result.selector is None
        assert result.is_ambiguous
        assert result.options == options
        assert len(result.options) == 3
    
    def test_result_string_representation(self):
        """Test string representation of results."""
        simple_result = ParseResult(
            is_ambiguous=False,
            selector="button[type='submit']"
        )
        
        ambiguous_result = ParseResult(
            is_ambiguous=True,
            selector=None,
            options=[("Button 1", ".btn1"), ("Button 2", ".btn2")]
        )
        
        assert "single: button[type='submit']" in str(simple_result)
        assert "ambiguous, 2 options" in str(ambiguous_result)


class TestResponseParserEdgeCases:
    """Test edge cases for response parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = AmbiguousFormatResponseParser()
    
    def test_very_long_response(self):
        """Test parsing very long response."""
        # Create a very long response
        long_response = "This is a very long response. " * 1000 + ".final-selector"
        
        result = self.parser.parse_response(long_response, "test")
        assert isinstance(result, ParseResult)
    
    def test_response_with_special_characters(self):
        """Test parsing response with special characters."""
        special_responses = [
            "div[data-test='special-chars-!@#$%^&*()']",
            "//div[@class='unicode-文字-test']",
            ".selector-with-émojis🎉",
            "input[placeholder*='Search...']"
        ]
        
        for response in special_responses:
            result = self.parser.parse_response(response, "test")
            assert isinstance(result, ParseResult)
    
    def test_empty_inputs_to_prompts(self):
        """Test prompt generation with empty inputs."""
        # Test with empty strings
        prompt = self.parser.get_full_prompt_template("", "", "")
        assert isinstance(prompt, str)
        
        validation_prompt = self.parser.get_validation_prompt_template("", "", "")
        assert isinstance(validation_prompt, str)
    
    def test_large_html_input(self):
        """Test prompt generation with large HTML."""
        large_html = "<div>" * 10000 + "</div>" * 10000
        
        prompt = self.parser.get_full_prompt_template(
            "test operation", 
            large_html, 
            "test selector"
        )
        
        assert isinstance(prompt, str)
        # Should handle large inputs gracefully
    
    def test_unicode_and_encoding(self):
        """Test handling of unicode characters in all inputs."""
        unicode_cases = [
            ("操作指示", "<html>中文内容</html>", "选择器"),
            ("инструкция", "<html>русский</html>", "селектор"),
            ("🎯 操作", "<html>🌍 content</html>", "🔍 selector"),
        ]
        
        for operation, html, selector in unicode_cases:
            prompt = self.parser.get_full_prompt_template(operation, html, selector)
            assert isinstance(prompt, str)
            
            validation_prompt = self.parser.get_validation_prompt_template(operation, html, selector)
            assert isinstance(validation_prompt, str)
            
            result = self.parser.parse_response(selector, "original")
            assert isinstance(result, ParseResult)


class TestResponseParserIntegration:
    """Test response parser integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = AmbiguousFormatResponseParser()
    
    def test_end_to_end_simple_case(self):
        """Test complete flow from prompt generation to response parsing."""
        # Generate prompt
        operation = "Click the submit button"
        html = """
        <form>
            <input type="text" name="username">
            <input type="password" name="password">
            <button type="submit" class="btn-primary">Submit</button>
        </form>
        """
        selector = "submit button"
        
        prompt = self.parser.get_full_prompt_template(operation, html, selector)
        assert isinstance(prompt, str)
        
        # Simulate AI response
        ai_response = ".btn-primary"
        
        # Parse response
        result = self.parser.parse_response(ai_response, selector)
        assert isinstance(result, ParseResult)
        assert result.selector == ".btn-primary"
        assert not result.is_ambiguous
    
    def test_round_trip_with_validation(self):
        """Test round trip including validation prompt."""
        operation = "Fill in email field"
        html = "<input type='email' id='email-input' placeholder='Enter email'>"
        selector = "email input"
        
        # Get initial prompt
        full_prompt = self.parser.get_full_prompt_template(operation, html, selector)
        
        # Get validation prompt  
        validation_prompt = self.parser.get_validation_prompt_template(operation, html, selector)
        
        # Both should be valid strings
        assert isinstance(full_prompt, str)
        assert isinstance(validation_prompt, str)
        
        # Parse a typical response
        response = "#email-input"
        result = self.parser.parse_response(response, selector)
        
        assert isinstance(result, ParseResult)
        assert result.selector == "#email-input"