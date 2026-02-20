"""Extracts unique CSS/XPath selectors from browser element handles."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

UNIQUE_CSS_SELECTOR_JS = """
function getUniqueSelector(element) {
    if (element.id) {
        return '#' + element.id;
    }

    if (element.className && typeof element.className === 'string') {
        var classes = element.className.split(' ').filter(function(c) { return c; }).join('.');
        if (classes) {
            var selector = element.tagName.toLowerCase() + '.' + classes;
            if (document.querySelectorAll(selector).length === 1) {
                return selector;
            }
        }
    }

    var path = [];
    var current = element;
    while (current && current !== document.body) {
        var sel = current.tagName.toLowerCase();
        if (current.id) {
            path.unshift('#' + current.id);
            break;
        }

        var sibling = current;
        var nth = 1;
        while (sibling.previousElementSibling) {
            sibling = sibling.previousElementSibling;
            if (sibling.tagName === current.tagName) {
                nth++;
            }
        }

        if (nth > 1 || current.nextElementSibling) {
            sel += ':nth-of-type(' + nth + ')';
        }

        path.unshift(sel);
        current = current.parentElement;
    }

    return path.join(' > ');
}
return getUniqueSelector(arguments[0]);
"""

XPATH_JS = """
function getXPath(element) {
    if (element.id) {
        return '//*[@id="' + element.id + '"]';
    }
    if (element === document.body) {
        return '/html/body';
    }

    var ix = 0;
    var siblings = element.parentNode.childNodes;
    for (var i = 0; i < siblings.length; i++) {
        var sibling = siblings[i];
        if (sibling === element) {
            return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
        }
        if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
            ix++;
        }
    }
}
return getXPath(arguments[0]);
"""


class UniqueSelectorExtractor:
    """Generates a unique CSS selector (or XPath fallback) for a browser element handle."""

    def __init__(self, browser_adapter: Any):
        self.browser = browser_adapter

    async def generate(self, element: Any) -> Optional[str]:
        """Return a unique selector string for *element*, or None on failure."""
        try:
            selector = await self.browser.execute_script(UNIQUE_CSS_SELECTOR_JS, element)
            if selector:
                return selector
        except Exception as e:
            logger.debug(f"CSS unique selector extraction failed: {e}")

        try:
            xpath = await self.browser.execute_script(XPATH_JS, element)
            if xpath:
                return xpath
        except Exception as e:
            logger.debug(f"XPath extraction failed: {e}")

        return None
