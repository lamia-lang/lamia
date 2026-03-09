# File Context for AI Prompts

The `files()` context manager allows you to reference files in your LLM prompts using the `{@filename}` syntax. This is perfect for AI-powered form filling, document analysis, and any task where the AI needs access to local files.

## Overview

```python
with files("~/Documents/", "~/projects/"):
    def answer_question(question: str, models="openai:gpt-4"):
        """
        Answer: {question}
        
        Use information from {@resume.pdf} and {@cover_letter.txt}
        """
```

## Key Features

### 🔍 Smart File Search

Files are resolved using **multiple strategies** (similar to Cursor):

1. **Exact filename match** (highest priority)
2. **Content grep** (searches inside files)
3. **Fuzzy matching** (handles typos)
4. **Path component matching**

### 📄 Automatic File Extraction

- **PDF files**: Text extracted using PyPDF2
- **DOCX files**: Text extracted using python-docx
- **Text files**: Read directly

### ⚠️ Error Handling

- **AmbiguousFileError**: Multiple files match with similar scores
- **FileReferenceError**: File not found (with suggestions)

---

## Usage

### Basic Example

```python
# linkedin_automation.hu

with files("~/Documents/"):
    def extract_name(models="openai:gpt-4"):
        """Extract my full name from {@resume.pdf}"""
    
    def answer_experience_question(question: str, models="openai:gpt-4"):
        """
        Answer this job application question: {question}
        
        Use {@resume.pdf} and {@cover_letter.txt} for context.
        """

# Call the functions
name = extract_name()
answer = answer_experience_question("What are your main skills?")
```

### Multiple Directories

```python
with files("~/Documents/", "~/projects/linkedin/", "./config/"):
    # All files from these directories are indexed
    def setup(models="openai:gpt-4"):
        """Load API keys from {@credentials.json}"""
```

### Nested Contexts

```python
with files("~/Documents/"):
    with session("linkedin", "https://linkedin.com/feed"):
        # Both files and session contexts are active
        def apply_to_job(models="openai:gpt-4"):
            """
            Fill the Easy Apply form using {@resume.pdf}
            """
```

---

## File Reference Syntax

### Exact Path

```python
{@resume.pdf}                    # Searches for resume.pdf in indexed directories
{@path/to/resume.pdf}            # Relative path from indexed directory
{@/Users/me/Documents/resume.pdf} # Absolute path (always works)
```

### Fuzzy Matching

The search is **typo-tolerant**:

```python
{@resum.pdf}      # Finds resume.pdf (fuzzy match)
{@my resume}      # Finds john_doe_resume.pdf (word matching)
{@config}         # Finds config.yaml, config.json, etc.
```

---

## File Search Strategies

### 1. Filename Match (Score: +100)

```python
with files("~/Documents/"):
    # Exact: resume.pdf (score: 150)
    # Prefix: resume_2024.pdf (score: 130)
    # Contains: my_resume.pdf (score: 100)
    {@resume}
```

### 2. Content Grep (Score: +50)

```python
with files("~/projects/"):
    # Searches file contents for "database"
    # Useful for finding files by keywords
    {@database}
```

### 3. Fuzzy Match (Score: +30)

```python
with files("~/Documents/"):
    # Handles typos and partial names
    {@resum}  # → resume.pdf
    {@cv}     # → john_doe_cv.pdf
```

### 4. Path Component Match (Score: +20)

```python
with files("~/projects/"):
    # Matches directory names in path
    {@linkedin}  # → projects/linkedin/config.yaml
```

---

## Error Handling

### AmbiguousFileError

Raised when multiple files have similar match scores:

```python
from lamia import AmbiguousFileError

with files("~/Documents/"):
    try:
        def load_config(models="openai:gpt-4"):
            "Load {@config}"  # Multiple config.* files exist
    except AmbiguousFileError as e:
        print(f"Multiple files match '{e.query}':")
        for path, score in e.matches:
            print(f"  - {path} (score: {score:.2f})")
```

**Solution**: Be more specific:
```python
def load_config(models="openai:gpt-4"):
    "Load {@config.yaml}"  # Specific extension
```

### FileReferenceError

Raised when file cannot be found:

```python
from lamia import FileReferenceError

with files("~/Documents/"):
    try:
        def load_data(models="openai:gpt-4"):
            "Load {@nonexistent.pdf}"
    except FileReferenceError as e:
        print(f"File '{e.query}' not found")
        print(f"Did you mean: {e.suggestions}")
```

---

## File Extraction

### PDF Files

Requires `PyPDF2`:
```bash
pip install PyPDF2
```

```python
with files("~/Documents/"):
    def extract_info(models="openai:gpt-4"):
        """
        Extract name, email, and skills from {@resume.pdf}
        """
```

**Output format**:
```
--- resume.pdf ---
--- Page 1 ---
John Doe
Senior Python Developer
...
--- Page 2 ---
...
```

### DOCX Files

Requires `python-docx`:
```bash
pip install python-docx
```

```python
with files("~/Documents/"):
    def summarize(models="openai:gpt-4"):
        "Summarize {@report.docx}"
```

### Text Files

No dependencies required:

```python
with files("~/projects/"):
    def analyze(models="openai:gpt-4"):
        "Analyze code in {@main.py}"
```

---

## Advanced Usage

### Multiple File References

```python
def compare_documents(models="openai:gpt-4"):
    """
    Compare {@resume_v1.pdf} and {@resume_v2.pdf}
    
    List the differences between these two resumes.
    """
```

### Conditional File Loading

```python
import os

resume_path = "~/Documents/resume.pdf" if os.path.exists("~/Documents/resume.pdf") else "./fallback_resume.pdf"

with files(resume_path):
    def get_name(models="openai:gpt-4"):
        "Extract name from {@resume.pdf}"
```

### Mixed Contexts

```python
with files("~/Documents/"):
    # Variable substitution + file references
    def answer_question(question: str, company: str, models="openai:gpt-4"):
        """
        Answer this {company} job application question: {question}
        
        Use {@resume.pdf} for background information.
        """
```

---

## Configuration

### Ambiguity Threshold

Adjust how strict ambiguity detection is:

```python
from lamia.engine.managers.files_context_manager import FilesContext

with FilesContext("~/Documents/") as ctx:
    ctx.AMBIGUITY_THRESHOLD = 20.0  # Default: 10.0
    # Higher = less likely to trigger AmbiguousFileError
```

### Search Threshold

Adjust fuzzy matching sensitivity:

```python
from lamia.engine.managers.files_context_manager import FileSearcher

searcher = FileSearcher(files)
results = searcher.search("query", threshold=0.7)  # Default: 0.6
# Higher threshold = stricter matching
```

---

## Performance

### Indexing

Files are indexed once when entering the context:

```python
with files("~/Documents/"):  # ← Indexing happens here
    # Fast lookups inside the context
    result1 = func1()
    result2 = func2()
```

**Best practices**:
- Use specific directories, not entire home folder
- Avoid indexing `node_modules/`, `.venv/`, etc. (automatically skipped)

### Caching

File contents are cached during a single context:

```python
with files("~/Documents/"):
    # resume.pdf read from disk
    result1 = extract_name()
    
    # resume.pdf from cache (fast)
    result2 = extract_skills()
```

---

## Git-Aware Filtering

The context automatically skips:
- Hidden directories (`.git/`, `.venv/`)
- `node_modules/`, `__pycache__/`
- Files matching `.gitignore` patterns

---

## Comparison with Cursor

| Feature | Cursor | Lamia `files()` |
|---------|--------|-----------------|
| Syntax | `@filename` | `{@filename}` |
| Exact path | ✅ | ✅ |
| Fuzzy search | ✅ | ✅ |
| Content grep | ✅ | ✅ |
| Typo tolerance | ✅ | ✅ |
| PDF extraction | ❌ | ✅ |
| DOCX extraction | ❌ | ✅ |
| Error suggestions | ✅ | ✅ |

**Why `{@}` instead of bare `@`?**
- Avoids conflicts with `@mentions`, `@everyone`, email addresses
- Consistent with `{variable}` syntax
- Explicit and unambiguous

---

## Real-World Example: LinkedIn Easy Apply

```python
# linkedin_automation.hu

with files("~/Documents/"):
    with session("linkedin", "https://linkedin.com/feed"):
        
        def navigate_to_jobs():
            web.navigate("https://linkedin.com/jobs")
            web.click("button[aria-label='Easy Apply']")
        
        def fill_application_form(models="openai:gpt-4"):
            """
            Analyze the current job application form and fill it.
            
            Use {@resume.pdf} for my background.
            Use {@cover_letter_template.txt} for writing style.
            
            Return JSON with field selectors and values:
            {
              "fields": [
                {"selector": "input[name='years_experience']", "value": "5"},
                {"selector": "textarea[name='why_interested']", "value": "..."}
              ]
            }
            """
        
        def submit_application():
            navigate_to_jobs()
            
            # AI analyzes form and generates answers
            form_data = fill_application_form()
            
            # Fill fields
            for field in form_data['fields']:
                web.type_text(field['selector'], field['value'])
            
            # Upload resume
            web.upload_file("input[type='file']", "~/Documents/resume.pdf")
            
            # Submit
            web.click("button[type='submit']")
        
        # Execute
        submit_application()
```

---

## Troubleshooting

### "FileReferenceError: File 'resume.pdf' not found"

**Cause**: File not in indexed directories

**Solution**:
1. Check file exists: `ls ~/Documents/resume.pdf`
2. Add directory to context: `with files("~/Documents/"):`
3. Use absolute path: `{@/full/path/to/resume.pdf}`

### "AmbiguousFileError: Multiple files match 'config'"

**Cause**: Multiple files have similar scores

**Solution**:
- Be more specific: `{@config.yaml}` instead of `{@config}`
- Use path: `{@linkedin/config.yaml}`

### "PyPDF2 not installed"

**Cause**: PDF extraction requires PyPDF2

**Solution**:
```bash
pip install PyPDF2
```

### Slow indexing

**Cause**: Indexing too many files

**Solution**:
- Use specific directories, not `~`
- Files are cached, so subsequent lookups are fast

---

## API Reference

### `files(*paths: str) -> FilesContext`

Create a files context manager.

**Parameters**:
- `*paths`: File or directory paths to index

**Returns**: `FilesContext` manager

**Example**:
```python
with files("~/Documents/", "./config/"):
    # Use files here
```

### `FilesContext.resolve_file_reference(query: str) -> str`

Resolve a file reference to absolute path.

**Parameters**:
- `query`: Filename or pattern

**Returns**: Absolute path to resolved file

**Raises**:
- `FileReferenceError`: File not found
- `AmbiguousFileError`: Multiple matches

### `FilesContext.inject_file_references(prompt: str) -> str`

Replace `{@filename}` references with file content.

**Parameters**:
- `prompt`: Prompt string with `{@}` references

**Returns**: Prompt with injected file contents

---

## Dependencies

### Required

None (uses Python stdlib)

### Optional

- `PyPDF2`: PDF extraction
- `python-docx`: DOCX extraction

```bash
pip install PyPDF2 python-docx
```

---

## See Also

- [Web Automation](web-automation.md)
- [Validation](validation.md)

















