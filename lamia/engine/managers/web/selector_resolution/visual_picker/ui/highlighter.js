/**
 * Visual element highlighter for Lamia visual picker
 */
class LamiaElementHighlighter {
    constructor() {
        this.highlightedElement = null;
        this.originalStyles = new Map();
        this.overlayElement = null;
        this.instructionElement = null;
        this.elementFilter = null;
        this.onElementSelected = null;
        
        // Highlight styles
        this.highlightStyle = {
            outline: '3px solid #00ff00',
            backgroundColor: 'rgba(0, 255, 0, 0.1)',
            cursor: 'pointer',
            boxShadow: '0 0 10px rgba(0, 255, 0, 0.5)'
        };
        
        this.setupEventHandlers();
    }
    
    setupEventHandlers() {
        this.onMouseMove = this.onMouseMove.bind(this);
        this.onElementClick = this.onElementClick.bind(this);
        this.onKeyDown = this.onKeyDown.bind(this);
    }
    
    /**
     * Start the visual picker overlay
     */
    startPicker(options = {}) {
        const {
            instruction = "Click on the element you want to select",
            elementFilter = null,
            onSelected = null
        } = options;
        
        // elementFilter may arrive as a string from Python JSON serialization
        if (typeof elementFilter === 'string') {
            try {
                this.elementFilter = new Function('return ' + elementFilter)();
            } catch (e) {
                console.warn('Visual Picker: Could not parse elementFilter, ignoring:', e);
                this.elementFilter = null;
            }
        } else {
            this.elementFilter = elementFilter;
        }
        this.onElementSelected = onSelected;
        
        this.createOverlay(instruction);
        this.enableHighlighting();
        
        // Prevent page interactions
        document.body.style.userSelect = 'none';
        document.body.style.pointerEvents = 'auto';
    }
    
    /**
     * Stop the visual picker and clean up
     */
    stopPicker() {
        this.disableHighlighting();
        this.removeOverlay();
        this.clearHighlight();
        
        // Restore page interactions
        document.body.style.userSelect = '';
        document.body.style.pointerEvents = '';
    }
    
    /**
     * Create instruction overlay
     */
    createOverlay(instruction) {
        // Create overlay backdrop
        this.overlayElement = document.createElement('div');
        this.overlayElement.id = 'lamia-picker-overlay';
        this.overlayElement.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.3);
            z-index: 999999;
            pointer-events: none;
        `;
        
        // Create instruction box
        this.instructionElement = document.createElement('div');
        this.instructionElement.id = 'lamia-picker-instruction';
        this.instructionElement.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #333;
            color: white;
            padding: 15px 25px;
            border-radius: 8px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 16px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            z-index: 1000000;
            pointer-events: none;
            max-width: 80%;
            text-align: center;
        `;
        // Determine if this is a template selection (looking for "ONE example")
        const isTemplateSelection = instruction.includes('ONE example');
        
        this.instructionElement.innerHTML = `
            <div style="margin-bottom: 8px; font-weight: bold; color: #4CAF50;">${instruction}</div>
            ${isTemplateSelection ? 
                `<div style="font-size: 14px; margin-bottom: 4px; color: #FFC107;">💡 Click on ONE individual element as an example</div>
                <div style="font-size: 13px; margin-bottom: 4px; color: #2196F3;">🎯 I'll find other similar elements automatically</div>` :
                `<div style="font-size: 14px; margin-bottom: 4px; color: #FFC107;">💡 For multiple elements: Click on the container/area that contains ALL the elements you want</div>
                <div style="font-size: 13px; margin-bottom: 4px; color: #2196F3;">🎯 Look for a form section or div that wraps question-answer pairs</div>`
            }
            <div style="font-size: 12px; opacity: 0.8;">⏱️ You have 3 minutes to select • Press ESC to cancel</div>
        `;
        
        document.body.appendChild(this.overlayElement);
        document.body.appendChild(this.instructionElement);
    }
    
    /**
     * Remove overlay elements
     */
    removeOverlay() {
        if (this.overlayElement) {
            this.overlayElement.remove();
            this.overlayElement = null;
        }
        if (this.instructionElement) {
            this.instructionElement.remove();
            this.instructionElement = null;
        }
    }
    
    /**
     * Enable highlighting on mouse movement
     */
    enableHighlighting() {
        document.addEventListener('mousemove', this.onMouseMove, true);
        document.addEventListener('click', this.onElementClick, true);
        document.addEventListener('keydown', this.onKeyDown, true);
    }
    
    /**
     * Disable highlighting
     */
    disableHighlighting() {
        document.removeEventListener('mousemove', this.onMouseMove, true);
        document.removeEventListener('click', this.onElementClick, true);
        document.removeEventListener('keydown', this.onKeyDown, true);
    }
    
    /**
     * Handle mouse movement for highlighting
     */
    onMouseMove(event) {
        event.preventDefault();
        event.stopPropagation();
        
        const element = document.elementFromPoint(event.clientX, event.clientY);
        if (!element || this.isPickerElement(element)) {
            return;
        }
        
        // Check if element passes filter
        if (this.elementFilter) {
            try {
                if (!this.elementFilter(element)) {
                    this.clearHighlight();
                    return;
                }
            } catch (e) {
                console.warn('Visual Picker: Element filter error, allowing element:', e);
            }
        }
        
        this.highlightElement(element);
    }
    
    /**
     * Handle element click for selection
     */
    onElementClick(event) {
        event.preventDefault();
        event.stopPropagation();
        
        const clickTarget = document.elementFromPoint(event.clientX, event.clientY);
        console.log('Visual Picker: Click detected at', event.clientX, event.clientY,
                     'target:', clickTarget ? clickTarget.tagName + (clickTarget.className ? '.' + clickTarget.className : '') : 'null');
        
        const element = this.highlightedElement;
        if (!element) {
            console.log('Visual Picker: No highlighted element - click not registered.',
                        'Filter active:', !!this.elementFilter,
                        'Click target was:', clickTarget ? clickTarget.tagName : 'null');
            return;
        }
        
        console.log('Visual Picker: Element clicked', element.tagName, element.className);
        
        // Get element information
        const elementInfo = this.getElementInfo(element);
        console.log('Visual Picker: Element info collected', elementInfo);
        
        this.showSelectionFeedback(element);
        
        // Give user visual feedback before stopping
        setTimeout(() => {
            this.stopPicker();
            
            if (this.onElementSelected) {
                this.onElementSelected(elementInfo);
            }
            
            // Also send to Python via global callback
            if (window.lamiaElementSelected) {
                console.log('Visual Picker: Calling lamiaElementSelected callback');
                window.lamiaElementSelected(elementInfo);
            } else {
                console.log('Visual Picker: WARNING - lamiaElementSelected callback not found');
            }
        }, 500);
    }
    
    /**
     * Show visual feedback when element is selected
     */
    showSelectionFeedback(element) {
        const feedback = document.createElement('div');
        feedback.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #4CAF50;
            color: white;
            padding: 15px 25px;
            border-radius: 8px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 16px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            z-index: 1000001;
            pointer-events: none;
        `;
        feedback.textContent = '✓ Element Selected!';
        document.body.appendChild(feedback);
        
        setTimeout(() => feedback.remove(), 2000);
    }
    
    /**
     * Handle keyboard events
     */
    onKeyDown(event) {
        if (event.key === 'Escape') {
            event.preventDefault();
            event.stopPropagation();
            this.stopPicker();
            
            if (window.lamiaPickerCancelled) {
                window.lamiaPickerCancelled();
            }
        }
    }
    
    /**
     * Highlight an element
     */
    highlightElement(element) {
        if (element === this.highlightedElement) return;
        
        this.clearHighlight();
        
        this.highlightedElement = element;
        
        // Store original styles
        this.originalStyles.clear();
        for (const [property, value] of Object.entries(this.highlightStyle)) {
            this.originalStyles.set(property, element.style[property]);
            element.style[property] = value;
        }
    }
    
    /**
     * Clear current highlight
     */
    clearHighlight() {
        if (!this.highlightedElement) return;
        
        // Restore original styles
        for (const [property, originalValue] of this.originalStyles.entries()) {
            this.highlightedElement.style[property] = originalValue;
        }
        
        this.originalStyles.clear();
        this.highlightedElement = null;
    }
    
    /**
     * Check if element is part of picker UI
     */
    isPickerElement(element) {
        return element.id === 'lamia-picker-overlay' || 
               element.id === 'lamia-picker-instruction' ||
               element.closest('#lamia-picker-overlay') ||
               element.closest('#lamia-picker-instruction');
    }
    
    /**
     * Get comprehensive element information
     */
    getElementInfo(element) {
        return {
            tagName: element.tagName,
            id: element.id,
            className: element.className,
            xpath: this.getElementXPath(element),
            cssSelector: this.getElementCSSSelector(element),
            outerHTML: element.outerHTML,
            innerText: element.innerText || element.textContent || '',
            attributes: this.getElementAttributes(element),
            boundingBox: element.getBoundingClientRect(),
            isVisible: this.isElementVisible(element),
            isClickable: this.isElementClickable(element)
        };
    }
    
    /**
     * Get XPath for element
     */
    getElementXPath(element) {
        if (element.id) {
            return `//*[@id="${element.id}"]`;
        }
        
        let path = '';
        let current = element;
        
        while (current && current.nodeType === Node.ELEMENT_NODE) {
            let selector = current.tagName.toLowerCase();
            
            if (current.id) {
                selector = `*[@id="${current.id}"]`;
                path = `/${selector}${path}`;
                break;
            } else {
                let sibling = current;
                let index = 1;
                while (sibling = sibling.previousElementSibling) {
                    if (sibling.tagName === current.tagName) {
                        index++;
                    }
                }
                selector += `[${index}]`;
            }
            
            path = `/${selector}${path}`;
            current = current.parentElement;
        }
        
        return path;
    }
    
    /**
     * Get CSS selector for element
     */
    getElementCSSSelector(element) {
        if (element.id) {
            return `#${element.id}`;
        }
        
        if (element.className) {
            const classes = element.className.trim().split(/\\s+/).join('.');
            if (classes) {
                return `${element.tagName.toLowerCase()}.${classes}`;
            }
        }
        
        return element.tagName.toLowerCase();
    }
    
    /**
     * Get all element attributes
     */
    getElementAttributes(element) {
        const attrs = {};
        for (const attr of element.attributes) {
            attrs[attr.name] = attr.value;
        }
        return attrs;
    }
    
    /**
     * Check if element is visible
     */
    isElementVisible(element) {
        const style = window.getComputedStyle(element);
        return style.display !== 'none' && 
               style.visibility !== 'hidden' && 
               style.opacity !== '0';
    }
    
    /**
     * Check if element is clickable
     */
    isElementClickable(element) {
        const clickableTags = ['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'];
        const clickableRoles = ['button', 'link', 'tab', 'option'];
        
        return clickableTags.includes(element.tagName) ||
               clickableRoles.includes(element.getAttribute('role')) ||
               element.onclick !== null ||
               element.style.cursor === 'pointer';
    }
}

// Global picker instance
window.lamiaHighlighter = new LamiaElementHighlighter();

// API functions for Python integration
window.startLamiaPicker = function(options) {
    return window.lamiaHighlighter.startPicker(options);
};

window.stopLamiaPicker = function() {
    return window.lamiaHighlighter.stopPicker();
};