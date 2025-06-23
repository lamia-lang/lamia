import ast
import inspect
import re
import signal
import sys
import tempfile
import os
import subprocess
import json
from typing import Any, Callable, List, Tuple, Union, Type, Optional
from ..base import BaseValidator, ValidationResult

class FunctionalValidator(BaseValidator):
    """
    Validator for Python functions with multi-layered security architecture.
    
    SECURITY MODEL:
    ===============
    
    Layer 1: AST Analysis (Pre-execution)
    - Blocks dangerous imports (os, sys, subprocess, etc.)
    - Blocks dangerous operations (exec, eval, file operations, etc.)
    - Prevents network and system calls before execution
    
    Layer 2: Namespace Restrictions (In-process execution)
    - Restricted __builtins__ with only safe Python built-ins
    - Exception types available for proper error handling
    - No access to dangerous modules or functions
    
    Layer 3: Timeout Protection
    - Signal-based timeout for infinite loop protection
    - Configurable execution timeout (default: 5 seconds)
    
    Layer 4: Docker Isolation (Optional)
    - Complete process isolation in containers
    - Read-only filesystem, no network access
    - Memory and CPU limits
    - Non-root user execution
    - Auto-cleanup of containers
    - Graceful fallback to namespace execution if Docker unavailable
    
    DOCKER SECURITY:
    ================
    Even within Docker containers, the following restrictions apply:
    - AST analysis still blocks dangerous code before execution
    - Restricted __builtins__ within the container
    - Container runs as 'nobody' user (non-root)
    - Read-only filesystem prevents file modifications
    - No network access (--network none)
    - Memory and CPU limits prevent resource exhaustion
    - Temporary filesystem limited to 10MB
    
    This means dangerous operations like os.system(), file I/O, network calls,
    and imports are blocked BOTH by code analysis AND container restrictions.
    
    FALLBACK BEHAVIOR:
    ==================
    - If Docker is requested but unavailable, automatically falls back to namespace execution
    - CI/CD environments without Docker daemon still work correctly
    - Warning messages inform users about fallback behavior
    - All security layers except Docker isolation remain active
    
    USAGE:
    ======
    ```python
    # Basic usage (namespace execution)
    validator = FunctionalValidator([((1, 2), 3), ((5, 3), 8)])
    
    # Docker execution (with fallback)
    validator = FunctionalValidator([((1, 2), 3)], use_docker=True)
    
    # Test function
    result = await validator.validate_strict("def add(a, b): return a + b")
    ```
    """
    
    def __init__(self, 
                 test_cases: List[Tuple[Tuple[Any, ...], Union[Any, Type[Exception]]]], 
                 strict: bool = True, 
                 execution_timeout: int = 5,
                 use_docker: bool = False,
                 docker_image: str = "python:3.11-alpine",
                 docker_memory_limit: str = "128m"):
        """
        Initialize FunctionalValidator.
        
        Args:
            test_cases: List of (input_tuple, expected_output) pairs
            strict: If True, expects clean code. If False, handles chatty responses
            execution_timeout: Timeout in seconds for function execution
            use_docker: If True, execute in Docker container for security (with fallback)
            docker_image: Docker image to use for execution
            docker_memory_limit: Memory limit for Docker container
        """
        self.test_cases = test_cases
        self.strict = strict
        self.execution_timeout = execution_timeout
        self.docker_image = docker_image
        self.docker_memory_limit = docker_memory_limit
        
        # Check Docker availability if requested
        if use_docker:
            if self._check_docker_available():
                self.use_docker = True
                print("✅ Docker is available - using containerized execution")
            else:
                self.use_docker = False
                print("⚠️  Docker is not available - falling back to namespace execution")
        else:
            self.use_docker = False

    def _check_docker_available(self) -> bool:
        """Check if Docker is available and running."""
        try:
            # Check if docker command exists
            result = subprocess.run(['docker', '--version'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode != 0:
                return False
                
            # Check if Docker daemon is running by trying to list containers
            result = subprocess.run(['docker', 'ps'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
            return result.returncode == 0
            
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
        except Exception:
            # Any other exception means Docker is not properly available
            return False

    @property
    def name(self) -> str:
        return "functional"

    @property
    def initial_hint(self) -> str:
        """Generate a clear hint with formatted test cases for LLM understanding."""
        security_note = ""
        if self.use_docker:
            security_note = "\n⚠️  Code will be executed in an isolated Docker container for security."
        
        hint_parts = [
            "Please provide a Python function that satisfies all the given test cases.",
            "",
            "IMPORTANT FORMATTING REQUIREMENTS:",
            "- Use triple backticks with 'python' language identifier: ```python",
            "- Do NOT include any explanations, comments, or text outside the code block",
            "- Provide ONLY the function definition inside the code block",
            "- Use only standard Python built-ins (no external imports)" + security_note,
            "",
            "Test cases your function must satisfy:"
        ]
        
        for i, (inputs, expected) in enumerate(self.test_cases):
            if inspect.isclass(expected) and issubclass(expected, Exception):
                # Format exception case
                args_str = ", ".join(repr(arg) for arg in inputs)
                hint_parts.append(f"  - func({args_str}) should raise {expected.__name__}")
            else:
                # Format normal return value case
                args_str = ", ".join(repr(arg) for arg in inputs)
                hint_parts.append(f"  - func({args_str}) should return {repr(expected)}")
        
        hint_parts.extend([
            "",
            "Example format:",
            "```python",
            "def your_function_name(param1, param2):",
            "    # your implementation",
            "    return result",
            "```"
        ])
        
        return "\n".join(hint_parts)

    def _validate_code_safety(self, code: str) -> None:
        """
        Validate that the code is safe to execute.
        Raises ValueError if code contains potentially dangerous operations.
        """
        # Parse the code to check for dangerous operations
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise ValueError(f"Syntax error in code: {e}")
        
        dangerous_patterns = [
            # File operations
            'open', 'file', 'read', 'write', 'remove', 'delete', 'mkdir', 'rmdir',
            # Network operations  
            'socket', 'urllib', 'requests', 'http', 'ftp', 'telnet',
            # System operations
            'os', 'sys', 'subprocess', 'exec', 'eval', 'compile', 'globals', 'locals',
            # Import restrictions
            '__import__', 'importlib',
        ]
        
        for node in ast.walk(tree):
            # Check for imports of dangerous modules
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module_names = []
                if isinstance(node, ast.Import):
                    module_names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_names = [node.module]
                
                for module_name in module_names:
                    if any(dangerous in module_name.lower() for dangerous in dangerous_patterns):
                        raise ValueError(f"Potentially dangerous import detected: {module_name}")
            
            # Check for dangerous function calls or attribute access
            if isinstance(node, ast.Name) and node.id in dangerous_patterns:
                raise ValueError(f"Potentially dangerous operation detected: {node.id}")
            
            if isinstance(node, ast.Attribute) and node.attr in dangerous_patterns:
                raise ValueError(f"Potentially dangerous attribute access detected: {node.attr}")

    def _create_safe_namespace(self) -> dict:
        """Create a safe execution namespace with only allowed built-ins."""
        safe_builtins = {
            'abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'divmod', 
            'enumerate', 'filter', 'float', 'format', 'frozenset', 'hex', 
            'int', 'isinstance', 'issubclass', 'iter', 'len', 'list', 'map', 
            'max', 'min', 'oct', 'ord', 'pow', 'range', 'reversed', 'round', 
            'set', 'slice', 'sorted', 'str', 'sum', 'tuple', 'type', 'zip',
            # Exception types that might be needed
            'ValueError', 'TypeError', 'IndexError', 'KeyError', 'AttributeError',
            'ZeroDivisionError', 'StopIteration', 'RuntimeError', 'ArithmeticError',
            'OverflowError', 'FloatingPointError', 'AssertionError'
        }
        
        # Create restricted built-ins
        restricted_builtins = {}
        namespace = {'__name__': '__restricted__'}
        
        for name in safe_builtins:
            if hasattr(__builtins__, name):
                builtin_obj = getattr(__builtins__, name)
                restricted_builtins[name] = builtin_obj
                # Also make exceptions directly available in namespace
                if name.endswith('Error') or name in ['StopIteration']:
                    namespace[name] = builtin_obj
        
        namespace['__builtins__'] = restricted_builtins
        return namespace

    def _execute_with_timeout(self, func: Callable, args: tuple, timeout: int = 5) -> Any:
        """Execute function with timeout protection (for in-process execution)."""
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Function execution exceeded {timeout} seconds")
        
        # Set up timeout (Unix systems only)
        if hasattr(signal, 'SIGALRM'):
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout)
        
        try:
            result = func(*args)
            return result
        finally:
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)  # Cancel the alarm
                signal.signal(signal.SIGALRM, old_handler)

    def _execute_in_docker(self, func_code: str, test_inputs: tuple, timeout: int = 5) -> dict:
        """
        Execute function in Docker container for maximum security isolation.
        Returns dict with 'result', 'success', and 'error' keys.
        """
        # Security check BEFORE Docker execution
        self._validate_code_safety(func_code)
        
        # Create test script that will run in Docker with additional security restrictions
        test_script = f'''
import json
import sys
import traceback

# Additional security: Restrict dangerous built-ins
ALLOWED_BUILTINS = {{
    'abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'divmod', 
    'enumerate', 'filter', 'float', 'format', 'frozenset', 'hex', 
    'int', 'isinstance', 'issubclass', 'iter', 'len', 'list', 'map', 
    'max', 'min', 'oct', 'ord', 'pow', 'range', 'reversed', 'round', 
    'set', 'slice', 'sorted', 'str', 'sum', 'tuple', 'type', 'zip',
    # Exception types
    'ValueError', 'TypeError', 'IndexError', 'KeyError', 'AttributeError',
    'ZeroDivisionError', 'StopIteration', 'RuntimeError', 'ArithmeticError',
    'OverflowError', 'FloatingPointError', 'AssertionError'
}}

# Create restricted namespace
restricted_builtins = {{}}
for name in ALLOWED_BUILTINS:
    if hasattr(__builtins__, name):
        restricted_builtins[name] = getattr(__builtins__, name)

# Add exception types to global namespace for easy access
for name in ['ValueError', 'TypeError', 'IndexError', 'KeyError', 'AttributeError',
             'ZeroDivisionError', 'StopIteration', 'RuntimeError', 'ArithmeticError',
             'OverflowError', 'FloatingPointError', 'AssertionError']:
    if name in restricted_builtins:
        globals()[name] = restricted_builtins[name]

# Replace __builtins__ with restricted version
__builtins__ = restricted_builtins

# Function code from user (already security-checked on host)
try:
    exec("""
{func_code}
""", globals())
except Exception as e:
    print(json.dumps({{"success": False, "error": f"Code execution failed: {{type(e).__name__}}: {{str(e)}}"}}))
    sys.exit(1)

# Get the function from globals
func_name = None
for name, obj in globals().items():
    if callable(obj) and not name.startswith('_') and name not in [
        'json', 'sys', 'traceback', 'exec', 'globals', 'locals'
    ] and name not in ALLOWED_BUILTINS:
        func_name = name
        break

if func_name is None:
    print(json.dumps({{"success": False, "error": "No function found"}}))
    sys.exit(1)

func = globals()[func_name]
test_inputs = {repr(test_inputs)}

try:
    result = func(*test_inputs)
    # Convert result to JSON-serializable format
    if hasattr(result, '__dict__'):
        result = str(result)  # Convert objects to string
    print(json.dumps({{"success": True, "result": result}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": f"{{type(e).__name__}}: {{str(e)}}"}}))
'''

        # Write script to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_script)
            temp_script_path = f.name

        try:
            # Run Docker container
            docker_cmd = [
                'docker', 'run',
                '--rm',  # Remove container after execution
                '--memory', self.docker_memory_limit,  # Memory limit
                '--cpus', '0.5',  # CPU limit
                '--network', 'none',  # No network access
                '--user', 'nobody',  # Run as non-root user
                '--read-only',  # Read-only filesystem
                '--tmpfs', '/tmp:rw,noexec,nosuid,size=10m',  # Small temp space
                '-v', f'{temp_script_path}:/script.py:ro',  # Mount script read-only
                self.docker_image,
                'python', '/script.py'
            ]
            
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 2  # Slightly longer timeout for Docker overhead
            )
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': f"Docker execution failed: {result.stderr.strip()}"
                }
            
            # Parse JSON response
            try:
                return json.loads(result.stdout.strip())
            except json.JSONDecodeError:
                return {
                    'success': False,
                    'error': f"Invalid response from Docker: {result.stdout.strip()}"
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f"Docker execution timed out after {timeout} seconds"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Docker execution error: {str(e)}"
            }
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_script_path)
            except OSError:
                pass  # Ignore cleanup errors

    def _parse_clean_function(self, response: str) -> Callable:
        """Parse function from clean code (strict mode)."""
        response = response.strip()
        
        # Security check
        self._validate_code_safety(response)
        
        # For strict mode, expect relatively clean function definitions
        # Look for function definition
        lines = response.split('\n')
        func_lines = []
        in_function = False
        
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith('def '):
                in_function = True
                func_lines = [line]  # Start fresh from this def
            elif in_function:
                func_lines.append(line)
                # Function ends when we hit a line with no indentation that's not empty
                # and doesn't start with def, unless it's the last line
                if (stripped_line and 
                    not line.startswith(' ') and 
                    not line.startswith('\t') and 
                    not stripped_line.startswith('def') and
                    not stripped_line.startswith('#')):
                    # This line is not part of the function
                    func_lines.pop()  # Remove the line that's not part of function
                    break
        
        if not func_lines:
            raise ValueError("No function definition found in the response")
        
        func_code = '\n'.join(func_lines)
        
        # For Docker execution, we'll return the code string wrapped in a special object
        if self.use_docker:
            class DockerFunction:
                def __init__(self, code):
                    self.code = code
                    self.__name__ = "docker_function"
            return DockerFunction(func_code)
        
        # Create a safe namespace and execute the function definition
        namespace = self._create_safe_namespace()
        try:
            exec(func_code, namespace)
        except Exception as e:
            raise ValueError(f"Failed to parse function from response: {e}")
        
        # Find the function in the namespace (exclude built-ins)
        functions = [v for k, v in namespace.items() if callable(v) and not k.startswith('__')]
        
        if not functions:
            raise ValueError("No function found in the response")
        
        if len(functions) > 1:
            function_names = [name for name, obj in namespace.items() if callable(obj) and not name.startswith('__')]
            raise ValueError(f"Multiple functions found in response: {', '.join(function_names)}. Please provide only one function")
        
        return functions[0]

    def _parse_chatty_function(self, response: str) -> Callable:
        """Parse function from chatty LLM response (permissive mode)."""
        response = response.strip()
        
        # Try to extract function from markdown code blocks first
        code_block_patterns = [
            r'```python\s*\n(.*?)\n```',  # ```python\n...\n```
            r'```\s*\n(.*?)\n```',       # ```\n...\n```
        ]
        
        extracted_code = None
        for pattern in code_block_patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                extracted_code = match.group(1).strip()
                break
        
        # If no code block found, try to find function definition in the entire response
        if not extracted_code:
            # Try to find any code that looks like a function using more aggressive regex
            def_matches = re.findall(r'def\s+\w+\s*\([^)]*\):[^def]*?(?=def|\Z)', response, re.DOTALL | re.MULTILINE)
            if def_matches:
                # Take the first function definition found
                extracted_code = def_matches[0].strip()
            else:
                extracted_code = response
        
        # Security check
        self._validate_code_safety(extracted_code)
        
        # Normalize indentation to handle cases where function is indented
        lines = extracted_code.split('\n')
        if lines:
            # Find the minimum indentation of non-empty lines
            min_indent = float('inf')
            for line in lines:
                if line.strip():  # Skip empty lines
                    indent = len(line) - len(line.lstrip())
                    min_indent = min(min_indent, indent)
            
            # Remove the minimum indentation from all lines
            if min_indent != float('inf') and min_indent > 0:
                normalized_lines = []
                for line in lines:
                    if line.strip():  # Non-empty line
                        normalized_lines.append(line[min_indent:] if len(line) >= min_indent else line)
                    else:  # Empty line
                        normalized_lines.append('')
                extracted_code = '\n'.join(normalized_lines)
        
        # Now extract function definition from the code
        lines = extracted_code.split('\n')
        func_lines = []
        in_function = False
        
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith('def '):
                in_function = True
                func_lines = [line]  # Start fresh from this def
            elif in_function:
                func_lines.append(line)
                # Function ends when we hit a line with no indentation that's not empty
                # and doesn't start with def, unless it's the last line
                if (stripped_line and 
                    not line.startswith(' ') and 
                    not line.startswith('\t') and 
                    not stripped_line.startswith('def') and
                    not stripped_line.startswith('#')):
                    # This line is not part of the function
                    func_lines.pop()  # Remove the line that's not part of function
                    break
        
        if not func_lines:
            raise ValueError("No function definition found in the response")
        
        func_code = '\n'.join(func_lines)
        
        # For Docker execution, we'll return the code string wrapped in a special object
        if self.use_docker:
            class DockerFunction:
                def __init__(self, code):
                    self.code = code
                    self.__name__ = "docker_function"
            return DockerFunction(func_code)
        
        # Create a safe namespace and execute the function definition
        namespace = self._create_safe_namespace()
        try:
            exec(func_code, namespace)
        except Exception as e:
            raise ValueError(f"Failed to parse function from response: {e}")
        
        # Find the function in the namespace (exclude built-ins)
        functions = [v for k, v in namespace.items() if callable(v) and not k.startswith('__')]
        
        if not functions:
            raise ValueError("No function found in the response")
        
        if len(functions) > 1:
            function_names = [name for name, obj in namespace.items() if callable(obj) and not name.startswith('__')]
            raise ValueError(f"Multiple functions found in response: {', '.join(function_names)}. Please provide only one function")
        
        return functions[0]

    def _test_function(self, func: Union[Callable, Any]) -> ValidationResult:
        """Test the function against all test cases."""
        for i, (inputs, expected) in enumerate(self.test_cases):
            try:
                if inspect.isclass(expected) and issubclass(expected, Exception):
                    # Expecting an exception
                    try:
                        if self.use_docker and hasattr(func, 'code'):
                            # Try Docker execution first
                            result_data = self._execute_in_docker(func.code, inputs, self.execution_timeout)
                            
                            # If Docker fails, fall back to namespace execution
                            if not result_data['success'] and 'Docker' in result_data['error']:
                                print(f"⚠️  Docker execution failed, falling back to namespace execution: {result_data['error']}")
                                # Parse and execute in namespace instead
                                namespace = self._create_safe_namespace()
                                exec(func.code, namespace)
                                functions = [v for k, v in namespace.items() if callable(v) and not k.startswith('__')]
                                if functions:
                                    fallback_func = functions[0]
                                    try:
                                        result = self._execute_with_timeout(fallback_func, inputs, self.execution_timeout)
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
                                        continue
                                else:
                                    return ValidationResult(
                                        is_valid=False,
                                        error_message=f"Test case {i+1}: No function found after fallback",
                                        hint=self.initial_hint
                                    )
                            
                            if result_data['success']:
                                return ValidationResult(
                                    is_valid=False,
                                    error_message=f"Test case {i+1}: Expected {expected.__name__} but got result: {result_data['result']}",
                                    hint=self.initial_hint
                                )
                            else:
                                # Check if the error matches expected exception
                                error_msg = result_data['error']
                                if expected.__name__ in error_msg:
                                    continue  # Expected exception occurred
                                else:
                                    return ValidationResult(
                                        is_valid=False,
                                        error_message=f"Test case {i+1}: Expected {expected.__name__} but got: {error_msg}",
                                        hint=self.initial_hint
                                    )
                        else:
                            # In-process execution
                            result = self._execute_with_timeout(func, inputs, self.execution_timeout)
                            return ValidationResult(
                                is_valid=False,
                                error_message=f"Test case {i+1}: Expected {expected.__name__} but got result: {result}",
                                hint=self.initial_hint
                            )
                    except TimeoutError:
                        return ValidationResult(
                            is_valid=False,
                            error_message=f"Test case {i+1}: Function execution timed out after {self.execution_timeout} seconds",
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
                    try:
                        if self.use_docker and hasattr(func, 'code'):
                            # Try Docker execution first
                            result_data = self._execute_in_docker(func.code, inputs, self.execution_timeout)
                            
                            # If Docker fails, fall back to namespace execution
                            if not result_data['success'] and 'Docker' in result_data['error']:
                                print(f"⚠️  Docker execution failed, falling back to namespace execution: {result_data['error']}")
                                # Parse and execute in namespace instead
                                namespace = self._create_safe_namespace()
                                exec(func.code, namespace)
                                functions = [v for k, v in namespace.items() if callable(v) and not k.startswith('__')]
                                if functions:
                                    fallback_func = functions[0]
                                    result = self._execute_with_timeout(fallback_func, inputs, self.execution_timeout)
                                else:
                                    return ValidationResult(
                                        is_valid=False,
                                        error_message=f"Test case {i+1}: No function found after fallback",
                                        hint=self.initial_hint
                                    )
                            elif not result_data['success']:
                                return ValidationResult(
                                    is_valid=False,
                                    error_message=f"Test case {i+1}: Execution failed: {result_data['error']}",
                                    hint=self.initial_hint
                                )
                            else:
                                result = result_data['result']
                        else:
                            # In-process execution
                            result = self._execute_with_timeout(func, inputs, self.execution_timeout)
                        
                        if result != expected:
                            return ValidationResult(
                                is_valid=False,
                                error_message=f"Test case {i+1}: Expected {expected} but got {result} for inputs {inputs}",
                                hint=self.initial_hint
                            )
                    except TimeoutError:
                        return ValidationResult(
                            is_valid=False,
                            error_message=f"Test case {i+1}: Function execution timed out after {self.execution_timeout} seconds",
                            hint=self.initial_hint
                        )
            except Exception as e:
                if not (inspect.isclass(expected) and issubclass(expected, Exception)):
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Test case {i+1}: Unexpected exception {type(e).__name__}: {e}",
                        hint=self.initial_hint
                    )
        
        # All test cases passed
        return ValidationResult(
            is_valid=True,
            validated_text=getattr(func, '__name__', 'function'),
            hint=self.initial_hint
        )

    async def validate_strict(self, response: Union[str, Callable], **kwargs) -> ValidationResult:
        """
        Strict validation: expects clean function code or actual function objects.
        Does not handle chatty responses. Only supports Python functions.
        """
        try:
            if callable(response):
                # Direct function validation - still apply security checks by testing
                return self._test_function(response)
            elif isinstance(response, str):
                # Parse clean function code
                func = self._parse_clean_function(response)
                return self._test_function(func)
            else:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Expected function or string, got {type(response).__name__}",
                    hint=self.initial_hint
                )
        except ValueError as e:
            return ValidationResult(
                is_valid=False,
                error_message=str(e),
                hint=self.initial_hint
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Failed to parse or execute function: {e}",
                hint=self.initial_hint
            )

    async def validate_permissive(self, response: Union[str, Callable], **kwargs) -> ValidationResult:
        """
        Permissive validation: extract function from chatty LLM responses.
        This mode scrapes away chattiness and explanation text.
        Only supports Python functions.
        """
        try:
            if callable(response):
                # Direct function validation
                return self._test_function(response)
            elif isinstance(response, str):
                # Parse chatty response and extract function
                func = self._parse_chatty_function(response)
                return self._test_function(func)
            else:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Expected function or string, got {type(response).__name__}",
                    hint=self.initial_hint
                )
        except ValueError as e:
            return ValidationResult(
                is_valid=False,
                error_message=str(e),
                hint=self.initial_hint
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Failed to parse or execute function: {e}",
                hint=self.initial_hint
            )

    @staticmethod
    def can_handle_content(content: str) -> bool:
        """
        Smart detection: Check if the content appears to be Python function code.
        This enables automatic selection of FunctionalValidator for string validation.
        
        Args:
            content: String content to analyze
            
        Returns:
            True if content appears to be Python function code
        """
        if not isinstance(content, str):
            return False
            
        content = content.strip()
        if not content:
            return False
        
        # Check for function definition patterns
        function_indicators = [
            r'def\s+\w+\s*\([^)]*\)\s*:',  # def function_name():
            r'```python\s*\n.*def\s+\w+',   # ```python\ndef function
            r'lambda\s+[^:]+:',             # lambda expressions
        ]
        
        for pattern in function_indicators:
            if re.search(pattern, content, re.DOTALL | re.MULTILINE):
                return True
        
        # Check for Python-specific keywords in context
        python_keywords = ['def', 'return', 'if', 'else', 'for', 'while', 'try', 'except']
        lines = content.split('\n')
        python_line_count = 0
        
        for line in lines:
            line = line.strip()
            if any(keyword in line for keyword in python_keywords):
                python_line_count += 1
        
        # If more than 30% of non-empty lines contain Python keywords, likely Python code
        non_empty_lines = len([line for line in lines if line.strip()])
        if non_empty_lines > 0 and python_line_count / non_empty_lines > 0.3:
            return True
            
        return False

    @staticmethod
    def suggest_test_cases_from_content(content: str) -> List[Tuple[Tuple[Any, ...], Any]]:
        """
        Smart suggestion: Extract potential test cases from content or comments.
        
        Args:
            content: String content to analyze
            
        Returns:
            List of suggested test cases in the format [((inputs...), expected_output)]
        """
        suggested_cases = []
        
        # Look for example calls in comments or docstrings
        example_patterns = [
            r'#.*(\w+)\(([^)]+)\).*(?:should return|returns?|=>|=)\s*([^\n]+)',
            r'""".*(\w+)\(([^)]+)\).*(?:should return|returns?|=>|=)\s*([^\n]+)',
            r'>>>.*(\w+)\(([^)]+)\)\s*([^\n]+)',  # Doctest style
        ]
        
        for pattern in example_patterns:
            matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
            for match in matches:
                try:
                    func_name, args_str, expected_str = match
                    # Try to parse arguments and expected result
                    args = eval(f"({args_str})")
                    if not isinstance(args, tuple):
                        args = (args,)
                    expected = eval(expected_str.strip())
                    suggested_cases.append((args, expected))
                except:
                    continue  # Skip if parsing fails
        
        # If no examples found, suggest simple test cases based on function signature
        if not suggested_cases:
            func_match = re.search(r'def\s+(\w+)\s*\(([^)]*)\)', content)
            if func_match:
                func_name, params = func_match.groups()
                param_list = [p.strip().split('=')[0].strip() for p in params.split(',') if p.strip()]
                
                # Suggest basic test cases based on parameter count
                if len(param_list) == 1:
                    suggested_cases = [((1,), 1), ((0,), 0)]
                elif len(param_list) == 2:
                    suggested_cases = [((1, 2), 3), ((0, 0), 0)]
                elif len(param_list) >= 3:
                    suggested_cases = [((1, 2, 3), 6), ((0, 0, 0), 0)]
        
        return suggested_cases

    @staticmethod
    def _should_use_docker_for_content(content: str) -> bool:
        """
        Determine if Docker should be used based on content analysis.
        
        Args:
            content: String content to analyze
            
        Returns:
            True if Docker is recommended for this content
        """
        # Use Docker for potentially risky content
        risky_patterns = [
            r'import\s+os',
            r'import\s+sys',
            r'import\s+subprocess',
            r'exec\s*\(',
            r'eval\s*\(',
            r'open\s*\(',
            r'file\s*\(',
        ]
        
        for pattern in risky_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        # Use Docker for complex functions (more than 10 lines)
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        if len(lines) > 10:
            return True
            
        return False 