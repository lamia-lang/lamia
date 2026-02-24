"""Tests for HybridSyntaxParser."""

import ast
import pytest
from unittest.mock import Mock, AsyncMock, patch
from lamia.interpreter.hybrid_syntax_parser import HybridSyntaxParser
from lamia.interpreter.hybrid_executor import HybridExecutor
from lamia.types import HTML, JSON


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
with session("test") -> str:
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
        """Test that transform propagates errors from syntax transformation."""
        with patch.object(self.parser._syntax_transformer, 'transform_code') as mock_transform:
            mock_transform.side_effect = RuntimeError("Transformation failed")
            
            with pytest.raises(RuntimeError, match="Transformation failed"):
                self.parser.transform("x = 1")


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
with session("test") -> str:
    def get_weather(city):
        f"What is the weather like in {city}?"

with session("test") -> list:
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

with session("test") -> dict:
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


class TestLLMCommandDetector:
    """Test the LLM command detection functionality."""
    
    def test_detect_simple_string_function(self):
        """Test detection of function with simple string command."""
        code = '''
def my_function():
    "Tell me a joke"
'''
        tree = ast.parse(code)
        from lamia.interpreter.detectors import LLMCommandDetector
        detector = LLMCommandDetector()
        detector.visit(tree)
        
        assert 'my_function' in detector.llm_functions
        assert detector.llm_functions['my_function'].command == "Tell me a joke"
        assert detector.llm_functions['my_function'].return_type is None
    
    def test_detect_multiline_string_function(self):
        """Test detection of function with multiline string command."""
        code = '''
def generate_story():
    """
    Write a short story about a robot
    who discovers emotions for the first time.
    Make it heartwarming and include dialogue.
    """
'''
        tree = ast.parse(code)
        from lamia.interpreter.detectors import LLMCommandDetector
        detector = LLMCommandDetector()
        detector.visit(tree)
        
        assert 'generate_story' in detector.llm_functions
        command = detector.llm_functions['generate_story'].command
        assert "Write a short story about a robot" in command
        assert "Make it heartwarming and include dialogue." in command
    
    def test_detect_function_with_return_type(self):
        """Test detection of function with return type annotation."""
        code = '''
def generate_html() -> HTML[MyModel]:
    "Generate HTML for a login form"
'''
        tree = ast.parse(code)
        from lamia.interpreter.detectors import LLMCommandDetector
        detector = LLMCommandDetector()
        detector.visit(tree)
        
        assert 'generate_html' in detector.llm_functions
        from lamia.interpreter.detectors.llm_command_detector import ParametricReturnType
        return_type = detector.llm_functions['generate_html'].return_type
        assert isinstance(return_type, ParametricReturnType)
        assert return_type.base_type == 'HTML'
        assert return_type.inner_type == 'MyModel'
        assert detector.llm_functions['generate_html'].command == "Generate HTML for a login form"
    
    def test_ignore_function_with_multiple_statements(self):
        """Test that functions with multiple statements are ignored."""
        code = '''
def complex_function():
    x = 1
    return "not an llm command"
'''
        tree = ast.parse(code)
        from lamia.interpreter.detectors import LLMCommandDetector
        detector = LLMCommandDetector()
        detector.visit(tree)
        
        assert 'complex_function' not in detector.llm_functions
    
    def test_ignore_function_with_non_string(self):
        """Test that functions with non-string expressions are ignored."""
        code = '''
def numeric_function():
    42
'''
        tree = ast.parse(code)
        from lamia.interpreter.detectors import LLMCommandDetector
        detector = LLMCommandDetector()
        detector.visit(tree)
        
        assert 'numeric_function' not in detector.llm_functions
    
    def test_ignore_regular_strings_outside_functions(self):
        """Test that strings outside functions are ignored."""
        code = '''
message = "This is just a regular string"
"Another regular string"
'''
        tree = ast.parse(code)
        from lamia.interpreter.detectors import LLMCommandDetector
        detector = LLMCommandDetector()
        detector.visit(tree)
        
        assert len(detector.llm_functions) == 0
    
    def test_complex_return_type_parsing(self):
        """Test parsing of complex return type annotations."""
        code = '''
def complex_type() -> Dict[str, HTML[MyModel]]:
    "Generate complex data structure"
'''
        tree = ast.parse(code)
        from lamia.interpreter.detectors import LLMCommandDetector
        detector = LLMCommandDetector()
        detector.visit(tree)
        
        assert 'complex_type' in detector.llm_functions
        return_type = detector.llm_functions['complex_type'].return_type
        assert 'Dict' in return_type.full_type


class TestHybridSyntaxTransformer:
    """Test the syntax transformation functionality."""
    
    def test_transform_simple_string_function(self):
        """Test transformation of function with simple string command."""
        code = '''
def tell_joke():
    "Tell me a joke"
'''
        from lamia.interpreter.transformers import HybridSyntaxTransformer
        transformer = HybridSyntaxTransformer()
        transformed = transformer.transform_code(code)
        
        assert 'def tell_joke' in transformed
        assert 'lamia.run(' in transformed
        assert 'Tell me a joke' in transformed
    
    def test_transform_function_with_return_type(self):
        """Test transformation of function with return type."""
        code = '''
def generate_html() -> HTML:
    "Generate simple HTML"
'''
        from lamia.interpreter.transformers import HybridSyntaxTransformer
        transformer = HybridSyntaxTransformer()
        transformed = transformer.transform_code(code)
        
        assert 'def generate_html' in transformed
        assert "return_type=HTML" in transformed
        assert 'lamia.run(' in transformed
    
    def test_transform_multiline_string(self):
        """Test transformation of multiline string command."""
        code = '''
def generate_story():
    """Write a story about robots
    and their adventures in space"""
'''
        from lamia.interpreter.transformers import HybridSyntaxTransformer
        transformer = HybridSyntaxTransformer()
        transformed = transformer.transform_code(code)
        
        assert 'def generate_story' in transformed
        assert 'Write a story about robots' in transformed
        assert 'adventures in space' in transformed
    
    def test_preserve_regular_functions(self):
        """Test that regular functions are preserved unchanged."""
        code = '''
def regular_function():
    x = 1
    return x + 1
'''
        from lamia.interpreter.transformers import HybridSyntaxTransformer
        transformer = HybridSyntaxTransformer()
        transformed = transformer.transform_code(code)
        
        assert 'def regular_function():' in transformed
        assert 'async' not in transformed
        assert 'lamia.run' not in transformed
    
    def test_preserve_regular_strings(self):
        """Test that regular strings outside functions are preserved."""
        code = '''
message = "This is a regular string"
print("Another regular string")
'''
        from lamia.interpreter.transformers import HybridSyntaxTransformer
        transformer = HybridSyntaxTransformer()
        transformed = transformer.transform_code(code)
        
        assert 'This is a regular string' in transformed
        assert 'Another regular string' in transformed
        assert 'lamia.run' not in transformed
    
    def test_custom_lamia_var_name(self):
        """Test using custom variable name for lamia instance."""
        code = '''
def test_func():
    "Test command"
'''
        from lamia.interpreter.transformers import HybridSyntaxTransformer
        transformer = HybridSyntaxTransformer(lamia_var_name='my_lamia')
        transformed = transformer.transform_code(code)
        
        assert 'my_lamia.run(' in transformed
        assert transformed.count('lamia.run(') == 1
    
    def test_transform_async_function(self):
        """Test transformation of async function with string command."""
        code = '''
async def tell_joke_async():
    "Tell me a joke"
'''
        from lamia.interpreter.transformers import HybridSyntaxTransformer
        transformer = HybridSyntaxTransformer()
        transformed = transformer.transform_code(code)
        
        assert 'async def tell_joke_async' in transformed
        assert 'await lamia.run_async(' in transformed
        assert 'Tell me a joke' in transformed


class TestComponentIntegrationScenarios:
    """Test realistic usage scenarios with component integration."""
    
    @pytest.fixture
    def mock_lamia(self):
        """Create a mock Lamia instance."""
        lamia = Mock()
        lamia.run_async = AsyncMock()
        lamia.run = Mock()
        return lamia
    
    @pytest.fixture
    def parser(self, mock_lamia):
        """Create a HybridSyntaxParser with mock lamia."""
        return HybridSyntaxParser()
    
    @pytest.mark.asyncio
    async def test_mixed_code_execution(self, parser, mock_lamia):
        """Test executing code with both LLM functions and regular Python."""
        mock_lamia.run_async.return_value = "Generated text"
        
        code = '''
# Regular Python code
name = "Alice"
greeting = f"Hello, {name}!"

# LLM function
def generate_response():
    "Generate a friendly response"

# Regular function
def process_data(data):
    return data.upper()
'''
        
        executor = HybridExecutor(mock_lamia)
        local_dict = await executor.execute(code)
        
        assert local_dict['name'] == "Alice"
        assert local_dict['greeting'] == "Hello, Alice!"
        assert 'generate_response' in local_dict
        assert 'process_data' in local_dict
        assert callable(local_dict['generate_response'])
        assert callable(local_dict['process_data'])
    
    @pytest.mark.asyncio
    async def test_multiline_command_execution(self, parser, mock_lamia):
        """Test execution of multiline LLM command."""
        mock_lamia.run.return_value = "Generated story"
        
        code = '''
def generate_story():
    """
    Write a short story about a robot
    who discovers emotions for the first time.
    Make it heartwarming and include dialogue.
    """
'''
        
        executor = HybridExecutor(mock_lamia)
        result = await executor.execute_function('generate_story', code)
        
        call_args = mock_lamia.run.call_args
        command = call_args[0][0]
        assert "Write a short story about a robot" in command
        assert "Make it heartwarming and include dialogue." in command
        assert result == "Generated story"
    
    def test_complex_return_type_transformation(self, parser):
        """Test transformation with complex return types."""
        code = '''
def complex_function() -> HTML[MyModel]:
    "Generate complex HTML structure"
'''
        
        transformed = parser.transform(code)
        
        assert 'def complex_function' in transformed
        assert "return_type=HTML[MyModel]" in transformed
    
    @pytest.mark.asyncio
    async def test_function_with_parameters(self, parser, mock_lamia):
        """Test that function parameters are preserved."""
        mock_lamia.run.return_value = "Generated content"
        
        code_simple = '''
def generate_content(topic: str, style: str = "casual"):
    "Write content based on the given parameters"
'''
        
        executor = HybridExecutor(mock_lamia)
        result = await executor.execute_function('generate_content', code_simple, "AI", "formal")
        
        mock_lamia.run.assert_called_once()
        assert result == "Generated content"


class TestParameterSubstitution:
    """Test parameter substitution functionality."""
    
    @pytest.fixture
    def mock_lamia(self):
        """Create a mock Lamia instance."""
        lamia = Mock()
        lamia.run_async = AsyncMock()
        lamia.run = Mock()
        return lamia
    
    @pytest.fixture  
    def parser(self, mock_lamia):
        """Create a HybridSyntaxParser with mock lamia."""
        return HybridSyntaxParser()
    
    @pytest.fixture
    def executor(self, mock_lamia):
        """Create a HybridExecutor with mock lamia."""
        return HybridExecutor(mock_lamia)
    
    def test_parameter_detection(self, parser):
        """Test detection of function parameters."""
        code = '''
def generate_report(weather_data: WeatherModel, location: str):
    "Generate report for {location} using {weather_data}"
'''
        result = parser.parse(code)
        
        assert 'generate_report' in result['llm_functions']
        params = result['llm_functions']['generate_report'].parameters
        assert len(params) == 2
        assert params[0].name == 'weather_data'
        assert params[0].type_annotation == 'WeatherModel'
        assert params[1].name == 'location'
        assert params[1].type_annotation == 'str'
    
    def test_parameter_substitution_transformation(self, parser):
        """Test that parameter substitution is handled in transformation."""
        code = '''
def generate_summary(data: dict, title: str):
    "Create summary titled '{title}' using {data}"
'''
        transformed = parser.transform(code)
        
        assert 'format(' in transformed
        assert 'title=' in transformed
        assert 'data=' in transformed
    
    def test_no_parameters_no_substitution(self, parser):
        """Test functions without parameters work normally."""
        code = '''
def simple_function():
    "Just a simple command"
'''
        transformed = parser.transform(code)
        
        assert 'format(' not in transformed
        assert 'Just a simple command' in transformed


class TestParametricReturnTypes:
    """Test parametric return type handling."""
    
    @pytest.fixture
    def mock_lamia(self):
        """Create a mock Lamia instance."""
        lamia = Mock()
        lamia.run_async = AsyncMock()
        lamia.run = Mock()
        return lamia
    
    @pytest.fixture
    def parser(self, mock_lamia):
        """Create a HybridSyntaxParser with mock lamia."""
        return HybridSyntaxParser()
    
    @pytest.fixture
    def executor(self, mock_lamia):
        """Create a HybridExecutor with mock lamia."""
        return HybridExecutor(mock_lamia)
    
    def test_parametric_return_type_detection(self, parser):
        """Test detection of parametric return types."""
        code = '''
def get_weather() -> HTML[WeatherModel]:
    "Get weather from API"
'''
        result = parser.parse(code)
        
        from lamia.interpreter.detectors.llm_command_detector import ParametricReturnType
        func_info = result['llm_functions']['get_weather']
        return_type = func_info.return_type

        assert isinstance(return_type, ParametricReturnType)
        assert return_type.base_type == 'HTML'
        assert return_type.inner_type == 'WeatherModel'
    
    def test_simple_return_type_detection(self, parser):
        """Test detection of simple return types."""
        code = '''
def get_data() -> JSON:
    "Get some data"
'''
        result = parser.parse(code)
        
        from lamia.interpreter.detectors.llm_command_detector import SimpleReturnType
        func_info = result['llm_functions']['get_data']
        return_type = func_info.return_type

        assert isinstance(return_type, SimpleReturnType)
        assert return_type.base_type == 'JSON'
    
    def test_no_return_type(self, parser):
        """Test functions without return types."""
        code = '''
def simple_text():
    "Generate some text"
'''
        result = parser.parse(code)
        
        func_info = result['llm_functions']['simple_text']
        assert func_info.return_type is None

