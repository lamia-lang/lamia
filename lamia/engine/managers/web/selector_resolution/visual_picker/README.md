# Visual Element Picker

Interactive element selection for Lamia web automation with visual UI overlay.

## Overview

The Visual Element Picker solves the core problem of AI selector ambiguity by letting users **visually select** the exact elements they want to interact with. Instead of guessing what "question and answer grouped together" means, the user simply clicks on the area they want.

## Key Benefits

- **Eliminates Ambiguity**: User shows exactly what they want
- **Works with All Web Methods**: click, type_text, get_element, get_elements, etc.
- **Smart Validation**: Method-specific validation ensures selections make sense  
- **Progressive Scope**: Automatically expands search scope if needed (for plural methods)
- **Intelligent Caching**: Remembers selections for future runs
- **Fallback Strategy**: Only activates when AI resolution fails

## How It Works

### 1. Trigger Condition
Visual picker activates when:
- Natural language selector fails with progressive AI resolution
- Visual picker is enabled in config
- Browser is available for overlay injection

### 2. User Experience Flow
```
User: web.get_element("submit button")
↓
AI tries progressive resolution first
↓ 
AI fails to resolve unambiguously
↓
🎯 Opens visual picker overlay
↓
User clicks on desired button
↓
AI generates scoped selectors for that specific area
↓
Selection cached for future use
```

### 3. Method-Specific Behavior

#### Singular Methods (`click`, `type_text`, `get_element`)
- Shows instruction like "👆 Click on the element you want to CLICK"
- Highlights only relevant elements (clickable for click, inputs for type_text)
- Validates selection is appropriate for the method
- Returns single element

#### Plural Methods (`get_elements`)  
- Shows instruction like "🔢 Click on area containing multiple elements"
- Focuses on container selection rather than individual elements
- Progressive scope expansion if no elements found
- Warns if only one element found

### 4. Smart Element Filtering
Each method highlights only relevant elements:

- **click**: Buttons, links, clickable elements
- **type_text**: Text inputs, textareas, contenteditable  
- **select_option**: Select dropdowns, comboboxes
- **upload_file**: File input elements
- **get_element/get_elements**: All elements (no filter)

## Configuration

```yaml
# config.yaml
web:
  visual_picker:
    enabled: true                    # Enable/disable visual picker
    disabled_for_operations: []      # Disable for specific operations
    cache_enabled: true              # Cache visual selections
    timeout: 300                     # Selection timeout (seconds)
```

## Usage Examples

### Basic Usage
```python
# If AI resolution fails, visual picker automatically activates
button = web.get_element("submit button")
```

### Configuration Control  
```python
# Disable visual picker entirely
config = {
    "web": {
        "visual_picker": {
            "enabled": False
        }
    }
}

# Disable for specific operations
config = {
    "web": {
        "visual_picker": {
            "disabled_for_operations": ["hover", "wait_for"]
        }
    }
}
```

### Cache Management
```python
# Visual selections are automatically cached
# First time - shows visual picker
elements = web.get_elements("question and answer fields")

# Subsequent times - uses cached selection  
elements = web.get_elements("question and answer fields")  # Instant!
```

## Technical Architecture

### Core Components

```
visual_picker/
├── picker.py              # Main orchestrator
├── overlay.py             # Browser JavaScript injection
├── cache.py               # Selection caching 
├── validation.py          # Selection validation
├── strategies/
│   ├── singular_strategy.py   # Single element selection
│   ├── plural_strategy.py     # Multiple element selection  
│   └── action_strategy.py     # Method-specific handlers
└── ui/
    ├── highlighter.js         # Element highlighting
    └── overlay.css            # Visual styling
```

### Integration Points

1. **Selector Resolution Service**: Falls back to visual picker when AI fails
2. **Browser Manager**: Provides browser adapter for overlay injection
3. **Web Manager**: Passes config and operation context
4. **Cache System**: Stores visual selections alongside AI resolutions

## JavaScript Overlay Features

### Element Highlighting
- **Hover Effects**: Elements light up green on mouseover
- **Smart Filtering**: Only highlights relevant elements per method
- **Visual Feedback**: Clear indication of what's selectable
- **Keyboard Support**: ESC to cancel selection

### User Interface
- **Clear Instructions**: Method-specific guidance text
- **Progress Indication**: Shows what's happening
- **Error Handling**: Validates selections and shows helpful errors
- **Accessibility**: Keyboard navigation support

### Selection Information
Captures comprehensive element data:
- **Tag name and attributes**  
- **XPath and CSS selectors**
- **Bounding box and visibility**
- **Element relationships**
- **Interaction capabilities**

## Progressive Scope Expansion

For `get_elements()` when container selection finds no elements:

1. **Try Original Container**: Check selected area for elements
2. **Expand 1 Level**: Try parent container  
3. **Expand 2 Levels**: Try grandparent container
4. **Expand 3 Levels**: Try great-grandparent container
5. **User Confirmation**: Ask if expanded scope is acceptable

```
User clicks on empty div
↓
No elements found in div  
↓
Try parent container → Found 3 elements
↓ 
Ask user: "Found 3 elements in broader area. Use this scope?"
↓
User accepts → Cache expanded selection
```

## Error Handling

### Validation Errors
- **Wrong Element Type**: Selected input for click action
- **Invisible Elements**: Selected hidden elements for visible actions  
- **Disabled Elements**: Selected disabled elements
- **Read-only Inputs**: Selected readonly fields for type_text

### Recovery Strategies
- **Clear Error Messages**: Explain what went wrong
- **Helpful Suggestions**: Guide user to correct element type
- **Retry Logic**: Allow re-selection after validation failure
- **Graceful Degradation**: Fall back to manual selector entry

## Performance Considerations

### Efficiency Features
- **Lazy Loading**: Components only loaded when needed
- **Smart Caching**: Selections cached by (method, description, URL)  
- **Minimal JavaScript**: Lightweight overlay injection
- **Fast Polling**: Efficient user interaction detection

### Resource Management
- **Automatic Cleanup**: Removes overlays and event handlers
- **Memory Management**: Clears references when done
- **Timeout Protection**: Prevents hanging on user inaction
- **Error Recovery**: Cleans up on failures

## Debugging

### Logging
```python
import logging
logging.getLogger('lamia.engine.managers.web.selector_resolution.visual_picker').setLevel(logging.DEBUG)
```

### Cache Inspection
```python
# View cached visual selections
stats = visual_picker.cache.get_stats()
entries = visual_picker.cache.list_entries(method_name="click")
```

### JavaScript Console
```javascript
// Check picker state
window.lamiaHighlighter
window.lamiaSelectionResult

// Manual picker control  
window.startLamiaPicker({instruction: "Test"})
window.stopLamiaPicker()
```

## Future Enhancements

1. **Multi-Element Selection**: Select multiple individual elements
2. **Visual Validation**: Preview what will be found before confirming
3. **Selection Recording**: Record user selection paths for replay
4. **Advanced Filtering**: More sophisticated element filtering options
5. **Mobile Support**: Touch-friendly selection for mobile browsers
6. **Accessibility**: Screen reader and keyboard-only support

## Conclusion

The Visual Element Picker transforms web automation from guesswork to precision. Users show exactly what they want, AI handles the complexity, and everything gets cached for speed. It's the perfect bridge between human intuition and AI automation.