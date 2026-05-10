"""File context management for LLM prompts with smart file search."""

import os
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from difflib import SequenceMatcher, get_close_matches
import re

import PyPDF2

from lamia.errors import AmbiguousFileError, FileReferenceError
from lamia.project import find_project_root

logger = logging.getLogger(__name__)

_FILE_REF_RE = re.compile(r'\{@([^}]+)\}')


def _compute_minimal_unique_paths(paths: List[str]) -> Dict[str, str]:
    """For a list of absolute paths that share a basename, compute the shortest
    path suffix that uniquely identifies each one.

    Example::

        ["/a/b/resume.pdf", "/a/c/resume.pdf"]
        → {"/a/b/resume.pdf": "b/resume.pdf",
           "/a/c/resume.pdf": "c/resume.pdf"}

    If two paths are truly identical after normalization, the full path is
    returned for both (the caller should have deduplicated).
    """
    if len(paths) <= 1:
        return {p: os.path.basename(p) for p in paths}

    split = {p: p.replace("\\", "/").split("/") for p in paths}
    result: Dict[str, str] = {}

    for target in paths:
        parts = split[target]
        for depth in range(1, len(parts) + 1):
            suffix = "/".join(parts[-depth:])
            others_match = any(
                "/".join(split[other][-depth:]) == suffix
                for other in paths
                if other != target
            )
            if not others_match:
                result[target] = suffix
                break
        else:
            result[target] = target

    return result


# ---------------------------------------------------------------------------
# Source-file context stack
# ---------------------------------------------------------------------------
_source_file_stack: List[str] = []


def push_source_file(path: str) -> None:
    _source_file_stack.append(str(Path(path).resolve()))


def pop_source_file() -> None:
    if _source_file_stack:
        _source_file_stack.pop()


def get_current_source_file() -> Optional[str]:
    return _source_file_stack[-1] if _source_file_stack else None


def _has_path_components(query: str) -> bool:
    """Return True if the query contains path separators or relative markers."""
    return os.sep in query or '/' in query or query.startswith('..')



class FileSearcher:
    """Smart file search with multiple strategies."""
    
    def __init__(self, indexed_files: List[str]):
        self.indexed_files = indexed_files
        self.file_cache: Dict[str, str] = {}
    
    def search(self, query: str, threshold: float = 0.6) -> List[Tuple[str, float]]:
        """Search for files using multiple strategies.
        
        Returns:
            List of (filepath, score) tuples, sorted by score descending
        """
        results = []
        
        # Strategy 1: Exact filename match (highest score)
        results.extend(self._filename_match(query, boost=100))
        
        # Strategy 2: Content grep (for keyword-like queries only)
        # Filename/path-like queries should avoid grep to keep failures fast.
        if (
            len(query) > 3
            and not query.endswith('.pdf')  # Skip binary files
            and not _has_path_components(query)
            and os.path.splitext(os.path.basename(query))[1] == ""
        ):
            results.extend(self._content_grep(query, boost=50))
        
        # Strategy 3: Fuzzy filename match
        results.extend(self._fuzzy_match(query, boost=30, threshold=threshold))
        
        # Strategy 4: Path component match
        results.extend(self._path_match(query, boost=20))
        
        # Deduplicate and sort by score
        seen = {}
        for filepath, score in results:
            if filepath not in seen or seen[filepath] < score:
                seen[filepath] = score
        
        return sorted(seen.items(), key=lambda x: x[1], reverse=True)
    
    def _filename_match(self, query: str, boost: int) -> List[Tuple[str, float]]:
        """Exact or prefix filename matching."""
        results = []
        query_lower = query.lower()
        
        for filepath in self.indexed_files:
            filename = os.path.basename(filepath).lower()
            
            if filename == query_lower:
                results.append((filepath, boost + 50))  # Exact match
            elif filename.startswith(query_lower):
                results.append((filepath, boost + 30))  # Prefix match
            elif query_lower in filename:
                results.append((filepath, boost))  # Contains match
        
        return results
    
    def _content_grep(self, query: str, boost: int) -> List[Tuple[str, float]]:
        """Search file contents for query string."""
        results = []
        query_lower = query.lower()
        
        for filepath in self.indexed_files:
            # Skip binary files
            if filepath.endswith(('.pdf', '.jpg', '.png', '.zip', '.exe', '.docx')):
                continue
            
            try:
                content = self._read_file_cached(filepath)
                content_lower = content.lower()
                
                # Count occurrences
                count = content_lower.count(query_lower)
                if count > 0:
                    score = boost + min(count * 5, 30)  # Cap bonus at +30
                    results.append((filepath, score))
            except Exception as e:
                logger.debug(f"Could not read file {filepath} for grep: {e}")
        
        return results
    
    def _fuzzy_match(self, query: str, boost: int, threshold: float) -> List[Tuple[str, float]]:
        """Fuzzy string matching using difflib."""
        results = []
        
        for filepath in self.indexed_files:
            filename = os.path.basename(filepath).lower()
            query_lower = query.lower()
            
            similarity = SequenceMatcher(None, query_lower, filename).ratio()
            if similarity > threshold:
                score = boost * similarity
                results.append((filepath, score))
        
        return results
    
    def _path_match(self, query: str, boost: int) -> List[Tuple[str, float]]:
        """Match against any path component."""
        results = []
        query_lower = query.lower()
        
        for filepath in self.indexed_files:
            path_parts = filepath.lower().split(os.sep)
            
            for part in path_parts:
                if query_lower in part:
                    results.append((filepath, boost))
                    break
        
        return results
    
    def _read_file_cached(self, filepath: str) -> str:
        """Read file with caching."""
        if filepath not in self.file_cache:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                self.file_cache[filepath] = f.read()
        return self.file_cache[filepath]


class FilesContext:
    """Manages file context for LLM prompts."""

    def __init__(self, *paths: str, _push_to_stack: bool = False):
        """Initialize file context with paths.
        
        Args:
            *paths: File or directory paths to include in context
        """
        self.paths = paths
        self.indexed_files: List[str] = []
        self._entered = False
    
    def __enter__(self):
        """Load files on context enter."""
        self.indexed_files = self._index_files(self.paths)
        self._entered = True
        logger.debug(f"Indexed {len(self.indexed_files)} files for context")
        
        _context_stack.append(self)
        logger.debug(f"FilesContext pushed to stack (size={len(_context_stack)})")
        
        return self
    
    def __exit__(self, *args):
        """Clean up on context exit."""
        if _context_stack and _context_stack[-1] is self:
            _context_stack.pop()
            logger.debug(f"FilesContext popped from stack (size={len(_context_stack)})")
        
        self.indexed_files.clear()
        self._entered = False
    
    def _index_files(self, paths: List[str]) -> List[str]:
        """Index all files in the given paths."""
        indexed = []
        
        for path_str in paths:
            path = Path(os.path.expanduser(path_str)).resolve()
            
            if path.is_file():
                indexed.append(str(path))
            elif path.is_dir():
                # Walk directory, skip common ignore patterns
                for root, dirs, files in os.walk(path):
                    # Skip hidden directories and common patterns
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    
                    for file in files:
                        if not file.startswith('.'):
                            filepath = os.path.join(root, file)
                            indexed.append(filepath)
            else:
                logger.warning(f"Path does not exist: {path}")
        
        return indexed
    
    def resolve_file_reference(self, query: str) -> str:
        """Resolve a file reference to an actual filepath using exact matching.

        Resolution order:
        1. Absolute path → use directly
        2. Exact path-suffix match against all indexed files
           - 1 match  → resolved
           - 0 matches → FileReferenceError with "Did you mean?" from difflib
           - >1 matches → AmbiguousFileError with minimal unique paths

        No fuzzy/similarity resolution is performed — only exact suffix matching.
        Fuzzy matching is used *only* for "Did you mean?" suggestions on failure.
        """
        if not self._entered:
            raise RuntimeError("FilesContext not entered. Use 'with files(...):'")
        if not self.indexed_files:
            raise FileReferenceError(
                query,
                [],
                self._build_empty_index_hint(),
            )

        # 1. Absolute path
        if os.path.isabs(query) and os.path.exists(query):
            logger.debug(f"Resolved '{query}' as absolute path")
            return query

        # 2. Exact suffix match: query must match the tail of the indexed path
        query_normalized = query.replace("\\", "/").strip("/")
        exact_matches: List[str] = []
        for indexed_path in self.indexed_files:
            normalized = indexed_path.replace("\\", "/")
            if normalized.endswith("/" + query_normalized) or normalized == query_normalized:
                exact_matches.append(indexed_path)

        if len(exact_matches) == 1:
            logger.debug(f"Resolved '{query}' → '{exact_matches[0]}'")
            return exact_matches[0]

        if len(exact_matches) > 1:
            unique_paths = _compute_minimal_unique_paths(exact_matches)
            raise AmbiguousFileError(
                query,
                [(p, unique_paths[p]) for p in exact_matches],
            )

        # 3. No exact match — build "Did you mean?" via difflib
        all_filenames = sorted({os.path.basename(f) for f in self.indexed_files})
        suggestions = get_close_matches(query_normalized, all_filenames, n=3, cutoff=0.4)
        raise FileReferenceError(
            query,
            suggestions,
            self._build_not_found_hint(),
        )

    def _build_empty_index_hint(self) -> str:
        """Diagnostic hint when indexed_files is empty — tells user which paths failed."""
        if not self.paths:
            return "files() was called with no paths."

        lines = ["files() indexed 0 files. Provided paths:"]
        for p in self.paths:
            resolved = Path(os.path.expanduser(p)).resolve()
            if resolved.exists():
                lines.append(f"  {p} → exists but contains no files")
            else:
                lines.append(f"  {p} → Does not exist (resolved to {resolved})")
        return "\n".join(lines)

    def _build_not_found_hint(self) -> str:
        """Diagnostic hint when file not found but paths are valid."""
        if not self.paths:
            roots = sorted({os.path.dirname(p) for p in self.indexed_files})
            preview = roots[:5]
            suffix = " ..." if len(roots) > 5 else ""
            return f"Searched {len(self.indexed_files)} files in: {', '.join(preview)}{suffix}"
        return f"Searched {len(self.indexed_files)} files in: {', '.join(self.paths)}"
    
    def read_file_content(self, filepath: str) -> str:
        """Read file content with appropriate extraction."""
        return read_file_content(filepath)
    
    def inject_file_references(self, prompt: str) -> str:
        """Replace {@filename} references with actual file content.
        
        Args:
            prompt: The prompt string potentially containing {@filename} references
        
        Returns:
            Prompt with file references replaced by content
        """
        def replace_file_ref(match):
            filename = match.group(1).strip()
            
            try:
                filepath = self.resolve_file_reference(filename)
                content = self.read_file_content(filepath)
                
                return f"\n\n--- {os.path.basename(filepath)} ---\n{content}\n"
            
            except (FileReferenceError, AmbiguousFileError) as e:
                # Re-raise these so user can fix the reference
                raise
            except Exception as e:
                logger.error(f"Error processing file reference '{filename}': {e}")
                return f"\n[Error loading file: {filename} - {e}]\n"
        
        # Find all {@filename} references
        pattern = r'\{@([^}]+)\}'
        return re.sub(pattern, replace_file_ref, prompt)


# Global context stack for nested contexts
_context_stack: List[FilesContext] = []


def get_active_files_context() -> Optional[FilesContext]:
    """Get the currently active FilesContext, if any."""
    return _context_stack[-1] if _context_stack else None


class CapturedFilesContext:
    """Snapshot of a FilesContext for deferred use outside the original ``with files()`` block.

    When an LLM function is defined inside a ``with files()`` block, the AST
    transformer inserts ``capture_files_context()`` before the function definition
    and wraps the function body with ``__enter__`` / ``__exit__`` calls so the
    captured context is re-activated on every invocation, even after the original
    ``with`` block has exited.
    """

    def __init__(self, indexed_files: List[str], original_paths: Tuple[str, ...] = ()) -> None:
        self._indexed_files = list(indexed_files)
        self._original_paths = original_paths

    def __enter__(self) -> 'FilesContext':
        ctx = FilesContext.__new__(FilesContext)
        ctx.paths = self._original_paths
        ctx.indexed_files = list(self._indexed_files)
        ctx._entered = True
        _context_stack.append(ctx)
        return ctx

    def __exit__(self, *args) -> None:
        if _context_stack:
            _context_stack.pop()


def capture_files_context() -> Optional[CapturedFilesContext]:
    """Snapshot the current active files context for deferred use.

    Call this inside a ``with files(...)`` block.  The returned
    :class:`CapturedFilesContext` can be used later (outside the original
    ``with`` block) to temporarily restore the same set of indexed files.
    Returns ``None`` when no files context is currently active.
    """
    ctx = get_active_files_context()
    if ctx is None:
        return None
    return CapturedFilesContext(list(ctx.indexed_files), ctx.paths)


def files(*paths: str) -> FilesContext:
    """Create a files context manager.
    
    Usage:
        with files("~/Documents/", "~/projects/"):
            # LLM calls in this block can reference files with {@filename}
            result = lamia.run("Extract name from {@resume.pdf}")
    
    Args:
        *paths: File or directory paths to include in context
    
    Returns:
        FilesContext manager that pushes itself to the global stack
    """
    # Create context with _push_to_stack=True
    return FilesContext(*paths, _push_to_stack=True)


# ---------------------------------------------------------------------------
# Module-level file content reader (shared by FilesContext and standalone)
# ---------------------------------------------------------------------------

def read_file_content(filepath: str) -> str:
    """Read file content with appropriate extraction for PDF/DOCX."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext == '.pdf':
        return _extract_pdf_text(filepath)
    elif ext in ['.docx', '.doc']:
        return _extract_docx_text(filepath)
    else:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()


def _extract_pdf_text(filepath: str) -> str:
    with open(filepath, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        text_parts = []

        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text.strip():
                text_parts.append(f"--- Page {page_num + 1} ---\n{text}")

        if text_parts:
            return "\n\n".join(text_parts)
        return f"[PDF file: {os.path.basename(filepath)} - text extraction returned empty]"


def _extract_docx_text(filepath: str) -> str:
    try:
        import docx
    except ImportError:
        return f"[DOCX file: {os.path.basename(filepath)} - python-docx not installed. Install with: pip install python-docx]"

    document = docx.Document(filepath)
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]

    if paragraphs:
        return "\n\n".join(paragraphs)
    return f"[DOCX file: {os.path.basename(filepath)} - no text content]"


# ---------------------------------------------------------------------------
# Standalone file-reference resolution (no FilesContext required)
# ---------------------------------------------------------------------------

def _resolve_standalone_reference(query: str, source_path: str) -> str:
    """Resolve a single {@...} reference without a FilesContext.

    Strategy:
    1. Absolute path -- use directly.
    2. Has path components (``/``, ``..``) -- resolve relative to source file.
    3. Bare filename -- find the project root (walk up to config.yaml) and
       use the same smart-search logic as ``FilesContext``.
    """
    # 1. Absolute path
    if os.path.isabs(query) and os.path.exists(query):
        logger.debug(f"Standalone resolved '{query}' as absolute path")
        return query

    # 2. Relative path with explicit components
    if _has_path_components(query):
        source_dir = os.path.dirname(source_path)
        candidate = os.path.normpath(os.path.join(source_dir, query))
        if os.path.exists(candidate):
            logger.debug(f"Standalone resolved '{query}' relative to source: {candidate}")
            return candidate
        raise FileReferenceError(query, [])

    # 3. Bare filename -- use project root as context
    project_root = find_project_root(source_path)
    if project_root is None:
        raise FileReferenceError(query, [])

    ctx = FilesContext(project_root)
    ctx.indexed_files = ctx._index_files([project_root])
    ctx._entered = True
    logger.debug(
        f"Standalone: indexed {len(ctx.indexed_files)} files under project root '{project_root}'"
    )
    return ctx.resolve_file_reference(query)


def resolve_standalone_file_references(prompt: str, source_path: str) -> str:
    """Replace {@...} references using path-based resolution.

    Called as a fallback when no ``FilesContext`` is active.
    """
    if not _FILE_REF_RE.search(prompt):
        return prompt

    def replace_ref(match: re.Match) -> str:
        query = match.group(1).strip()
        try:
            filepath = _resolve_standalone_reference(query, source_path)
            content = read_file_content(filepath)
            return f"\n\n--- {os.path.basename(filepath)} ---\n{content}\n"
        except (FileReferenceError, AmbiguousFileError):
            raise
        except Exception as e:
            logger.error(f"Error processing standalone file reference '{query}': {e}")
            return f"\n[Error loading file: {query} - {e}]\n"

    return _FILE_REF_RE.sub(replace_ref, prompt)

