"""Parser for classifying selector syntax."""

from enum import Enum
from lxml import etree
from cssselect import parse

HTML_TAG_NAMES = frozenset({
    "a", "abbr", "address", "area", "article", "aside", "audio",
    "b", "base", "bdi", "bdo", "blockquote", "body", "br", "button",
    "canvas", "caption", "cite", "code", "col", "colgroup",
    "data", "datalist", "dd", "del", "details", "dfn", "dialog", "div", "dl", "dt",
    "em", "embed",
    "fieldset", "figcaption", "figure", "footer", "form",
    "h1", "h2", "h3", "h4", "h5", "h6", "head", "header", "hgroup", "hr", "html",
    "i", "iframe", "img", "input", "ins",
    "kbd",
    "label", "legend", "li", "link",
    "main", "map", "mark", "menu", "meta", "meter",
    "nav", "noscript",
    "object", "ol", "optgroup", "option", "output",
    "p", "param", "picture", "pre", "progress",
    "q",
    "rp", "rt", "ruby",
    "s", "samp", "script", "search", "section", "select", "slot", "small",
    "source", "span", "strong", "style", "sub", "summary", "sup", "svg",
    "table", "tbody", "td", "template", "textarea", "tfoot", "th", "thead",
    "time", "title", "tr", "track",
    "u", "ul",
    "var", "video",
    "wbr",
})


class SelectorType(Enum):
    """Types of selectors that can be parsed."""
    VALID_CSS = "valid_css"
    VALID_XPATH = "valid_xpath"  
    INVALID_CSS = "invalid_css"
    INVALID_XPATH = "invalid_xpath"
    NATURAL_LANGUAGE = "natural_language"


class SelectorParser:
    """Parses and classifies selectors to determine if they need AI resolution."""
    
    def classify(self, selector: str) -> SelectorType:
        """Classify a selector string into one of the SelectorType categories.
        
        Args:
            selector: The selector string to classify
            
        Returns:
            SelectorType indicating the classification result
            
        Raises:
            ValueError: If selector is empty or None
        """
        if not selector or not selector.strip():
            raise ValueError("Selector cannot be empty or None")
            
        selector = selector.strip()
        
        # Check for XPath patterns first (more specific)
        if self._looks_like_xpath(selector):
            if self._is_valid_xpath(selector):
                return SelectorType.VALID_XPATH
            else:
                return SelectorType.INVALID_XPATH
                
        # Check for CSS patterns
        if self._looks_like_css(selector):
            if self._is_valid_css(selector):
                return SelectorType.VALID_CSS
            else:
                return SelectorType.INVALID_CSS
                
        # Default to natural language if no patterns match
        return SelectorType.NATURAL_LANGUAGE
    
    def _looks_like_xpath(self, selector: str) -> bool:
        """Check if selector has XPath-like structure."""
        return (
            selector.startswith('//') or 
            selector.startswith('/') or 
            selector.startswith('./') or
            '@' in selector or
            'ancestor::' in selector or 
            'descendant::' in selector or
            'following::' in selector or
            'preceding::' in selector
        )
    
    def _looks_like_css(self, selector: str) -> bool:
        """Check if selector has CSS-like structure."""
        css_chars = {'.', '#', '[', ']', ':', '>', '+', '~', '*'}
        has_css_chars = any(char in selector for char in css_chars)
        if has_css_chars:
            return True
        is_simple_identifier = selector.replace('-', '').replace('_', '').isalnum() and ' ' not in selector
        if is_simple_identifier:
            return selector.lower() in HTML_TAG_NAMES
        return False
    
    def _is_valid_xpath(self, selector: str) -> bool:
        """Validate XPath syntax using lxml parser."""
        try:
            etree.XPath(selector)
            return True
        except Exception:
            return False
    
    def _is_valid_css(self, selector: str) -> bool:
        """Validate CSS selector syntax using cssselect parser."""
        try:
            parse(selector)
            return True
        except Exception:
            return False