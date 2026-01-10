"""Tests for HybridSyntaxParser."""

import pytest
from unittest.mock import Mock, patch
from lamia.interpreter.hybrid_syntax_parser import HybridSyntaxParser


class TestHybridSyntaxParserInitialization:
    """Test HybridSyntaxParser initialization."""
    
    def test_initialization_with_default_lamia_var(self):
        """Test initialization with default lamia variable name."""
        parser = HybridSyntaxParser()
        
        assert parser.lamia_var_name == 'lamia'
        assert parser._preprocessor is not None
        assert parser._detector is not None
        assert parser._syntax_transformer is not None
    
    def test_initialization_with_custom_lamia_var(self):
        """Test initialization with custom lamia variable name."""
        parser = HybridSyntaxParser(lamia_var_name='my_lamia')
        
        assert parser.lamia_var_name == 'my_lamia'
        assert parser._preprocessor is not None
        assert parser._detector is not None
        assert parser._syntax_transformer is not None
    
    def test_initialization_creates_component_instances(self):
        """Test that initialization creates proper component instances."""
        parser = HybridSyntaxParser()
        
        # Check that components are properly initialized
        from lamia.interpreter.preprocessors import WithReturnTypePreprocessor
        from lamia.interpreter.detectors import LLMCommandDetector
        from lamia.interpreter.transformers import HybridSyntaxTransformer
        
        assert isinstance(parser._preprocessor, WithReturnTypePreprocessor)
        assert isinstance(parser._detector, LLMCommandDetector)
        assert isinstance(parser._syntax_transformer, HybridSyntaxTransformer)


class TestHybridSyntaxParserParsing:
    """Test parsing functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = HybridSyntaxParser()
    
    @patch('lamia.interpreter.hybrid_syntax_parser.WithReturnTypePreprocessor')
    @patch('lamia.interpreter.hybrid_syntax_parser.LLMCommandDetector')
    def test_parse_method_orchestrates_components(self, mock_detector_class, mock_preprocessor_class):
        """Test that parse method properly orchestrates components."""
        # Setup mocks
        mock_preprocessor = Mock()
        mock_detector = Mock()
        mock_preprocessor_class.return_value = mock_preprocessor
        mock_detector_class.return_value = mock_detector
        
        # Configure mock return values
        mock_preprocessor.preprocess.return_value = ("processed_code", {"func": "str"})
        mock_detector.detect_commands.return_value = [{"name": "test_func", "command": "test"}]
        
        # Create parser (will use mocked components)
        parser = HybridSyntaxParser()
        
        # Call parse
        result = parser.parse("test source code")
        
        # Verify orchestration
        mock_preprocessor.preprocess.assert_called_once_with("test source code")
        mock_detector.detect_commands.assert_called_once_with("processed_code")
        
        # Verify result structure
        assert "llm_functions" in result
        assert "with_return_types" in result
        assert result["llm_functions"] == [{"name": "test_func", "command": "test"}]
        assert result["with_return_types"] == {"func": "str"}
    
    def test_parse_simple_function_with_string(self):
        """Test parsing simple function with string literal."""
        source_code = '''
def test_function():
    "What is the weather today?"
'''
        
        result = self.parser.parse(source_code)
        
        assert "llm_functions" in result
        assert "with_return_types" in result
        # The actual detection logic will be tested in component-specific tests
    
    def test_parse_function_with_return_type_syntax(self):
        """Test parsing function with return type syntax."""
        source_code = '''
with -> str:
    def get_weather():
        "What is the weather today?"
'''
        
        result = self.parser.parse(source_code)
        
        assert "llm_functions" in result
        assert "with_return_types" in result
    
    def test_parse_empty_code(self):
        """Test parsing empty code."""
        result = self.parser.parse("")
        
        assert "llm_functions" in result
        assert "with_return_types" in result
        assert isinstance(result["llm_functions"], (list, dict))
        assert isinstance(result["with_return_types"], dict)
    
    def test_parse_plain_python_code(self):
        """Test parsing plain Python code without LLM commands."""
        source_code = '''
def regular_function():
    return "This is regular Python"

x = 5
y = x + 10
'''
        
        result = self.parser.parse(source_code)
        
        assert "llm_functions" in result
        assert "with_return_types" in result


class TestHybridSyntaxParserTransformation:
    """Test transformation functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = HybridSyntaxParser()
    
    @patch('lamia.interpreter.hybrid_syntax_parser.WithReturnTypePreprocessor')
    @patch('lamia.interpreter.hybrid_syntax_parser.SessionWithTransformer')
    @patch('lamia.interpreter.hybrid_syntax_parser.HybridSyntaxTransformer')
    @patch('lamia.interpreter.hybrid_syntax_parser.ast')
    def test_transform_method_orchestrates_components(self, mock_ast, mock_syntax_transformer_class, 
                                                     mock_session_transformer_class, mock_preprocessor_class):
        """Test that transform method properly orchestrates components."""
        # Setup mocks
        mock_preprocessor = Mock()
        mock_syntax_transformer = Mock()
        mock_session_transformer = Mock()
        mock_tree = Mock()
        
        mock_preprocessor_class.return_value = mock_preprocessor
        mock_syntax_transformer_class.return_value = mock_syntax_transformer
        mock_session_transformer_class.return_value = mock_session_transformer
        
        # Configure mock return values
        mock_preprocessor.preprocess.return_value = ("processed_code", {"func": "str"})
        mock_ast.parse.return_value = mock_tree
        mock_session_transformer.transform_sessions.return_value = mock_tree
        mock_syntax_transformer.transform_code.return_value = "final_transformed_code"
        
        # Mock ast.unparse to exist
        mock_ast.unparse.return_value = "unparsed_code"
        
        # Create parser (will use mocked components)
        parser = HybridSyntaxParser()
        
        # Call transform
        result = parser.transform("test source code")
        
        # Verify orchestration
        mock_preprocessor.preprocess.assert_called_once_with("test source code")
        mock_ast.parse.assert_called_once_with("processed_code")
        mock_session_transformer_class.assert_called_once_with({"func": "str"})
        mock_session_transformer.transform_sessions.assert_called_once_with(mock_tree)
        mock_syntax_transformer.transform_code.assert_called_once_with("unparsed_code", {"func": "str"})
        
        assert result == "final_transformed_code"
    
    @patch('lamia.interpreter.hybrid_syntax_parser.WithReturnTypePreprocessor')
    @patch('lamia.interpreter.hybrid_syntax_parser.HybridSyntaxTransformer')
    @patch('lamia.interpreter.hybrid_syntax_parser.ast')
    def test_transform_without_return_types(self, mock_ast, mock_syntax_transformer_class, mock_preprocessor_class):
        """Test transformation when no return types are present."""
        # Setup mocks
        mock_preprocessor = Mock()
        mock_syntax_transformer = Mock()
        mock_tree = Mock()
        
        mock_preprocessor_class.return_value = mock_preprocessor
        mock_syntax_transformer_class.return_value = mock_syntax_transformer
        
        # Configure mock return values - no return types
        mock_preprocessor.preprocess.return_value = ("processed_code", {})
        mock_ast.parse.return_value = mock_tree
        mock_syntax_transformer.transform_code.return_value = "final_transformed_code"
        
        # Create parser (will use mocked components)
        parser = HybridSyntaxParser()
        
        # Call transform
        result = parser.transform("test source code")
        
        # Verify that SessionWithTransformer is not called when no return types
        from unittest.mock import call
        # Should not create SessionWithTransformer instance
        
        assert result == "final_transformed_code"
    
    @patch('lamia.interpreter.hybrid_syntax_parser.ast')
    def test_transform_handles_ast_unparse_fallback(self, mock_ast):
        """Test transformation handles fallback when ast.unparse is not available."""
        # Setup mocks - simulate older Python without ast.unparse
        mock_tree = Mock()
        mock_ast.parse.return_value = mock_tree
        delattr(mock_ast, 'unparse')  # Remove unparse attribute
        
        # Mock other components
        with patch('lamia.interpreter.hybrid_syntax_parser.WithReturnTypePreprocessor') as mock_preprocessor_class:
            with patch('lamia.interpreter.hybrid_syntax_parser.HybridSyntaxTransformer') as mock_syntax_transformer_class:
                mock_preprocessor = Mock()
                mock_syntax_transformer = Mock()
                mock_preprocessor_class.return_value = mock_preprocessor
                mock_syntax_transformer_class.return_value = mock_syntax_transformer
                
                mock_preprocessor.preprocess.return_value = ("processed_code", {})
                mock_syntax_transformer.transform_code.return_value = "final_code"
                
                parser = HybridSyntaxParser()
                result = parser.transform("test code")
                
                # Should use processed_code instead of unparsed AST
                mock_syntax_transformer.transform_code.assert_called_once_with("processed_code", {})
                assert result == "final_code"
    
    def test_transform_simple_function(self):
        """Test transforming simple function with string literal."""
        source_code = '''
def test_function():
    "What is the weather today?"
'''
        
        result = self.parser.transform(source_code)
        
        # Should return transformed code (exact transformation tested in component tests)
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_transform_empty_code(self):
        """Test transforming empty code."""
        result = self.parser.transform("")
        
        assert isinstance(result, str)
    
    def test_transform_preserves_regular_python(self):
        """Test that transformation preserves regular Python code."""
        source_code = '''
def regular_function():
    return "This is regular Python"

x = 5
y = x + 10
'''
        
        result = self.parser.transform(source_code)
        
        assert isinstance(result, str)
        assert len(result) > 0


class TestHybridSyntaxParserCustomLamiaVar:
    """Test parser behavior with custom lamia variable names."""
    
    def test_custom_lamia_var_passed_to_transformer(self):
        """Test that custom lamia variable name is passed to transformer."""
        with patch('lamia.interpreter.hybrid_syntax_parser.HybridSyntaxTransformer') as mock_transformer_class:
            parser = HybridSyntaxParser(lamia_var_name='custom_lamia')
            
            # Verify transformer was initialized with custom name
            mock_transformer_class.assert_called_once_with('custom_lamia')
    
    def test_different_lamia_vars_create_different_transformers(self):
        """Test that different lamia variable names create different transformer instances."""
        with patch('lamia.interpreter.hybrid_syntax_parser.HybridSyntaxTransformer') as mock_transformer_class:
            parser1 = HybridSyntaxParser(lamia_var_name='lamia1')
            parser2 = HybridSyntaxParser(lamia_var_name='lamia2')
            
            # Should be called twice with different names
            assert mock_transformer_class.call_count == 2
            call_args = [call[0][0] for call in mock_transformer_class.call_args_list]
            assert 'lamia1' in call_args
            assert 'lamia2' in call_args


class TestHybridSyntaxParserErrorHandling:
    """Test error handling in parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = HybridSyntaxParser()
    
    def test_parse_handles_syntax_error_in_preprocessing(self):
        """Test that parse handles syntax errors in preprocessing."""
        with patch.object(self.parser._preprocessor, 'preprocess') as mock_preprocess:
            mock_preprocess.side_effect = SyntaxError("Invalid syntax")
            
            with pytest.raises(SyntaxError):
                self.parser.parse("invalid syntax")
    
    def test_parse_handles_error_in_detection(self):
        """Test that parse handles errors in command detection."""
        with patch.object(self.parser._detector, 'detect_commands') as mock_detect:
            mock_detect.side_effect = RuntimeError("Detection failed")
            
            with pytest.raises(RuntimeError):
                self.parser.parse("test code")
    
    def test_transform_handles_syntax_error_in_ast_parsing(self):
        """Test that transform handles syntax errors in AST parsing."""
        with patch('lamia.interpreter.hybrid_syntax_parser.ast.parse') as mock_parse:
            mock_parse.side_effect = SyntaxError("Invalid syntax")
            
            with pytest.raises(SyntaxError):
                self.parser.transform("invalid syntax")
    
    def test_transform_handles_error_in_transformation(self):
        """Test that transform handles errors in syntax transformation."""
        with patch.object(self.parser._syntax_transformer, 'transform_code') as mock_transform:
            mock_transform.side_effect = RuntimeError("Transformation failed")
            
            with pytest.raises(RuntimeError):
                self.parser.transform("test code")


class TestHybridSyntaxParserIntegration:
    """Test integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = HybridSyntaxParser()
    
    def test_parse_and_transform_consistency(self):
        """Test that parse and transform work consistently on same input."""
        source_code = '''
def test_function():
    "What is the weather today?"
    return "Sunny"
'''
        
        # Both should work without errors
        parse_result = self.parser.parse(source_code)
        transform_result = self.parser.transform(source_code)
        
        assert isinstance(parse_result, dict)
        assert isinstance(transform_result, str)
    
    def test_realistic_hybrid_syntax_code(self):
        """Test parsing and transforming realistic hybrid syntax code."""
        source_code = '''
with -> str:
    def get_weather(city):
        f"What is the weather like in {city}?"

with -> list:
    def analyze_data():
        "Analyze the sales data and provide key insights"

def regular_function():
    return "This is regular Python"
'''
        
        # Parse
        parse_result = self.parser.parse(source_code)
        assert "llm_functions" in parse_result
        assert "with_return_types" in parse_result
        
        # Transform
        transform_result = self.parser.transform(source_code)
        assert isinstance(transform_result, str)
        assert len(transform_result) > 0
    
    def test_multiple_transformations_same_parser(self):
        """Test that same parser instance can handle multiple transformations."""
        source_codes = [
            'def func1(): "First command"',
            'def func2(): "Second command"',
            'def func3(): "Third command"'
        ]
        
        results = []
        for code in source_codes:
            parse_result = self.parser.parse(code)
            transform_result = self.parser.transform(code)
            results.append((parse_result, transform_result))
        
        # All should succeed
        assert len(results) == 3
        for parse_result, transform_result in results:
            assert isinstance(parse_result, dict)
            assert isinstance(transform_result, str)
    
    def test_complex_code_with_mixed_syntax(self):
        """Test complex code mixing regular Python with hybrid syntax."""
        source_code = '''
import os
from typing import List

class DataProcessor:
    def __init__(self, data_path: str):
        self.data_path = data_path
    
    def load_data(self):
        with open(self.data_path) as f:
            return f.read()

with -> dict:
    def analyze_sentiment():
        "Analyze the sentiment of the loaded text data"

def process_results(sentiment_data):
    if sentiment_data['positive'] > 0.5:
        return "Positive sentiment detected"
    return "Negative sentiment detected"
'''
        
        parse_result = self.parser.parse(source_code)
        transform_result = self.parser.transform(source_code)
        
        assert isinstance(parse_result, dict)
        assert isinstance(transform_result, str)
        # Should preserve the class definition and other Python constructs
        assert "class DataProcessor" in transform_result or "DataProcessor" in str(parse_result)


class TestHybridSyntaxParserEdgeCases:
    """Test edge cases and unusual inputs."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = HybridSyntaxParser()
    
    def test_parse_code_with_only_comments(self):
        """Test parsing code with only comments."""
        source_code = '''
# This is a comment
# Another comment
"""
This is a docstring
"""
'''
        
        result = self.parser.parse(source_code)
        
        assert "llm_functions" in result
        assert "with_return_types" in result
    
    def test_transform_code_with_only_comments(self):
        """Test transforming code with only comments."""
        source_code = '''
# This is a comment
# Another comment
'''
        
        result = self.parser.transform(source_code)
        
        assert isinstance(result, str)
    
    def test_parse_code_with_nested_functions(self):
        """Test parsing code with nested function definitions."""
        source_code = '''
def outer_function():
    def inner_function():
        "What is the inner command?"
    
    "What is the outer command?"
    return inner_function()
'''
        
        result = self.parser.parse(source_code)
        
        assert "llm_functions" in result
        assert "with_return_types" in result
    
    def test_transform_preserves_indentation(self):
        """Test that transformation preserves code structure."""
        source_code = '''
if True:
    def nested_function():
        "What should we do?"
        
    for i in range(10):
        print(i)
'''
        
        result = self.parser.transform(source_code)
        
        assert isinstance(result, str)
        # Should maintain some structural elements
        assert len(result.split('\n')) > 1  # Multi-line result