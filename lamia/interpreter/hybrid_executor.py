"""
Hybrid syntax executor for executing transformed hybrid syntax code.

Handles execution of transformed hybrid syntax code with smart type resolution,
parameter handling, and integration with Lamia instances.
"""

import inspect
from typing import Optional, Dict, Any
from .hybrid_syntax_parser import HybridSyntaxParser


class HybridExecutor:
    """Executes hybrid syntax code with smart type resolution."""
    
    def __init__(self, lamia_instance, lamia_var_name: str = 'lamia'):
        self.lamia = lamia_instance
        self.lamia_var_name = lamia_var_name
        self.parser = HybridSyntaxParser(lamia_var_name)
    
    def parse(self, source_code: str) -> Dict[str, Any]:
        """Parse hybrid syntax and return information about LLM commands."""
        return self.parser.parse(source_code)
    
    def transform(self, source_code: str) -> str:
        """Transform hybrid syntax code into executable Python."""
        return self.parser.transform(source_code)
    
    async def execute(self, source_code: str, globals_dict: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute hybrid syntax code."""
        # Transform the code
        transformed_code = self.transform(source_code)
        
        # Prepare execution environment
        if globals_dict is None:
            globals_dict = {}
        
        # Add lamia instance to globals
        globals_dict[self.lamia_var_name] = self.lamia
        
        # Import necessary types for return type annotations
        from lamia.types import HTML, JSON
        globals_dict.update({
            'HTML': HTML,
            'JSON': JSON
        })
        
        # Execute the transformed code
        compiled_code = compile(transformed_code, '<hybrid_syntax>', 'exec')
        
        # Create a new local scope for execution
        local_dict = {}
        
        # Execute in async context
        exec(compiled_code, globals_dict, local_dict)
        
        return local_dict
    
    async def execute_function(self, func_name: str, source_code: str, *args, **kwargs) -> Any:
        """Execute a specific function from hybrid syntax code."""
        local_dict = await self.execute(source_code)
        
        if func_name not in local_dict:
            raise ValueError(f"Function '{func_name}' not found in executed code")
        
        func = local_dict[func_name]
        if not callable(func):
            raise ValueError(f"'{func_name}' is not a callable function")
        
        # Call the function
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)


class SmartTypeResolver:
    """Handles smart type resolution for LamiaResult objects.
    
    Automatically extracts the appropriate value (result_type or result_text)
    based on context for parametric return types.
    """
    
    @staticmethod
    def resolve_for_assignment(lamia_result, target_type: str) -> Any:
        """Resolve LamiaResult for typed variable assignment.
        
        Args:
            lamia_result: The LamiaResult object
            target_type: The target type string (e.g., "WeatherModel")
            
        Returns:
            Appropriate value based on context
        """
        # For parametric types, extract structured data (result_type)
        if hasattr(lamia_result, 'result_type') and lamia_result.result_type is not None:
            return lamia_result.result_type
        
        # Fallback to raw text
        return lamia_result.result_text if hasattr(lamia_result, 'result_text') else lamia_result
    
    @staticmethod
    def resolve_for_string_context(lamia_result) -> str:
        """Resolve LamiaResult for string operations or file operations.
        
        Args:
            lamia_result: The LamiaResult object
            
        Returns:
            Raw text content
        """
        # For string/file operations, extract raw text (result_text)
        if hasattr(lamia_result, 'result_text'):
            return lamia_result.result_text
        
        # Fallback to string representation
        return str(lamia_result)
    
    @staticmethod
    def resolve_for_parameter(lamia_result, param_type: Optional[str] = None) -> Any:
        """Resolve LamiaResult when passed as function parameter.
        
        Args:
            lamia_result: The LamiaResult object
            param_type: The parameter type annotation (if available)
            
        Returns:
            Appropriate value based on parameter type
        """
        # If parameter has a specific type annotation, try to match it
        if param_type and hasattr(lamia_result, 'result_type') and lamia_result.result_type is not None:
            return lamia_result.result_type
        
        # Default to raw text for untyped parameters
        return lamia_result.result_text if hasattr(lamia_result, 'result_text') else lamia_result


# Example usage patterns:
"""
# Create executor
executor = HybridExecutor(lamia_instance)

# Parse hybrid syntax code  
code = '''
def get_weather() -> HTML[WeatherModel]:
    "https://api.weather.com/current"

def generate_report(weather_data: WeatherModel, location: str):
    "Generate report for {location} using {weather_data}"
'''

# Execute code
local_scope = await executor.execute(code)

# Call functions
weather_result = local_scope['get_weather']()  # Returns LamiaResult
weather_data: WeatherModel = weather_result   # Smart resolution to structured data

# Or execute specific function
report = await executor.execute_function('generate_report', code, weather_data, "NYC")
"""