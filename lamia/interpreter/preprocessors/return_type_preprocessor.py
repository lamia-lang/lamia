"""
Return type preprocessor for handling -> Type syntax in with statements and expressions.

Handles preprocessing of:
- with session("name") -> Type: syntax
- web.method(args) -> Type expressions
- "prompt" -> File(...) expressions
"""

import re
import hashlib
from typing import Dict, Tuple


class WithReturnTypePreprocessor:
    """Preprocesses with session() -> Type: syntax before AST parsing."""
    
    def preprocess(self, source_code: str) -> Tuple[str, Dict[str, str]]:
        """
        Extract return type annotations from with session() statements and web expressions.
        
        This is the main public interface method.
        
        Args:
            source_code: Raw source code with hybrid syntax
            
        Returns:
            tuple: (processed_source_code, extracted_return_types)
        """
        return_types = {}
        processed_code = source_code
        
        # Process with session() -> Type: statements
        processed_code = self._process_session_statements(processed_code, return_types)
        
        # Process web.method() -> Type expressions
        processed_code = self._process_web_expressions(processed_code)
        
        # Process "prompt" -> File(...) expressions
        processed_code = self._process_file_write_expressions(processed_code)
        
        return processed_code, return_types
    
    def _process_session_statements(self, source_code: str, return_types: Dict[str, str]) -> str:
        """Process with session() -> Type: statements."""
        # Pattern to match: with session("name") -> Type:
        session_pattern = r'(\s*)(with\s+session\([^)]+\))\s*->\s*([^:]+):'
        
        def replace_with_statement(match):
            indent = match.group(1)
            with_part = match.group(2)
            return_type = match.group(3).strip()
            
            # Generate a unique key for this with statement
            key = self._generate_unique_key(f"{with_part}_{return_type}")
            return_types[key] = return_type
            
            # Replace with standard with statement + comment marker
            return f"{indent}{with_part}:  # LAMIA_WITH_RETURN_TYPE_{key}"
        
        return re.sub(session_pattern, replace_with_statement, source_code)
    
    def _process_web_expressions(self, source_code: str) -> str:
        """Process web.method() -> Type expressions."""
        # Pattern to match: web.method(args) -> Type at expression level
        # We rewrite to __LAMIA_WEB_RT__(Type, web.method(args)) so the transformer can handle it
        web_expr_pattern = r'(\s*)(web\.[\w_]+\([^\n]*?\))\s*->\s*([^\n]+)'
        
        def replace_web_expr(match):
            indent = match.group(1)
            call_part = match.group(2)
            return_type = match.group(3).strip()
            # Keep order: __LAMIA_WEB_RT__(Type, web.call(...))
            return f"{indent}__LAMIA_WEB_RT__({return_type}, {call_part})"
        
        return re.sub(web_expr_pattern, replace_web_expr, source_code)
    
    def _process_file_write_expressions(self, source_code: str) -> str:
        """Process standalone expression -> File(...) patterns.

        Matches patterns like:
            "Generate HTML about cats" -> File(HTML, "output.html")
            "Generate text" -> File("output.txt")

        Rewrites to:
            __LAMIA_FILE_WRITE__("Generate HTML about cats", File(HTML, "output.html"))

        The syntax transformer then handles __LAMIA_FILE_WRITE__ markers.
        """
        # Match: string_literal -> File(...)
        # The string can use single or double quotes, possibly triple-quoted.
        file_write_pattern = (
            r'(\s*)'                            # indent
            r'(\"\"\"[^\"]*\"\"\"|'             # triple-double-quoted string
            r"'''[^']*'''|"                     # triple-single-quoted string
            r'"[^"\n]*"|'                       # double-quoted string
            r"'[^'\n]*')"                       # single-quoted string
            r'\s*->\s*'                         # arrow
            r'(File\([^\n]+\))'                 # File(...) to end of meaningful parens
        )

        def replace_file_write(match: re.Match) -> str:
            indent = match.group(1)
            string_lit = match.group(2)
            file_call = match.group(3)
            return f"{indent}__LAMIA_FILE_WRITE__({string_lit}, {file_call})"

        return re.sub(file_write_pattern, replace_file_write, source_code)

    def _generate_unique_key(self, content: str) -> str:
        """Generate a unique key for content."""
        return hashlib.md5(content.encode()).hexdigest()[:8]
