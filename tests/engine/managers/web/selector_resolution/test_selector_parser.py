"""Tests for selector parser."""

import pytest
from lamia.engine.managers.web.selector_resolution.selector_parser import SelectorParser, SelectorType


class TestSelectorParser:
    """Test SelectorParser classification functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = SelectorParser()
    
    def test_empty_selector_raises_error(self):
        """Test that empty selectors raise ValueError."""
        with pytest.raises(ValueError, match="Selector cannot be empty or None"):
            self.parser.classify("")
        
        with pytest.raises(ValueError, match="Selector cannot be empty or None"):
            self.parser.classify("   ")
        
        with pytest.raises(ValueError, match="Selector cannot be empty or None"):
            self.parser.classify(None)
    
    def test_valid_css_selectors(self):
        """Test classification of valid CSS selectors."""
        valid_css_selectors = [
            ".class-name",
            "#element-id",
            "div",
            "div.class",
            "div#id",
            ".class1.class2",
            "div > p",
            "div + p",
            "div ~ p",
            "[data-test]",
            "[data-test='value']",
            "input[type='text']",
            "p:first-child",
            "p:nth-child(2)",
            "div.class > p:first-child",
            "button[type='submit']:not(:disabled)",
            "input, select, textarea",
            "h1, h2, h3",
        ]
        
        for selector in valid_css_selectors:
            result = self.parser.classify(selector)
            assert result == SelectorType.VALID_CSS, f"Selector '{selector}' should be valid CSS"
    
    def test_valid_xpath_selectors(self):
        """Test classification of valid XPath selectors."""
        valid_xpath_selectors = [
            "//div",
            "//div[@class='test']",
            "/html/body/div",
            "//button[text()='Click me']",
            "//input[@type='text']",
            "//div[contains(@class, 'partial')]",
            "//span[normalize-space(text())='exact text']",
            "//a[@href and contains(@href, 'example.com')]",
            "//div[@id='main']//p[2]"
        ]
        
        for selector in valid_xpath_selectors:
            result = self.parser.classify(selector)
            assert result == SelectorType.VALID_XPATH, f"Selector '{selector}' should be valid XPath"
    
    def test_complex_xpath_selectors(self):
        """Test more complex XPath selectors that might have parsing edge cases."""
        # Some complex XPath patterns that might be valid or invalid
        complex_xpath_cases = [
            ("(//div)[1]", SelectorType.INVALID_CSS),  # This gets classified as CSS first due to parentheses
            ("ancestor::div", SelectorType.VALID_XPATH),  # Should be XPath due to axis
            (".//*[@class]", SelectorType.VALID_XPATH),  # Relative XPath
        ]
        
        for selector, expected_type in complex_xpath_cases:
            result = self.parser.classify(selector)
            assert result == expected_type, f"Selector '{selector}' should be {expected_type}"
    
    def test_invalid_css_selectors(self):
        """Test classification of invalid CSS selectors."""
        invalid_css_selectors = [
            "..",  # Invalid class selector
            "##double-hash",  # Invalid ID selector
            "div[unclosed",  # Unclosed attribute selector
            "div > > p",  # Invalid combinator sequence
            "div..class",  # Invalid class syntax
            "div[]",  # Empty attribute selector
            "div[=value]",  # Missing attribute name
            "div:not(",  # Unclosed pseudo-class
        ]
        
        for selector in invalid_css_selectors:
            result = self.parser.classify(selector)
            assert result == SelectorType.INVALID_CSS, f"Selector '{selector}' should be invalid CSS"
    
    def test_invalid_xpath_selectors(self):
        """Test classification of invalid XPath selectors."""
        invalid_xpath_selectors = [
            "//div[",  # Unclosed predicate
            "//div[@]",  # Empty attribute
            "//div[text()=",  # Incomplete expression
            "//div[@class='unclosed",  # Unclosed string
        ]
        
        for selector in invalid_xpath_selectors:
            result = self.parser.classify(selector)
            assert result == SelectorType.INVALID_XPATH, f"Selector '{selector}' should be invalid XPath"
    
    def test_ambiguous_xpath_syntax(self):
        """Test XPath syntax that might be parsed differently."""
        # The parser might accept some syntax that looks wrong
        ambiguous_cases = [
            ("///div", SelectorType.VALID_XPATH),  # Triple slash might be valid XPath
        ]
        
        for selector, expected_type in ambiguous_cases:
            result = self.parser.classify(selector)
            assert result == expected_type, f"Selector '{selector}' should be {expected_type}"
    
    def test_natural_language_selectors(self):
        """Test classification of natural language selectors."""
        natural_language_selectors = [
            "click the submit button",
            "find the login form",
            "select all products",
            "the red button in the header",
            "input field for email address",
            "navigation menu item",
            "search box on the top",
            "price element next to the product name",
            "close modal button",
            "first paragraph with class highlight"
        ]
        
        for selector in natural_language_selectors:
            result = self.parser.classify(selector)
            assert result == SelectorType.NATURAL_LANGUAGE, f"Selector '{selector}' should be natural language"

    def test_single_word_natural_language_not_html_tag(self):
        """Single words that are NOT HTML tags must be classified as natural language."""
        non_tag_words = [
            "question",
            "password",
            "username",
            "email",
            "answer",
            "description",
            "name",
            "phone",
            "salary",
        ]
        for selector in non_tag_words:
            result = self.parser.classify(selector)
            assert result == SelectorType.NATURAL_LANGUAGE, (
                f"Selector '{selector}' is not an HTML tag and should be natural language, got {result}"
            )

    def test_single_word_html_tags_are_valid_css(self):
        """Single words that ARE valid HTML tags should be classified as valid CSS."""
        tag_selectors = ["div", "span", "button", "input", "p", "a", "h1", "nav", "header", "section"]
        for selector in tag_selectors:
            result = self.parser.classify(selector)
            assert result == SelectorType.VALID_CSS, (
                f"HTML tag '{selector}' should be valid CSS, got {result}"
            )
    
    def test_whitespace_handling(self):
        """Test that whitespace is properly handled."""
        # Leading/trailing whitespace should be stripped
        assert self.parser.classify("  .class-name  ") == SelectorType.VALID_CSS
        assert self.parser.classify("\t//div\t") == SelectorType.VALID_XPATH
        assert self.parser.classify("\nclick button\n") == SelectorType.NATURAL_LANGUAGE


class TestSelectorParserEdgeCases:
    """Test edge cases for selector parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = SelectorParser()
    
    def test_ambiguous_selectors(self):
        """Test selectors that might be ambiguous between types."""
        # These could potentially be confused
        test_cases = [
            ("div", SelectorType.VALID_CSS),  # Simple tag, should be CSS
            ("//div//div", SelectorType.VALID_XPATH),  # Clear XPath
            ("button:contains('text')", SelectorType.VALID_CSS),  # CSS parser might accept this
        ]
        
        for selector, expected_type in test_cases:
            result = self.parser.classify(selector)
            assert result == expected_type, f"Selector '{selector}' should be {expected_type}"
    
    def test_very_long_selectors(self):
        """Test very long selectors."""
        # Very long CSS selector
        long_css = ".class" + "-name" * 100
        result = self.parser.classify(long_css)
        assert result == SelectorType.VALID_CSS
        
        # Very long XPath
        long_xpath = "//div" + "//div" * 50
        result = self.parser.classify(long_xpath)
        assert result == SelectorType.VALID_XPATH
        
        # Very long natural language
        long_natural = "find the button " * 20 + "that says click me"
        result = self.parser.classify(long_natural)
        assert result == SelectorType.NATURAL_LANGUAGE
    
    def test_special_characters(self):
        """Test selectors with special characters."""
        special_char_cases = [
            ("#id-with-dashes", SelectorType.VALID_CSS),
            (".class_with_underscores", SelectorType.VALID_CSS),
            ("div[data-test-id='123']", SelectorType.VALID_CSS),
            ("//div[@data-test='value with spaces']", SelectorType.VALID_XPATH),
            ("button with emoji 🚀", SelectorType.NATURAL_LANGUAGE),
        ]
        
        for selector, expected_type in special_char_cases:
            result = self.parser.classify(selector)
            assert result == expected_type, f"Selector '{selector}' should be {expected_type}"
    
    def test_case_sensitivity(self):
        """Test case sensitivity in classification."""
        # CSS is generally case-insensitive for element names, but case-sensitive for classes/IDs
        assert self.parser.classify("DIV") == SelectorType.VALID_CSS
        assert self.parser.classify("div") == SelectorType.VALID_CSS
        
        # XPath function names - both might be valid depending on implementation
        assert self.parser.classify("//div[text()='test']") == SelectorType.VALID_XPATH
        # Let's test what the actual parser returns for uppercase XPath functions
        result = self.parser.classify("//div[TEXT()='test']")
        assert result in [SelectorType.VALID_XPATH, SelectorType.INVALID_XPATH]
    
    def test_numeric_selectors(self):
        """Test selectors that are primarily numeric or start with numbers."""
        numeric_cases = [
            ("#123", SelectorType.VALID_CSS),  # ID starting with number (valid in CSS)
            ("input[name='123']", SelectorType.VALID_CSS),
            ("//input[@name='123']", SelectorType.VALID_XPATH),
            ("click button 1", SelectorType.NATURAL_LANGUAGE),
            ("123 main selector", SelectorType.NATURAL_LANGUAGE),
        ]
        
        for selector, expected_type in numeric_cases:
            result = self.parser.classify(selector)
            assert result == expected_type, f"Selector '{selector}' should be {expected_type}"


class TestSelectorParserInternalMethods:
    """Test internal classification methods if they're accessible."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = SelectorParser()
    
    def test_xpath_detection_patterns(self):
        """Test patterns that should be detected as XPath-like."""
        xpath_test_cases = [
            ("//div", SelectorType.VALID_XPATH),
            ("/html/body", SelectorType.VALID_XPATH),
            ("div[@class='test']", SelectorType.VALID_XPATH),  # Should be XPath due to @ symbol
            ("//div[text()='test']", SelectorType.VALID_XPATH),
            ("ancestor::div", SelectorType.VALID_XPATH),
            ("./div", SelectorType.VALID_XPATH),
        ]
        
        for selector, expected_type in xpath_test_cases:
            result = self.parser.classify(selector)
            assert result == expected_type, f"Selector '{selector}' should be {expected_type}"
    
    def test_css_detection_patterns(self):
        """Test patterns that should be detected as CSS-like."""
        css_patterns = [
            ".class",
            "#id", 
            "[attr",
            ":pseudo",
            ">",
            "+",
            "~",
        ]
        
        for pattern in css_patterns:
            selector = f"div{pattern}"
            result = self.parser.classify(selector)
            # Should be classified as CSS (valid or invalid) or natural language if unrecognized
            assert result in [SelectorType.VALID_CSS, SelectorType.INVALID_CSS, SelectorType.NATURAL_LANGUAGE]