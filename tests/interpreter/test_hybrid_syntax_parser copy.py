"""
Unit tests for hybrid_syntax_parser module.
"""

import pytest
import ast
from unittest.mock import Mock, AsyncMock
from lamia.interpreter.hybrid_syntax_parser import LLMCommandDetector, HybridSyntaxTransformer, HybridSyntaxParser
from lamia.interpreter.hybrid_executor import HybridExecutor
from lamia.types import HTML, JSON


class TestLLMCommandDetector:
    """Test the LLM command detection functionality."""
    
    def test_detect_simple_string_function(self):
        """Test detection of function with simple string command."""
        code = '''
def my_function():
    "Tell me a joke"
'''
        tree = ast.parse(code)
        detector = LLMCommandDetector()
        detector.visit(tree)
        
        assert 'my_function' in detector.llm_functions
        assert detector.llm_functions['my_function']['command'] == "Tell me a joke"
        assert detector.llm_functions['my_function']['type'] == 'function_with_string_command'
        assert detector.llm_functions['my_function']['return_type'] is None
    
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
        detector = LLMCommandDetector()
        detector.visit(tree)
        
        assert 'generate_story' in detector.llm_functions
        command = detector.llm_functions['generate_story']['command']
        assert "Write a short story about a robot" in command
        assert "Make it heartwarming and include dialogue." in command
    
    def test_detect_function_with_return_type(self):
        """Test detection of function with return type annotation."""
        code = '''
def generate_html() -> HTML[MyModel]:
    "Generate HTML for a login form"
'''
        tree = ast.parse(code)
        detector = LLMCommandDetector()
        detector.visit(tree)
        
        assert 'generate_html' in detector.llm_functions
        return_type = detector.llm_functions['generate_html']['return_type']
        assert return_type['type'] == 'parametric'
        assert return_type['base_type'] == 'HTML'
        assert return_type['inner_type'] == 'MyModel'
        assert detector.llm_functions['generate_html']['command'] == "Generate HTML for a login form"
    
    def test_ignore_function_with_multiple_statements(self):
        """Test that functions with multiple statements are ignored."""
        code = '''
def complex_function():
    x = 1
    return "not an llm command"
'''
        tree = ast.parse(code)
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
        detector = LLMCommandDetector()
        detector.visit(tree)
        
        assert 'complex_type' in detector.llm_functions
        # Note: This is a simplified test - complex generic parsing might need more work
        return_type = detector.llm_functions['complex_type']['return_type']
        assert 'Dict' in return_type['full_type']


class TestHybridSyntaxTransformer:
    """Test the syntax transformation functionality."""
    
    def test_transform_simple_string_function(self):
        """Test transformation of function with simple string command."""
        code = '''
def tell_joke():
    "Tell me a joke"
'''
        transformer = HybridSyntaxTransformer()
        transformed = transformer.transform_code(code)
        
        # def functions should remain synchronous and use lamia.run
        assert 'def tell_joke' in transformed
        assert 'lamia.run(' in transformed
        assert 'Tell me a joke' in transformed
    
    def test_transform_function_with_return_type(self):
        """Test transformation of function with return type."""
        code = '''
def generate_html() -> HTML:
    "Generate simple HTML"
'''
        transformer = HybridSyntaxTransformer()
        transformed = transformer.transform_code(code)
        
        # def functions should remain synchronous and use lamia.run
        assert 'def generate_html' in transformed
        assert "return_type='HTML'" in transformed
        assert 'lamia.run(' in transformed
    
    def test_transform_multiline_string(self):
        """Test transformation of multiline string command."""
        code = '''
def generate_story():
    """Write a story about robots
    and their adventures in space"""
'''
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
        transformer = HybridSyntaxTransformer()
        transformed = transformer.transform_code(code)
        
        # Should remain as regular function
        assert 'def regular_function():' in transformed
        assert 'async' not in transformed
        assert 'lamia.run' not in transformed
    
    def test_preserve_regular_strings(self):
        """Test that regular strings outside functions are preserved."""
        code = '''
message = "This is a regular string"
print("Another regular string")
'''
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
        transformer = HybridSyntaxTransformer(lamia_var_name='my_lamia')
        transformed = transformer.transform_code(code)
        
        assert 'my_lamia.run(' in transformed
        assert transformed.count('lamia.run(') == 1  # Only in "my_lamia.run(", not standalone
    
    def test_transform_async_function(self):
        """Test transformation of async function with string command."""
        code = '''
async def tell_joke_async():
    "Tell me a joke"
'''
        transformer = HybridSyntaxTransformer()
        transformed = transformer.transform_code(code)
        
        # async def functions should use await lamia.run_async
        assert 'async def tell_joke_async' in transformed
        assert 'await lamia.run_async(' in transformed
        assert 'Tell me a joke' in transformed


class TestHybridSyntaxParser:
    """Test the main parser interface."""
    
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
    
    def test_parse_simple_function(self, parser):
        """Test parsing function with string command."""
        code = '''
def tell_joke():
    "Tell me a joke"
'''
        result = parser.parse(code)
        
        assert 'tell_joke' in result['llm_functions']
        assert result['llm_functions']['tell_joke']['command'] == "Tell me a joke"
        assert result['llm_functions']['tell_joke']['return_type'] is None
    
    def test_parse_function_with_return_type(self, parser):
        """Test parsing function with return type."""
        code = '''
def generate_html() -> HTML:
    "Generate simple HTML"
'''
        result = parser.parse(code)
        
        assert 'generate_html' in result['llm_functions']
        return_type = result['llm_functions']['generate_html']['return_type']
        assert return_type['type'] == 'simple'
        assert return_type['base_type'] == 'HTML'
    
    def test_transform_code(self, parser):
        """Test code transformation."""
        code = '''
def test_func():
    "Test command"
'''
        transformed = parser.transform(code)
        
        assert 'def test_func' in transformed
        assert 'lamia.run(' in transformed
    
    @pytest.mark.asyncio
    async def test_execute_simple_code(self, executor, mock_lamia):
        """Test executing code with function containing string command."""
        mock_lamia.run_async.return_value = "Mock response"
        
        code = '''
def tell_joke():
    "Tell me a joke"

result = tell_joke()
'''
        local_dict = await executor.execute(code)
        
        # The function should be in local scope
        assert 'tell_joke' in local_dict
        assert callable(local_dict['tell_joke'])
    
    @pytest.mark.asyncio
    async def test_execute_function(self, executor, mock_lamia):
        """Test executing a specific function."""
        mock_lamia.run.return_value = "Mock joke"
        
        code = '''
def tell_joke():
    "Tell me a joke"
'''
        
        result = await executor.execute_function('tell_joke', code)
        
        # Should have called run and returned the result
        mock_lamia.run.assert_called_once_with("Tell me a joke")
        assert result == "Mock joke"
    
    @pytest.mark.asyncio
    async def test_execute_function_with_return_type(self, executor, mock_lamia):
        """Test executing function with return type."""
        mock_lamia.run.return_value = "<html>Test</html>"
        
        code = '''
def generate_html() -> HTML:
    "Generate simple HTML"
'''
        
        result = await executor.execute_function('generate_html', code)
        
        # Should have called run with return_type parameter
        mock_lamia.run.assert_called_once_with("Generate simple HTML", return_type='HTML')
        assert result == "<html>Test</html>"
    
    @pytest.mark.asyncio
    async def test_execute_function_not_found(self, executor):
        """Test error when function is not found."""
        code = 'x = 1'
        
        with pytest.raises(ValueError, match="Function 'nonexistent' not found"):
            await executor.execute_function('nonexistent', code)


class TestIntegrationScenarios:
    """Test realistic usage scenarios."""
    
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
        
        # Create executor for this test
        from lamia.interpreter.hybrid_executor import HybridExecutor
        executor = HybridExecutor(mock_lamia)
        local_dict = await executor.execute(code)
        
        # Check that both regular Python and LLM function are available
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
        
        # Create executor for this test
        from lamia.interpreter.hybrid_executor import HybridExecutor
        executor = HybridExecutor(mock_lamia)
        result = await executor.execute_function('generate_story', code)
        
        # Check that the multiline command was passed correctly
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
        
        # def functions remain synchronous, complex return types are preserved
        assert 'def complex_function' in transformed
        assert "return_type='HTML[MyModel]'" in transformed
        # Note: Complex generic type parsing might need refinement
    
    @pytest.mark.asyncio
    async def test_function_with_parameters(self, parser, mock_lamia):
        """Test that function parameters are preserved."""
        mock_lamia.run.return_value = "Generated content"
        
        code = '''
def generate_content(topic: str, style: str = "casual"):
    f"Write about {topic} in a {style} style"
'''
        
        # Note: This test demonstrates a limitation - we can't easily handle
        # f-strings or complex expressions in the current implementation
        # The function would need to have a simple string literal
        code_simple = '''
def generate_content(topic: str, style: str = "casual"):
    "Write content based on the given parameters"
'''
        
        # Create executor for this test
        from lamia.interpreter.hybrid_executor import HybridExecutor
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
        from lamia.interpreter.hybrid_executor import HybridExecutor
        return HybridExecutor(mock_lamia)
    
    def test_parameter_detection(self, parser):
        """Test detection of function parameters."""
        code = '''
def generate_report(weather_data: WeatherModel, location: str):
    "Generate report for {location} using {weather_data}"
'''
        result = parser.parse(code)
        
        assert 'generate_report' in result['llm_functions']
        params = result['llm_functions']['generate_report']['parameters']
        assert len(params) == 2
        assert params[0]['name'] == 'weather_data'
        assert params[0]['type'] == 'WeatherModel'
        assert params[1]['name'] == 'location'
        assert params[1]['type'] == 'str'
    
    def test_parameter_substitution_transformation(self, parser):
        """Test that parameter substitution is handled in transformation."""
        code = '''
def generate_summary(data: dict, title: str):
    "Create summary titled '{title}' using {data}"
'''
        transformed = parser.transform(code)
        
        # Should contain format call with parameter substitution
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
        
        # Should not contain format call
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
        from lamia.interpreter.hybrid_executor import HybridExecutor
        return HybridExecutor(mock_lamia)
    
    def test_parametric_return_type_detection(self, parser):
        """Test detection of parametric return types."""
        code = '''
def get_weather() -> HTML[WeatherModel]:
    "Get weather from API"
'''
        result = parser.parse(code)
        
        func_info = result['llm_functions']['get_weather']
        return_type = func_info['return_type']
        
        assert return_type['type'] == 'parametric'
        assert return_type['base_type'] == 'HTML'
        assert return_type['inner_type'] == 'WeatherModel'
    
    def test_simple_return_type_detection(self, parser):
        """Test detection of simple return types."""
        code = '''
def get_data() -> JSON:
    "Get some data"
'''
        result = parser.parse(code)
        
        func_info = result['llm_functions']['get_data']
        return_type = func_info['return_type']
        
        assert return_type['type'] == 'simple'
        assert return_type['base_type'] == 'JSON'
    
    def test_no_return_type(self, parser):
        """Test functions without return types."""
        code = '''
def simple_text():
    "Generate some text"
'''
        result = parser.parse(code)
        
        func_info = result['llm_functions']['simple_text']
        assert func_info['return_type'] is None