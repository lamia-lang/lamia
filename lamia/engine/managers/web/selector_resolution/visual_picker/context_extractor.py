"""HTML context extraction for visual picker elements."""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ElementContextExtractor:
    """
    Extracts HTML context for each element matched by a visual picker XPath.
    
    This enables resolution to work within smaller HTML segments rather than
    the entire page, improving accuracy and performance.
    """
    
    def __init__(self, browser_adapter):
        """Initialize context extractor.
        
        Args:
            browser_adapter: Browser adapter for executing JavaScript
        """
        self.browser = browser_adapter
    
    async def extract_contexts_for_xpath(self, xpath_selector: str) -> List[Dict[str, Any]]:
        """
        Extract HTML context for each element matched by the XPath selector.
        
        Args:
            xpath_selector: XPath selector that matches multiple elements
            
        Returns:
            List of contexts, each containing:
            - element_html: HTML content of the element
            - element_xpath: Unique XPath to this specific element
            - element_index: Index in the matched elements list
        """
        logger.info(f"Extracting HTML contexts for XPath: {xpath_selector}")
        
        # JavaScript to find all matching elements and extract their context
        js_code = f"""
        var xpath = "{xpath_selector}";
        var elements = document.evaluate(
            xpath, 
            document, 
            null, 
            XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, 
            null
        );
        
        var contexts = [];
        
        for (var i = 0; i < elements.snapshotLength; i++) {{
            var element = elements.snapshotItem(i);
            
            // Generate unique XPath for this specific element
            var uniqueXPath = xpath + "[" + (i + 1) + "]";
            
            // Extract HTML content
            var elementHTML = element.outerHTML;
            
            // Get some metadata
            var rect = element.getBoundingClientRect();
            
            contexts.push({{
                element_html: elementHTML,
                element_xpath: uniqueXPath,
                element_index: i,
                is_visible: rect.width > 0 && rect.height > 0,
                bounds: {{
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height
                }}
            }});
        }}
        
        return contexts;
        """
        
        try:
            contexts = await self.browser.execute_script(js_code)
            
            if not contexts:
                logger.warning(f"No contexts found for XPath: {xpath_selector}")
                return []
            
            logger.info(f"Extracted {len(contexts)} HTML contexts")
            
            # Filter out invisible or malformed elements
            valid_contexts = []
            for i, context in enumerate(contexts):
                if context.get('is_visible', False) and context.get('element_html'):
                    valid_contexts.append(context)
                else:
                    logger.debug(f"Skipping context {i}: not visible or no HTML")
            
            logger.info(f"Found {len(valid_contexts)} valid contexts")
            return valid_contexts
            
        except Exception as e:
            logger.error(f"Failed to extract contexts for XPath '{xpath_selector}': {e}")
            return []
    
    async def find_elements_within_context(
        self, 
        context: Dict[str, Any], 
        inner_selector: str
    ) -> List[Any]:
        """
        Find elements within a specific HTML context using an inner selector.
        
        Args:
            context: HTML context from extract_contexts_for_xpath()
            inner_selector: CSS or XPath selector to find within the context
            
        Returns:
            List of elements found within this context
        """
        element_xpath = context.get('element_xpath')
        if not element_xpath:
            logger.error("Context missing element_xpath")
            return []
        
        # Determine if inner_selector is CSS or XPath
        is_xpath = inner_selector.startswith('//') or inner_selector.startswith('/')
        
        if is_xpath:
            # For XPath, scope it to the context element
            scoped_selector = f"{element_xpath}{inner_selector}"
        else:
            # For CSS, we need to use querySelector within the context element
            js_code = f"""
            var contextElement = document.evaluate(
                "{element_xpath}", 
                document, 
                null, 
                XPathResult.FIRST_ORDERED_NODE_TYPE, 
                null
            ).singleNodeValue;
            
            if (contextElement) {{
                var found = contextElement.querySelectorAll("{inner_selector}");
                return Array.from(found).map(function(el) {{
                    return {{
                        tagName: el.tagName,
                        outerHTML: el.outerHTML,
                        textContent: el.textContent,
                        value: el.value || '',
                        id: el.id,
                        className: el.className
                    }};
                }});
            }}
            return [];
            """
            
            try:
                elements = await self.browser.execute_script(js_code)
                logger.debug(f"Found {len(elements)} elements with CSS selector '{inner_selector}' in context")
                return elements or []
            except Exception as e:
                logger.error(f"Failed to find elements with CSS selector in context: {e}")
                return []
        
        # For XPath, use the scoped selector with the browser adapter
        try:
            from lamia.internal_types import BrowserActionParams
            params = BrowserActionParams(selector=scoped_selector)
            elements = await self.browser.get_elements(params)
            logger.debug(f"Found {len(elements)} elements with XPath '{scoped_selector}'")
            return elements or []
        except Exception as e:
            logger.error(f"Failed to find elements with XPath in context: {e}")
            return []
    
    async def resolve_within_contexts(
        self,
        contexts: List[Dict[str, Any]],
        target_description: str,
        llm_manager
    ) -> Dict[str, Any]:
        """
        Resolve a target description within the extracted HTML contexts.
        
        This method finds the best matching elements across all contexts
        for a given natural language description.
        
        Args:
            contexts: List of HTML contexts from extract_contexts_for_xpath()
            target_description: Natural language description to resolve
            llm_manager: LLM manager for resolution
            
        Returns:
            Dictionary with resolution results across all contexts
        """
        logger.info(f"Resolving '{target_description}' within {len(contexts)} contexts")
        
        all_matches = []
        
        for i, context in enumerate(contexts):
            logger.debug(f"Processing context {i+1}/{len(contexts)}")
            
            # Use progressive resolution within this specific context
            context_matches = await self._resolve_in_single_context(
                context, target_description, llm_manager
            )
            
            if context_matches:
                # Add context metadata to matches
                for match in context_matches:
                    match['context_index'] = i
                    match['context_xpath'] = context.get('element_xpath')
                
                all_matches.extend(context_matches)
        
        logger.info(f"Found {len(all_matches)} total matches across all contexts")
        
        return {
            'matches': all_matches,
            'contexts_processed': len(contexts),
            'total_matches': len(all_matches)
        }
    
    async def _resolve_in_single_context(
        self,
        context: Dict[str, Any], 
        target_description: str,
        llm_manager
    ) -> List[Dict[str, Any]]:
        """Resolve target description within a single HTML context."""
        
        context_html = context.get('element_html', '')
        context_xpath = context.get('element_xpath', '')
        
        if not context_html:
            return []
        
        # Limit HTML size for LLM processing
        if len(context_html) > 1500:
            context_html = context_html[:1500] + "..."
        
        # Generate selectors for the target within this context
        prompt = f"""Find CSS selectors for "{target_description}" within this HTML segment:

HTML CONTEXT:
{context_html}

TASK: Generate 2-3 CSS selectors that will find "{target_description}" within this HTML.

RULES:
- Return only selectors that would work within this HTML segment
- Focus on specific attributes, classes, or structural patterns
- Prefer selectors that match the target description precisely

Return as JSON array: ["selector1", "selector2"]"""

        try:
            from lamia.interpreter.commands import LLMCommand
            llm_command = LLMCommand(prompt=prompt)
            result = await llm_manager.execute(llm_command)
            
            import json
            selectors = json.loads(result.validated_text)
            
            matches = []
            for selector in selectors[:3]:  # Try top 3 selectors
                elements = await self.find_elements_within_context(context, selector)
                if elements:
                    matches.extend([{
                        'selector': selector,
                        'element': el,
                        'found_in_context': True
                    } for el in elements])
            
            return matches
            
        except Exception as e:
            logger.error(f"Failed to resolve in context: {e}")
            return []