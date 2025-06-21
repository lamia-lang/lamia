import ast
import inspect
from typing import Any, Callable, List, Tuple, Union, Type
from ..base import BaseValidator, ValidationResult

class FunctionalValidator(BaseValidator):
    """Validates if a function produces expected outputs for given inputs."""
    
    def __init__(self, test_cases: List[Tuple[Tuple[Any, ...], Union[Any, Type[Exception]]]], strict: bool = True):
        """
        Initialize the functional validator.
        
        Args:
            test_cases: List of (inputs, expected_output) tuples where:
                - inputs: Tuple of arguments to pass to the function
                - expected_output: Expected return value OR expected exception type
            strict: Whether to use strict validation mode
        
        Examples:
            test_cases = [
                ((1, 2), 3),  # func(1, 2) should return 3
                ((0,), ValueError),  # func(0) should raise ValueError
                ((0, 0), 0),  # func(0, 0) should return 0
            ]
        """
        super().__init__(strict=strict)
        self.test_cases = test_cases

    @property
    def initial_hint(self) -> str:
        """Generate a clear hint with formatted test cases for LLM understanding."""
        hint_parts = ["Please provide a function that satisfies all the given test cases:"]
        
        for i, (inputs, expected) in enumerate(self.test_cases):
            if inspect.isclass(expected) and issubclass(expected, Exception):
                # Format exception case
                args_str = ", ".join(repr(arg) for arg in inputs)
                hint_parts.append(f"  - func({args_str}) should raise {expected.__name__}")
            else:
                # Format normal return value case
                args_str = ", ".join(repr(arg) for arg in inputs)
                hint_parts.append(f"  - func({args_str}) should return {repr(expected)}")
        
        hint_parts.append("")
        hint_parts.append("Provide only the function definition, no explanation or extra text.")
        
        return "\n".join(hint_parts)

    @classmethod
    def name(cls) -> str:
        return "functional"

    def _parse_function_from_response(self, response: str) -> Callable:
        """Extract and compile a function from the response text."""
        response = response.strip()
        
        # Try to find function definition in the response
        lines = response.split('\n')
        func_lines = []
        in_function = False
        
        for line in lines:
            if line.strip().startswith('def '):
                in_function = True
            if in_function:
                func_lines.append(line)
                # Simple heuristic: function ends when we hit a line with no indentation
                # and it's not empty and doesn't start with def
                if line.strip() and not line.startswith(' ') and not line.startswith('\t') and not line.strip().startswith('def'):
                    if len(func_lines) > 1:  # We have more than just the def line
                        func_lines.pop()  # Remove the line that's not part of function
                        break
        
        if not func_lines:
            # If no function found, try to treat entire response as function
            func_code = response
        else:
            func_code = '\n'.join(func_lines)
        
        # Create a local namespace and execute the function definition
        namespace = {}
        try:
            exec(func_code, namespace)
        except Exception as e:
            raise ValueError(f"Failed to parse function from response: {e}")
        
        # Find the function in the namespace (exclude built-ins)
        functions = [v for k, v in namespace.items() if callable(v) and not k.startswith('__')]
        
        if not functions:
            raise ValueError("No function found in the response")
        
        if len(functions) > 1:
            raise ValueError("Multiple functions found in response, please provide only one function")
        
        return functions[0]

    def _test_function(self, func: Callable) -> ValidationResult:
        """Test the function against all test cases."""
        for i, (inputs, expected) in enumerate(self.test_cases):
            try:
                if inspect.isclass(expected) and issubclass(expected, Exception):
                    # Expecting an exception
                    try:
                        result = func(*inputs)
                        return ValidationResult(
                            is_valid=False,
                            error_message=f"Test case {i+1}: Expected {expected.__name__} but got result: {result}",
                            hint=self.initial_hint
                        )
                    except Exception as e:
                        if not isinstance(e, expected):
                            return ValidationResult(
                                is_valid=False,
                                error_message=f"Test case {i+1}: Expected {expected.__name__} but got {type(e).__name__}: {e}",
                                hint=self.initial_hint
                            )
                        # Exception matches, continue to next test case
                else:
                    # Expecting a normal return value
                    result = func(*inputs)
                    if result != expected:
                        return ValidationResult(
                            is_valid=False,
                            error_message=f"Test case {i+1}: Expected {expected} but got {result} for inputs {inputs}",
                            hint=self.initial_hint
                        )
            except Exception as e:
                if not (inspect.isclass(expected) and issubclass(expected, Exception)):
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Test case {i+1}: Unexpected exception {type(e).__name__}: {e} for inputs {inputs}",
                        hint=self.initial_hint
                    )
                # If we expected an exception but got a different one, it's handled above
        
        # All test cases passed
        return ValidationResult(is_valid=True, validated_text=func.__name__ if hasattr(func, '__name__') else 'function')

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        """Strict validation: function must be syntactically correct and pass all test cases."""
        try:
            func = self._parse_function_from_response(response)
            return self._test_function(func)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Failed to parse or execute function: {e}",
                hint=self.initial_hint
            )

    async def validate_permissive(self, response: str, **kwargs) -> ValidationResult:
        """Permissive validation: same as strict for functional testing."""
        # For functional validation, permissive mode is the same as strict
        # since we need the function to work correctly
        return await self.validate_strict(response, **kwargs) 