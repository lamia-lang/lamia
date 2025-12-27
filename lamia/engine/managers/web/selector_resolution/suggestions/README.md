# AI-Powered Selector Suggestion System

## Overview

This document describes the AI-powered selector suggestion system that automatically provides intelligent alternatives when web selectors fail to find elements.

## Problem Statement

Previously, when a CSS selector failed to find an element:
1. The error was incorrectly classified as **permanent** (non-retryable)
2. Users received generic "element not found" errors with no guidance
3. No AI-powered suggestions were provided

## Solution Architecture

### 1. Browser Error Classification

**File**: `lamia/adapters/error_classifiers/browser.py`

Created a specialized `BrowserErrorClassifier` that correctly handles browser automation errors:

- **Transient Errors** (retryable):
  - `element not found`
  - `not visible`
  - `not clickable`
  - `timeout`
  - `stale element`
  - DOM timing issues

- **Permanent Errors** (non-retryable):
  - `not initialized`
  - `invalid session`
  - `browser not supported`
  - `invalid selector syntax`

This ensures "element not found" errors are retried before escalating to AI suggestions.

### 2. AI Selector Suggestion Service

**File**: `lamia/engine/managers/web/selector_resolution/selector_suggestion_service.py`

The `SelectorSuggestionService` provides intelligent selector alternatives:

```python
class SelectorSuggestionService:
    """Provides AI-powered suggestions when selectors fail to find elements."""
    
    async def suggest_alternative_selectors(
        self,
        failed_selector: str,
        operation_type: str,
        max_suggestions: int = 3
    ) -> List[Tuple[str, str]]:
        """Generate alternative selector suggestions using AI."""
```

**Features**:
- Analyzes page HTML context
- Considers operation type (click, type, hover, etc.)
- Returns up to 3 ranked suggestions
- Provides human-readable descriptions for each suggestion

### 3. Integration with Retry System

**File**: `lamia/adapters/retry/adapter_wrappers/browser.py`

Enhanced `RetryingBrowserAdapter` to:
1. Accept optional `suggestion_service` parameter
2. Catch "element not found" errors after retries exhausted
3. Automatically invoke AI suggestion service
4. Present formatted suggestions in error messages

```python
async def _handle_all_selectors_failed(...):
    """Handle case when all selectors failed by providing AI suggestions."""
    # Try to get AI suggestions if service is available
    if self.suggestion_service:
        suggestions = await self.suggestion_service.suggest_alternative_selectors(...)
        if suggestions:
            # Build helpful error message with suggestions
```

### 4. Browser Manager Integration

**File**: `lamia/engine/managers/web/browser_manager.py`

The `BrowserManager` now:
1. Creates `SelectorSuggestionService` with LLM manager
2. Passes it to the browser adapter during initialization
3. Provides page HTML context for AI analysis

## User Experience

### Before

```
ERROR - Element '.jobs-search-results__list .job-card-container:nth-child(1)' not found
```

### After

```
❌ Element not found after all retries
Operation: click
Tried selectors: .jobs-search-results__list .job-card-container:nth-child(1)

🤖 AI-Powered Suggestions:

  1. First job card in the search results list
     Selector: .jobs-search-results-list__list-item:first-child

  2. Job card container with job link
     Selector: .job-card-container--clickable

  3. Primary job listing card
     Selector: div[data-job-id]:first-of-type

💡 Try replacing your selector with one of the suggestions above.
   The AI analyzed the page HTML and found these potential matches.
```

## How It Works

### Flow Diagram

```
1. User provides selector
   ↓
2. Browser action attempts to find element
   ↓
3. Element not found → Classified as TRANSIENT
   ↓
4. Retry handler retries up to max_attempts
   ↓
5. All retries exhausted
   ↓
6. RetryingBrowserAdapter catches error
   ↓
7. Calls SelectorSuggestionService
   ↓
8. AI analyzes page HTML + operation type
   ↓
9. Returns 3 ranked alternative selectors
   ↓
10. Error message includes suggestions
```

### AI Prompt Strategy

The suggestion service creates operation-aware prompts:

```python
def _create_suggestion_prompt(...):
    prompt = f"""The following CSS selector FAILED to find any elements on the page:
    FAILED SELECTOR: {failed_selector}
    
    OPERATION: {operation_desc}
    
    PAGE HTML:
    {page_html[:15000]}
    
    Your task is to analyze the HTML and suggest up to {max_suggestions} 
    alternative CSS selectors that might work.
    
    Look for:
    1. Elements with similar attributes, classes, or IDs
    2. Elements that match the likely intent of the failed selector
    3. Elements appropriate for the operation type
    4. Common selector issues (typos, outdated classes, changed structure)
    
    Return your suggestions in this exact format:
    SUGGESTION 1: "Description" -> css_selector_here
    SUGGESTION 2: "Description" -> css_selector_here
    """
```

### Response Parsing

The service parses AI responses into structured suggestions:

```python
def _parse_suggestions(response: str, failed_selector: str):
    """Parse AI response into list of (description, selector) tuples."""
    # Extracts suggestions from format:
    # SUGGESTION 1: "description" -> selector
    # Filters out duplicates of the failed selector
    # Returns ranked list of alternatives
```

## Configuration

### Enabling/Disabling

The suggestion service is automatically enabled when:
- LLM manager is available
- Browser operations fail with element not found

No additional configuration required - it works out of the box!

### Customization

To customize suggestion behavior, modify:

```python
# In browser_manager.py
self._selector_suggestion_service = SelectorSuggestionService(
    llm_manager=llm_manager,
    get_page_html_func=self._get_current_page_html
)

# Change max_suggestions in adapter_wrappers/browser.py
suggestions = await self.suggestion_service.suggest_alternative_selectors(
    failed_selector=selectors[0],
    operation_type=method_name,
    max_suggestions=3  # Change this value
)
```

## Benefits

### 1. Faster Debugging
Users get actionable suggestions immediately instead of trial-and-error.

### 2. Context-Aware
AI analyzes actual page HTML, not just guessing based on selector text.

### 3. Operation-Specific
Suggestions are tailored to the operation (click, type, hover, etc.).

### 4. Learning Aid
Descriptions help users understand why alternative selectors work.

### 5. Reduced Support Load
Self-service debugging reduces need for manual intervention.

## Integration with Existing Systems

### Reuses Existing Infrastructure

The solution leverages existing components:

- **LLM Manager**: For AI queries
- **Selector Resolution Service**: For natural language → CSS conversion
- **Retry Handler**: For transient error classification
- **Browser Adapters**: For page HTML access

### Clean Separation of Concerns

```
BrowserManager
  ├── Creates SelectorSuggestionService
  ├── Passes to RetryingBrowserAdapter
  └── Provides page HTML context

RetryingBrowserAdapter
  ├── Handles retry logic
  ├── Catches exhausted retries
  └── Invokes suggestion service

SelectorSuggestionService
  ├── Creates AI prompts
  ├── Parses AI responses
  └── Returns ranked suggestions
```

## Future Enhancements

### 1. Suggestion Caching
Cache successful suggestions to avoid repeated AI calls for same failures.

### 2. User Feedback Loop
Learn from which suggestions users actually adopt.

### 3. Multi-Language Support
Support XPath and other selector formats in suggestions.

### 4. Confidence Scores
Add confidence scores to each suggestion based on element similarity.

### 5. Interactive Mode
Allow users to preview suggestions before applying them.

## Troubleshooting

### No Suggestions Shown

**Cause**: LLM manager not available or API key missing

**Solution**: Ensure valid API key configured:
```bash
export OPENAI_API_KEY=your-key-here
# or
export ANTHROPIC_API_KEY=your-key-here
```

### Generic Suggestions

**Cause**: Page HTML not accessible

**Solution**: Ensure browser adapter is initialized and page is loaded before action.

### Suggestions Don't Work

**Cause**: Dynamic content or wrong operation type

**Solution**: 
- Add explicit wait before action
- Try natural language selector instead
- Check if element loads asynchronously

## Testing

### Unit Tests

Test individual components:

```python
# Test error classification
def test_browser_error_classifier():
    classifier = BrowserErrorClassifier()
    error = Exception("Element not found")
    assert classifier.classify_error(error) == ErrorCategory.TRANSIENT

# Test suggestion parsing
def test_parse_suggestions():
    service = SelectorSuggestionService(llm_manager, get_html)
    response = 'SUGGESTION 1: "Login button" -> button.login'
    suggestions = service._parse_suggestions(response, ".old-selector")
    assert len(suggestions) == 1
    assert suggestions[0] == ("Login button", "button.login")
```

### Integration Tests

Test end-to-end flow:

```python
async def test_ai_suggestions_on_failure():
    # Setup browser with invalid selector
    lamia = Lamia(config=config)
    
    try:
        await lamia.web.click(".invalid-selector-that-does-not-exist")
    except ExternalOperationTransientError as e:
        # Verify suggestions in error message
        assert "AI-Powered Suggestions:" in str(e)
        assert "Selector:" in str(e)
```

## Performance Considerations

### Token Usage

- AI suggestions consume ~500-1500 tokens per request
- Limited to max 15,000 chars of HTML (prevents token overflow)
- Only triggered when all retries exhausted (not on every failure)

### Latency

- Suggestion generation adds ~1-3 seconds to failure path
- Does not impact successful operations
- Can be disabled if latency-sensitive

### Cost

- ~$0.001-0.003 per suggestion request (GPT-4)
- Only incurred when selectors actually fail
- Much cheaper than manual debugging time

## Summary

The AI-powered selector suggestion system transforms frustrating "element not found" errors into actionable, context-aware guidance. By analyzing the actual page HTML and considering the operation type, it provides intelligent alternatives that help users quickly resolve selector issues.

**Key Innovation**: Automatic, context-aware suggestions without any manual intervention or configuration required.

