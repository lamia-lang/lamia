"""File context management for LLM prompts with smart file search."""

import os
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from difflib import SequenceMatcher, get_close_matches
import re

import PyPDF2

from lamia.errors import AmbiguousFileError, FileReferenceError

logger = logging.getLogger(__name__)

_FILE_REF_RE = re.compile(r'\{@([^}]+)\}')

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


def _find_project_root(start_path: str) -> Optional[str]:
    """Walk up from *start_path* looking for a directory containing config.yaml."""
    current = Path(start_path).resolve()
    if current.is_file():
        current = current.parent
    for directory in [current, *current.parents]:
        if (directory / "config.yaml").is_file():
            return str(directory)
    return None

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
        
        # Strategy 2: Content grep (if query looks like a keyword)
        if len(query) > 3 and not query.endswith('.pdf'):  # Skip binary files
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
    
    # Ambiguity threshold: if top 2 matches differ by less than this, it's ambiguous
    AMBIGUITY_THRESHOLD = 10.0
    
    def __init__(self, *paths: str, _push_to_stack: bool = False):
        """Initialize file context with paths.
        
        Args:
            *paths: File or directory paths to include in context
        """
        self.paths = paths
        self.indexed_files: List[str] = []
        self.searcher: Optional[FileSearcher] = None
    
    def __enter__(self):
        """Load files on context enter."""
        self.indexed_files = self._index_files(self.paths)
        self.searcher = FileSearcher(self.indexed_files)
        logger.info(f"Indexed {len(self.indexed_files)} files for context")
        
        # Push to global stack
        _context_stack.append(self)
        logger.info(f"FilesContext pushed to stack (size={len(_context_stack)})")
        
        return self
    
    def __exit__(self, *args):
        """Clean up on context exit."""
        # Pop from global stack if we pushed
        if _context_stack and _context_stack[-1] is self:
            _context_stack.pop()
            logger.info(f"FilesContext popped from stack (size={len(_context_stack)})")
        
        self.indexed_files.clear()
        self.searcher = None
    
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
        """Resolve a file reference to an actual filepath.
        
        Args:
            query: The filename or pattern to search for (e.g., "resume.pdf")
        
        Returns:
            Absolute path to the resolved file
        
        Raises:
            FileNotFoundError: If no file matches
            AmbiguousFileError: If multiple files match with similar scores
        """
        if not self.searcher:
            raise RuntimeError("FilesContext not entered. Use 'with files(...):'")
        
        # 1. Try as absolute path
        if os.path.isabs(query) and os.path.exists(query):
            logger.debug(f"Resolved '{query}' as absolute path")
            return query
        
        # 2. Try as relative path from each indexed directory
        for indexed_path in self.indexed_files:
            indexed_dir = os.path.dirname(indexed_path)
            candidate = os.path.join(indexed_dir, query)
            if os.path.exists(candidate):
                logger.debug(f"Resolved '{query}' as relative path: {candidate}")
                return candidate
        
        # 3. Smart search
        matches = self.searcher.search(query)
        
        if not matches:
            # No matches - provide fuzzy suggestions
            all_filenames = [os.path.basename(f) for f in self.indexed_files]
            suggestions = get_close_matches(query, all_filenames, n=3, cutoff=0.3)
            raise FileReferenceError(query, suggestions)
        
        # Check for ambiguity
        if len(matches) > 1:
            top_score = matches[0][1]
            second_score = matches[1][1]
            
            if abs(top_score - second_score) < self.AMBIGUITY_THRESHOLD:
                raise AmbiguousFileError(query, matches)
        
        # Clear winner
        resolved_path = matches[0][0]
        logger.info(f"Resolved '{query}' → '{resolved_path}' (score: {matches[0][1]:.2f})")
        return resolved_path
    
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
    project_root = _find_project_root(source_path)
    if project_root is None:
        raise FileReferenceError(query, [])

    ctx = FilesContext(project_root)
    ctx.indexed_files = ctx._index_files([project_root])
    ctx.searcher = FileSearcher(ctx.indexed_files)
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

