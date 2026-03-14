"""
Return type preprocessor for handling -> Type syntax in with statements and expressions.

Handles preprocessing of:
- with session("name") -> Type: syntax
- web.method(args) -> Type expressions
- "prompt" -> File(...) expressions
- [var =] "prompt" -> Type expressions (with optional assignment)
- [var =] callable(...) -> Type expressions (function calls piped to a type)
- [var =] callable(...) -> File(...) expressions (function calls piped to file output)
"""

import re
import hashlib
from typing import Dict, Tuple

# Shared sub-pattern matching any single- or triple-quoted string literal.
_QUOTED_STRING = (
    r'(\"\"\"[^\"]*\"\"\"|'   # triple-double-quoted string
    r"'''[^']*'''|"            # triple-single-quoted string
    r'"[^"\n]*"|'              # double-quoted string
    r"'[^'\n]*')"              # single-quoted string
)


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
        
        # Process "prompt" -> File(...) expressions (string-literal only)
        processed_code = self._process_file_write_expressions(processed_code)

        # Process [var =] expr -> File(...) where expr is NOT a string literal
        processed_code = self._process_callable_file_write_expressions(processed_code)

        # Process [var =] "prompt" -> Type expressions (must run AFTER file writes)
        processed_code = self._process_typed_prompt_expressions(processed_code)

        # Process [var =] expr -> Type where expr is NOT a string literal.
        # Must run LAST — catches any remaining -> Type patterns left by the above passes.
        processed_code = self._process_callable_typed_expressions(processed_code)

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
        file_write_pattern = (
            r'(\s*)'               # indent
            + _QUOTED_STRING +
            r'\s*->\s*'            # arrow
            r'(File\([^\n]+\))'    # File(...) to end of meaningful parens
        )

        def replace_file_write(match: re.Match) -> str:
            indent = match.group(1)
            string_lit = match.group(2)
            file_call = match.group(3)
            return f"{indent}__LAMIA_FILE_WRITE__({string_lit}, {file_call})"

        return re.sub(file_write_pattern, replace_file_write, source_code)

    def _process_callable_file_write_expressions(self, source_code: str) -> str:
        """Catch-all for ``[var =] expr -> File(...)`` not handled by the string-literal pass.

        Handles function calls and assignments::

            developer(specs=specs) -> File(str, "src/app.py")
            code = developer(specs=specs) -> File(str, "src/app.py")
            result = "prompt" -> File(HTML, "out.html")   # assignment case also caught here
        """
        _ALREADY = ('__LAMIA_FILE_WRITE__', '__LAMIA_TYPED_EXPR__', '__LAMIA_WEB_RT__')
        _FILE_RE = re.compile(r'\s*->\s*(File\([^\n]+\))\s*$')

        lines = source_code.split('\n')
        result: list[str] = []
        for line in lines:
            stripped = line.rstrip()
            lstripped = stripped.lstrip()

            if (lstripped.startswith('def ')
                    or stripped.endswith(':')
                    or any(m in stripped for m in _ALREADY)):
                result.append(line)
                continue

            m = _FILE_RE.search(stripped)
            if not m:
                result.append(line)
                continue

            file_call = m.group(1)
            before = stripped[:m.start()].rstrip()
            indent = stripped[:len(stripped) - len(lstripped)]
            expr = before.lstrip()

            assign_match = re.match(r'(\w+)\s*=\s*(.*)', expr, re.DOTALL)
            if assign_match:
                var = assign_match.group(1)
                call = assign_match.group(2).strip()
                result.append(f"{indent}{var} = __LAMIA_FILE_WRITE__({call}, {file_call})")
            else:
                result.append(f"{indent}__LAMIA_FILE_WRITE__({expr}, {file_call})")

        return '\n'.join(result)

    def _process_typed_prompt_expressions(self, source_code: str) -> str:
        """Process ``"prompt" -> Type`` and ``var = "prompt" -> Type`` expressions.

        Rewrites to a ``__LAMIA_TYPED_EXPR__`` marker that the AST transformer
        converts into ``lamia.run("prompt", return_type=Type)``::

            "generate html" -> HTML
            →  __LAMIA_TYPED_EXPR__(HTML, "generate html")

            result = "generate html" -> HTML
            →  result = __LAMIA_TYPED_EXPR__(HTML, "generate html")

        Must run **after** ``_process_file_write_expressions`` so that
        ``"prompt" -> File(...)`` is not consumed here.
        """
        typed_prompt_pattern = (
            r'^(\s*)'                              # indent
            r'(?:(\w+)\s*=\s*)?'                   # optional: variable =
            + _QUOTED_STRING +
            r'\s*->\s*'                            # arrow
            r'([A-Za-z_]\w*(?:\[[^\]]+\])?)'      # TypeName or TypeName[Inner]
            r'\s*$'                                # end of line
        )

        def replace_typed_prompt(match: re.Match) -> str:
            indent = match.group(1)
            variable = match.group(2)
            string_lit = match.group(3)
            type_name = match.group(4)
            marker = f"__LAMIA_TYPED_EXPR__({type_name}, {string_lit})"
            if variable:
                return f"{indent}{variable} = {marker}"
            return f"{indent}{marker}"

        return re.sub(typed_prompt_pattern, replace_typed_prompt, source_code, flags=re.MULTILINE)

    def _process_callable_typed_expressions(self, source_code: str) -> str:
        """Process ``expr -> Type`` where *expr* is NOT a string literal.

        Catches patterns that the string-literal pass did not consume, e.g.
        function calls from ``.hu`` files::

            greet(name="Alice") -> HTML
            result = greet(name="Alice") -> HTML[Model]

        Rewrites to ``__LAMIA_TYPED_EXPR__`` markers identical to the string-
        literal case so the AST transformer handles them uniformly.
        """
        _ARROW_TYPE_RE = re.compile(
            r'\s*->\s*([A-Za-z_]\w*(?:\[[^\]]+\])?)\s*$'
        )
        _ALREADY_PROCESSED = ('__LAMIA_TYPED_EXPR__', '__LAMIA_FILE_WRITE__', '__LAMIA_WEB_RT__')

        lines = source_code.split('\n')
        result: list[str] = []
        for line in lines:
            stripped = line.rstrip()
            lstripped = stripped.lstrip()

            if (lstripped.startswith('def ')
                    or stripped.endswith(':')
                    or any(m in stripped for m in _ALREADY_PROCESSED)):
                result.append(line)
                continue

            m = _ARROW_TYPE_RE.search(stripped)
            if not m:
                result.append(line)
                continue

            type_name = m.group(1)
            before = stripped[:m.start()].rstrip()
            indent = stripped[:len(stripped) - len(lstripped)]
            expr = before.lstrip()

            assign_match = re.match(r'(\w+)\s*=\s*(.*)', expr, re.DOTALL)
            if assign_match:
                var = assign_match.group(1)
                call = assign_match.group(2).strip()
                result.append(f"{indent}{var} = __LAMIA_TYPED_EXPR__({type_name}, {call})")
            else:
                result.append(f"{indent}__LAMIA_TYPED_EXPR__({type_name}, {expr})")

        return '\n'.join(result)

    def _generate_unique_key(self, content: str) -> str:
        """Generate a unique key for content."""
        return hashlib.md5(content.encode()).hexdigest()[:8]
