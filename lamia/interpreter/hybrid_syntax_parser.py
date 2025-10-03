"""
The original monolithic hybrid_syntax_parser.py has been broken down into:

1. preprocessors/return_type_preprocessor.py - Handles -> Type syntax preprocessing
2. detectors/llm_command_detector.py - Detects string literal commands in functions  
3. transformers/session_transformer.py - Transforms with session() blocks
4. transformers/syntax_transformer.py - Main AST transformation logic
5. hybrid_parser.py - Clean main parser interface that orchestrates components

Each module now has:
- One clear public interface method
- All other methods are private helpers
- Single responsibility principle
- Clear separation of concerns

Use the new HybridSyntaxParser from hybrid_parser.py instead of this file.
"""

"""
Clean main interface for hybrid syntax parsing.

This is the main entry point that orchestrates all the parsing components.
Each component has a single public method and clear responsibilities.
"""

from typing import Dict, Any
from .preprocessors import WithReturnTypePreprocessor
from .detectors import LLMCommandDetector
from .transformers import SessionWithTransformer, HybridSyntaxTransformer
import ast


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
        # Step 1: Preprocess return type syntax
        processed_code, return_types = self._preprocessor.preprocess(source_code)
        
        # Step 2: Parse into AST
        tree = ast.parse(processed_code)
        
        # Step 3: Transform session blocks with return types
        print(f"Return types: {return_types}")
        if return_types:
            session_transformer = SessionWithTransformer(return_types)
            tree = session_transformer.transform_sessions(tree)
        
        # Step 4: Transform hybrid syntax
        transformed_code = self._syntax_transformer.transform_code(
            ast.unparse(tree) if hasattr(ast, 'unparse') else processed_code, 
            return_types
        )
        
        print(f"Transformed code: {transformed_code}")
        return transformed_code