"""
Hybrid Python syntax parser for LLM commands.

The original monolithic file has been refactored into focused components:

1. preprocessors/return_type_preprocessor.py - Handles -> Type syntax preprocessing
2. detectors/llm_command_detector.py - Detects string literal commands in functions  
3. transformers/session_transformer.py - Transforms with session() blocks
4. transformers/syntax_transformer.py - Main AST transformation logic

Each component has:
- One clear public interface method
- All other methods are private helpers
- Single responsibility principle
- Clear separation of concerns

This file orchestrates all the components through the main HybridSyntaxParser class.
"""

import ast
import builtins

from typing import Dict, Any, Tuple

from .preprocessors import WithReturnTypePreprocessor
from .detectors import LLMCommandDetector
from .transformers import SessionWithTransformer, HybridSyntaxTransformer

builtins_compile = builtins.compile


def _fix_line_ranges(tree: ast.AST) -> None:
    """Ensure all AST nodes have valid line ranges for compile().

    After transformation, some nodes may have end_lineno < lineno or
    end_col_offset < col_offset which causes ValueError in compile().
    """
    for node in ast.walk(tree):
        lineno = getattr(node, 'lineno', None)
        end_lineno = getattr(node, 'end_lineno', None)
        if lineno is not None and end_lineno is not None and end_lineno < lineno:
            node.end_lineno = lineno
        col = getattr(node, 'col_offset', None)
        end_col = getattr(node, 'end_col_offset', None)
        if (col is not None and end_col is not None
                and lineno == end_lineno and end_col < col):
            node.end_col_offset = col


def _walk_paired_trees(src_node: ast.AST, out_node: ast.AST, smap: dict) -> None:
    """Walk two ASTs with identical structure, building {output_line: source_line}.

    *src_node* carries original source line numbers (preserved through the
    AST transformation pipeline).  *out_node* carries line numbers from the
    final output string.  Both trees have the same structure because
    out_node was parsed from src_node's unparse.
    """
    for attr in ('body', 'orelse', 'finalbody', 'handlers'):
        src_children = getattr(src_node, attr, None)
        out_children = getattr(out_node, attr, None)
        if not isinstance(src_children, list) or not isinstance(out_children, list):
            continue
        for s_child, o_child in zip(src_children, out_children):
            if not (isinstance(s_child, ast.AST) and isinstance(o_child, ast.AST)):
                continue
            if not (hasattr(s_child, 'lineno') and hasattr(o_child, 'lineno')):
                continue

            orig_line = s_child.lineno
            out_start = o_child.lineno
            out_end = getattr(o_child, 'end_lineno', out_start) or out_start

            for ln in range(out_start, out_end + 1):
                smap[ln] = orig_line

            _walk_paired_trees(s_child, o_child, smap)


def _densify_source_map(
    source_map: Dict[int, int], transformed_code: str, source_code: str
) -> Dict[int, int]:
    """Fill missing transformed lines with monotonic interpolation anchors.

    AST-derived mapping is sparse (mostly statement lines). The debugger, however,
    can stop on any executable line number. This helper guarantees a mapping for
    every transformed line so line events never fall back to raw transformed
    positions.
    """
    transformed_line_count = len(transformed_code.splitlines())
    source_line_count = max(len(source_code.splitlines()), 1)

    if transformed_line_count <= 0:
        return {}

    if not source_map:
        return {
            ln: min(max(ln, 1), source_line_count)
            for ln in range(1, transformed_line_count + 1)
        }

    anchors = sorted(
        (out_ln, min(max(src_ln, 1), source_line_count))
        for out_ln, src_ln in source_map.items()
        if 1 <= out_ln <= transformed_line_count
    )
    if not anchors:
        return {
            ln: min(max(ln, 1), source_line_count)
            for ln in range(1, transformed_line_count + 1)
        }

    # Ensure strict monotonic source anchors to avoid backwards jumps while stepping.
    monotonic_anchors = []
    prev_src = 1
    for out_ln, src_ln in anchors:
        src_ln = max(src_ln, prev_src)
        monotonic_anchors.append((out_ln, src_ln))
        prev_src = src_ln

    dense_map: Dict[int, int] = {}
    first_out, first_src = monotonic_anchors[0]

    for out_ln in range(1, first_out):
        dense_map[out_ln] = max(1, first_src - (first_out - out_ln))
    dense_map[first_out] = first_src

    for (left_out, left_src), (right_out, right_src) in zip(
        monotonic_anchors, monotonic_anchors[1:]
    ):
        dense_map[left_out] = left_src
        gap = right_out - left_out
        if gap <= 1:
            dense_map[right_out] = right_src
            continue

        for out_ln in range(left_out + 1, right_out):
            ratio = (out_ln - left_out) / gap
            interp = left_src + round((right_src - left_src) * ratio)
            dense_map[out_ln] = min(max(interp, left_src), right_src)
        dense_map[right_out] = right_src

    last_out, last_src = monotonic_anchors[-1]
    for out_ln in range(last_out + 1, transformed_line_count + 1):
        dense_map[out_ln] = min(last_src + (out_ln - last_out), source_line_count)

    return dense_map


class HybridSyntaxParser:
    """Main interface for parsing and transforming hybrid syntax code.
    
    This class orchestrates the parsing pipeline:
    1. Preprocessing (return type extraction)
    2. Detection (LLM command identification)
    3. Transformation (AST transformation to executable code)
    """
    
    def __init__(self, lamia_var_name: str = 'lamia'):
        """Initialize the parser with configuration.
        
        Args:
            lamia_var_name: Variable name for lamia instance in generated code
        """
        self.lamia_var_name = lamia_var_name
        self._preprocessor = WithReturnTypePreprocessor()
        self._detector = LLMCommandDetector()
        self._syntax_transformer = HybridSyntaxTransformer(lamia_var_name)

    def _build_transformed_tree(self, source_code: str) -> Tuple[ast.AST, str]:
        """Return transformed AST and preprocessed source used to build it."""
        processed_code, return_types = self._preprocessor.preprocess(source_code)
        tree = ast.parse(processed_code)
        session_transformer = SessionWithTransformer(return_types)
        tree = session_transformer.transform_sessions(tree)

        # Use a fresh transformer instance each run to avoid stale detector state.
        transformer = HybridSyntaxTransformer(self.lamia_var_name)
        transformer.detector.visit(tree)
        transformed_tree = transformer.visit(tree)
        ast.fix_missing_locations(transformed_tree)
        return transformed_tree, processed_code
    
    def parse(self, source_code: str) -> Dict[str, Any]:
        """
        Parse hybrid syntax and return information about LLM commands.
        
        This is the main public interface method for analysis.
        
        Args:
            source_code: Raw source code with hybrid syntax
            
        Returns:
            Dictionary containing:
            - llm_functions: Detected LLM functions with metadata
            - with_return_types: Extracted return types from with statements
        """
        # Step 1: Preprocess return type syntax
        processed_code, return_types = self._preprocessor.preprocess(source_code)
        
        # Step 2: Detect LLM commands
        llm_functions = self._detector.detect_commands(processed_code)
        
        return {
            'llm_functions': llm_functions,
            'with_return_types': return_types
        }
    
    def transform(self, source_code: str) -> str:
        """
        Transform hybrid syntax code into executable Python.
        
        This is the main public interface method for transformation.
        
        Args:
            source_code: Raw source code with hybrid syntax
            
        Returns:
            Transformed executable Python code
        """
        transformed_tree, _ = self._build_transformed_tree(source_code)
        return self._syntax_transformer._ast_to_source(transformed_tree)

    def compile(self, source_code: str, filename: str = "<lamia>") -> Any:
        """Transform and compile to a code object preserving original line numbers."""
        transformed_tree, _ = self._build_transformed_tree(source_code)
        _fix_line_ranges(transformed_tree)
        return builtins_compile(transformed_tree, filename, "exec")

    def transform_with_source_map(self, source_code: str) -> Tuple[str, Dict[int, int]]:
        """Transform code and return (transformed_code, {output_line: original_line}).

        Instead of comparing two independently-parsed ASTs, this feeds the
        AST (which carries original source line numbers) directly into the
        transformer.  The transformed AST and the re-parsed output have
        *identical* structure, so a trivial lockstep walk builds the map.
        """
        transformed_tree, processed_code = self._build_transformed_tree(source_code)
        transformed_code = self._syntax_transformer._ast_to_source(transformed_tree)

        source_map: Dict[int, int] = {}
        try:
            output_tree = ast.parse(transformed_code)
            _walk_paired_trees(transformed_tree, output_tree, source_map)
        except SyntaxError:
            pass

        dense_map = _densify_source_map(source_map, transformed_code, processed_code)
        return transformed_code, dense_map