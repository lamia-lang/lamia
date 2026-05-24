# File Context for AI Prompts

The `files()` context manager allows you to reference files in your LLM prompts using the `{@filename}` syntax. This is perfect for AI-powered form filling, document analysis, and any task where the AI needs access to local files.

## Overview

```python
with files("~/Documents/", "~/projects/"):
    def answer_question(question):
        """
        Answer: {question}

        Use information from {@resume.pdf} and {@cover_letter.txt}
        """

answer = answer_question(question="What are my main skills?")
```

## Key Features

### Exact File Resolution

Files are resolved by **exact suffix matching** against indexed paths. No fuzzy loading — only the file you name gets loaded:

1. Absolute path → used directly
2. Filename or path suffix → must match exactly (e.g., `resume.pdf` or `docs/resume.pdf`)

If the same filename exists in multiple directories, you'll be asked to disambiguate with a longer path.

### Automatic File Extraction

- **PDF files**: Text extracted using PyPDF2
- **DOCX files**: Text extracted using python-docx
- **Text files**: Read directly

### Error Handling

- **AmbiguousFileError**: Same filename exists in multiple indexed directories
- **FileReferenceError**: File not found (with "Did you mean?" suggestions)

---

## Usage

### Basic Example

```python
# linkedin_automation.lm

with files("~/Documents/"):
    def extract_name(models="openai:gpt-4"):
        """Extract my full name from {@resume.pdf}"""
    
    def answer_experience_question(question, models="openai:gpt-4"):
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

### Filename or Path

```python
{@resume.pdf}                    # Exact filename match in indexed directories
{@docs/resume.pdf}               # Path suffix — disambiguates when resume.pdf exists in multiple dirs
{@/Users/me/Documents/resume.pdf} # Absolute path (always works)
```

File references use **exact suffix matching**. The reference must match the end of an indexed file path. No fuzzy or partial matching is performed — this prevents accidentally loading the wrong file.

### Disambiguating Duplicates

When the same filename exists in multiple directories:

```python
with files("~/Documents/", "~/Archive/"):
    # Both dirs have resume.pdf — this will raise AmbiguousFileError:
    {@resume.pdf}

    # Fix: use enough of the path to be unique:
    {@Documents/resume.pdf}
    {@Archive/resume.pdf}
```

The error message shows the minimal path needed to disambiguate each file.

### Variable File References (`.hu` files)

In `.hu` files, `{@identifier}` can refer to a parameter passed by the caller. If the caller passes a kwarg with that name, its value replaces the reference as a filepath:

```python
# summarize.hu
Summarize the following document: {@doc_path}
```

```python
# caller.lm
with files("~/Documents/"):
    result = summarize(doc_path="report.pdf")
    # {@doc_path} becomes {@report.pdf} → resolves to ~/Documents/report.pdf
```

If no kwarg matches, the identifier is treated as a literal filename.

### Variable vs File Reference

- `{variable}` — Python variable substitution (no `@`)
- `{@filename}` — file content injection (has `@`)

---

## Error Handling

### AmbiguousFileError

Raised when the same filename exists in multiple indexed directories:

```python
with files("~/Documents/", "~/Archive/"):
    try:
        def load_config(models="openai:gpt-4"):
            "Load {@config.yaml}"  # config.yaml exists in both dirs
    except AmbiguousFileError as e:
        print(f"Multiple files match '{e.query}':")
        for path, minimal in e.matches:
            print(f"  - {{@{minimal}}}")
```

**Solution**: Use the minimal unique path shown in the error:
```python
def load_config(models="openai:gpt-4"):
    "Load {@Documents/config.yaml}"
```

### FileReferenceError

Raised when no file matches the exact reference:

```python
with files("~/Documents/"):
    try:
        def load_data(models="openai:gpt-4"):
            "Load {@nonexistent.pdf}"
    except FileReferenceError as e:
        print(f"File '{e.query}' not found")
        if e.suggestions:
            print(f"Did you mean: {e.suggestions}")
```

When `files()` indexes zero files (e.g., due to a typo in the path), the error shows which paths failed:
```
files() indexed 0 files. Provided paths:
  ~/Dcouments → DOES NOT EXIST (resolved to /Users/sergey/Dcouments)
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

### Variable Paths

`files()` accepts variables — the paths are resolved at runtime:

```python
import os
from pathlib import Path

docs_dir = Path("~/Documents").expanduser()
resume = str(docs_dir / "resume.pdf") if (docs_dir / "resume.pdf").exists() else "./fallback_resume.pdf"

with files(resume):
    def get_name(models="openai:gpt-4"):
        "Extract name from {@resume.pdf}"
```

You can also pass directory variables:

```python
project_dir = os.environ.get("PROJECT_DIR", "./projects")

with files(project_dir):
    def summarize_readme(models="openai:gpt-4"):
        "Summarize {@README.md}"
```

### Mixed Contexts

```python
with files("~/Documents/"):
    # Variable substitution + file references
    def answer_question(question, company, models="openai:gpt-4"):
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
# linkedin_automation.lm

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

















