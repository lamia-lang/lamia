"""Tool definitions for Lamia.

This is the single source of truth for:
- ToolName enum (all tools the IDE can call)
- TOOL_DEFINITIONS (full IDE tool list sent in the system prompt)
- FILE_CONTEXT_TOOL_DEFINITIONS (restricted read-only subset for ``with files()`` contexts)
"""

import enum


MAX_READ_CHUNK_CHARS = 100_000


class ToolName(str, enum.Enum):
    GET_DOCS = "get_docs"
    READ_FILE = "read_file"
    LIST_FILES = "list_files"
    WRITE_FILE = "write_file"
    PATCH_FILE = "patch_file"
    DELETE_FILE = "delete_file"
    FIND_DEFINITION = "find_definition"
    FIND_REFERENCES = "find_references"
    COPY_FILE = "copy_file"
    MOVE_FILE = "move_file"
    GREP = "grep"
    GLOB = "glob"
    WEB_FETCH = "web_fetch"
    BROWSER_NAVIGATE = "browser_navigate"
    BROWSER_CLICK = "browser_click"
    BROWSER_TYPE = "browser_type"
    BROWSER_GET_TEXT = "browser_get_text"
    BROWSER_SCREENSHOT = "browser_screenshot"
    BROWSER_WAIT = "browser_wait"
    BROWSER_GET_ACCESSIBILITY_TREE = "get_accessibility_tree"
    LINT_CODE = "lint_code"


TOOL_LABELS: dict[str, tuple[str, str]] = {
    ToolName.GET_DOCS:           ("Reading docs",        "topic"),
    ToolName.READ_FILE:          ("Reading file",        "path"),
    ToolName.LIST_FILES:         ("Listing files",       "directory"),
    ToolName.WRITE_FILE:         ("Writing file",        "path"),
    ToolName.PATCH_FILE:         ("Editing file",        "path"),
    ToolName.DELETE_FILE:        ("Deleting file",       "path"),
    ToolName.COPY_FILE:          ("Copying",             "source"),
    ToolName.MOVE_FILE:          ("Moving",              "source"),
    ToolName.GREP:               ("Searching",           "pattern"),
    ToolName.GLOB:               ("Finding files",       "pattern"),
    ToolName.FIND_DEFINITION:    ("Finding definition",  "symbol"),
    ToolName.FIND_REFERENCES:    ("Finding references",  "symbol"),
    ToolName.WEB_FETCH:          ("Fetching page",       "url"),
    ToolName.BROWSER_NAVIGATE:   ("Navigating to",       "url"),
    ToolName.BROWSER_CLICK:      ("Clicking",            "selector"),
    ToolName.BROWSER_TYPE:       ("Typing into",         "selector"),
    ToolName.BROWSER_GET_TEXT:   ("Reading page text",   "selector"),
    ToolName.BROWSER_SCREENSHOT: ("Taking screenshot",   ""),
    ToolName.BROWSER_WAIT:       ("Waiting for",         "selector"),
    ToolName.BROWSER_GET_ACCESSIBILITY_TREE: ("Investigating page structure", ""),
    ToolName.LINT_CODE:          ("Linting code",        "file_type"),
}


_SUPPRESS_DETAIL_VALUES = {"body", "html", "page"}


def tool_progress_label(tool: str, args: dict) -> str:
    entry = TOOL_LABELS.get(tool)
    if not entry:
        return tool.replace("_", " ")
    verb, arg_key = entry
    detail = str(args.get(arg_key, "")) if arg_key else ""
    if detail.strip().lower() in _SUPPRESS_DETAIL_VALUES:
        detail = ""
    return f"{verb}: {detail}" if detail else verb


TOPIC_TO_FILE = {
    "lm-syntax": "user-guide/lm-syntax.md",
    ".lm": "user-guide/lm-syntax.md",
    "hu-syntax": "user-guide/hu-syntax.md",
    ".hu": "user-guide/hu-syntax.md",
    "files-context": "user-guide/files-context.md",
    "files": "user-guide/files-context.md",
    "configuration": "getting-started/configuration.md",
    "config.yaml": "getting-started/configuration.md",
    "installation": "getting-started/installation.md",
    "validation": "user-guide/validation.md",
    "web-automation": "user-guide/web-automation.md",
    "model-evaluation": "user-guide/evaluation.md",
    "selector": "validation/selector-usage-guide.md",
    "debugger": "advanced/debugger.md",
    "hu-style-guide": "style-guides/hu-style.md",
    "lm-style-guide": "style-guides/lm-style.md",
    "project-structure": "style-guides/project-structure.md",
    "getting-started": "getting-started/index.md",
    "lamia-as-python-library": "user-guide/python-library.md",
    "pydantic-models": "user-guide/pydantic-models.md",
    "custom-llm-adapters": "user-guide/custom-llm-adapters.md",
    "file-operations": "user-guide/file-operations.md",
    "file.read": "user-guide/file-operations.md",
    "file.write": "user-guide/file-operations.md",
    "file.append": "user-guide/file-operations.md",
    "file.exists": "user-guide/file-operations.md",
    "file.glob": "user-guide/file-operations.md",
    "scheduling": "user-guide/scheduling.md",
    "schedule": "user-guide/scheduling.md",
    "cron": "user-guide/scheduling.md",
    "cloud": "advanced/lamia-cloud.md",
    "lamia-cloud": "advanced/lamia-cloud.md",
    "remote": "advanced/lamia-cloud.md",
    "--remote": "advanced/lamia-cloud.md",
    "cloud-scheduler": "advanced/lamia-cloud.md",
    "cloud-trigger": "user-guide/triggers.md",
    "trigger": "user-guide/triggers.md",
    "triggers": "user-guide/triggers.md",
}


_HU_FILE_HINT = (
    "IMPORTANT for .hu files: use PLAIN TEXT only (no markdown -- "
    "no **bold**, *italic*, # headers, `backticks`, or HTML), "
    "parameters use single braces {param}, NOT double {{param}} which makes them literals, "
    "do NOT include output structure information and example outputs (JSON, YAML, code blocks) -- "
    ".hu files are output agnostic and the caller specifies the return type."
)

_DOCS_TOPICS = ", ".join(sorted(set(TOPIC_TO_FILE.keys())))


# ── Full IDE tool definitions ────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": ToolName.GET_DOCS.value,
        "description": f"Retrieve Lamia language documentation by topic. Topics: {_DOCS_TOPICS}.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Documentation topic to retrieve",
                }
            },
            "required": ["topic"],
        },
    },
    {
        "name": ToolName.READ_FILE.value,
        "description": (
            f"Read the contents of a file. For large files (>{MAX_READ_CHUNK_CHARS} chars), "
            "returns a chunk and reports the total size. Use 'offset' to "
            "read subsequent chunks."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative file path to read",
                },
                "offset": {
                    "type": "integer",
                    "description": "Character offset to start reading from. Defaults to 0.",
                },
                "chunk_size": {
                    "type": "integer",
                    "description": f"Max characters to read. Defaults to and capped at {MAX_READ_CHUNK_CHARS}.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": ToolName.LIST_FILES.value,
        "description": "Recursively list files and subdirectories (up to 4 levels deep).",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory path to list (default: current directory)",
                }
            },
        },
    },
    {
        "name": ToolName.WRITE_FILE.value,
        "description": (
            "Create or overwrite a file with the given content. " + _HU_FILE_HINT
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to write to",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": ToolName.PATCH_FILE.value,
        "description": (
            "Edit an existing file by replacing old_text with new_text. "
            "Preferred over write_file for modifications -- only express the change, not the whole file. "
            + _HU_FILE_HINT
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to edit",
                },
                "old_text": {
                    "type": "string",
                    "description": "Exact text to find in the file (must match exactly)",
                },
                "new_text": {
                    "type": "string",
                    "description": "Replacement text",
                },
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": ToolName.DELETE_FILE.value,
        "description": "Delete a file at the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to delete",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": ToolName.FIND_DEFINITION.value,
        "description": (
            "Find where a function, class, or .hu file is defined. "
            "Returns file path and line number."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Name of the function, class, or .hu file to find",
                },
            },
            "required": ["symbol"],
        },
    },
    {
        "name": ToolName.FIND_REFERENCES.value,
        "description": (
            "Find all files that reference or call a given symbol. "
            "Returns file paths with line numbers and context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Name of the function, class, or variable to search for",
                },
            },
            "required": ["symbol"],
        },
    },
    {
        "name": ToolName.COPY_FILE.value,
        "description": "Copy a file or directory to a new location. Works recursively for directories.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source file or directory path",
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path",
                },
            },
            "required": ["source", "destination"],
        },
    },
    {
        "name": ToolName.MOVE_FILE.value,
        "description": "Move or rename a file or directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source file or directory path",
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path",
                },
            },
            "required": ["source", "destination"],
        },
    },
    {
        "name": ToolName.GREP.value,
        "description": (
            "Search for a pattern in files. Returns matching lines with file paths and line numbers. "
            "Searches recursively in the given directory."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Text or regex pattern to search for",
                },
                "directory": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)",
                },
                "include": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g. '*.py', '*.lm')",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": ToolName.GLOB.value,
        "description": (
            "Find files matching a glob pattern. Returns file paths sorted by modification time. "
            "Use | to combine multiple patterns: '*.ts|*.tsx|config.json'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern, use | for OR (e.g. '**/*.py', '*.lm|*.hu', 'config.json|*.yaml')",
                },
                "directory": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": ToolName.WEB_FETCH.value,
        "description": (
            "Fetch a web page via Lamia HTTP actions and return response content. "
            "Lightweight -- no browser required. Prefer this over browser tools when you only need page content."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": ToolName.BROWSER_NAVIGATE.value,
        "description": "Navigate to a URL in the browser. Returns the page title and visible text.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to navigate to",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": ToolName.BROWSER_CLICK.value,
        "description": "Click an element on the page. Use CSS selectors or natural language descriptions.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector, XPath, or natural language description (e.g. 'Sign in button')",
                },
            },
            "required": ["selector"],
        },
    },
    {
        "name": ToolName.BROWSER_TYPE.value,
        "description": "Type text into an input element.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector or description of the input field",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type",
                },
            },
            "required": ["selector", "text"],
        },
    },
    {
        "name": ToolName.BROWSER_GET_TEXT.value,
        "description": "Get visible text content from the page or a specific element.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector to get text from (default: body — entire page)",
                },
            },
        },
    },
    {
        "name": ToolName.BROWSER_SCREENSHOT.value,
        "description": "Take a screenshot of the current page. Returns the file path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to save screenshot (default: screenshot.png in cwd)",
                },
            },
        },
    },
    {
        "name": ToolName.BROWSER_WAIT.value,
        "description": "Wait for an element to appear or become visible.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector or description to wait for",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default: 10)",
                },
            },
            "required": ["selector"],
        },
    },
    {
        "name": ToolName.BROWSER_GET_ACCESSIBILITY_TREE.value,
        "description": (
            "Get the accessibility tree (AXTree) of the current page. "
            "Returns a compact structured view of all interactive elements with their roles "
            "and labels. Use this to discover page structure and selectors for automation scripts. "
            "Much smaller than full HTML. Call browser_navigate first to load the page."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "depth": {
                    "type": "integer",
                    "description": "Max tree depth (default: no limit). Use 3-5 for large pages.",
                },
            },
        },
    },
    {
        "name": ToolName.LINT_CODE.value,
        "description": (
            "Lint Lamia code without writing to disk. Use this to validate "
            ".lm or .hu code before presenting it. Returns lint violations "
            "and feedback. Fix any errors before showing the code to the user."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The code content to lint",
                },
                "file_type": {
                    "type": "string",
                    "description": '"lm" for Lamia scripts or "hu" for prompt templates',
                },
            },
            "required": ["content", "file_type"],
        },
    },
]


# ── File-context tool definitions (read-only subset for ``with files()``) ────

MAX_FILE_CONTEXT_READ_CHARS = 100_000
MAX_FILE_CONTEXT_LIST_DEPTH = 4

FILE_CONTEXT_TOOL_DEFINITIONS = [
    {
        "name": "list_files",
        "description": "List files and subdirectories (up to 4 levels deep) within the file context.",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory path relative to the file context root (default: '.')",
                }
            },
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file within the file context.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to the file context root",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "glob_files",
        "description": "Find files matching a glob pattern within the file context. Use | to combine patterns.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g. '*.txt', '**/*.csv', '*.json|*.yaml')",
                }
            },
            "required": ["pattern"],
        },
    },
]
