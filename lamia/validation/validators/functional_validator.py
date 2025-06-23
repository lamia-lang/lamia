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


class LoopCounterTransformer(ast.NodeTransformer):
    """AST transformer that injects loop counters to detect infinite loops."""
    
    def __init__(self, max_iterations: int = 10000):
        self.max_iterations = max_iterations
        self.counter_name = "_lamia_loop_counter"
    
    def visit_FunctionDef(self, node):
        # Initialize loop counter at the start of each function
        counter_init = ast.Assign(
            targets=[ast.Name(id=self.counter_name, ctx=ast.Store())],
            value=ast.Constant(value=0)
        )
        
        # Transform the function body
        transformed_body = [counter_init]
        for stmt in node.body:
            transformed_body.append(self.visit(stmt))
        
        node.body = transformed_body
        return node
    
    def _create_counter_check(self):
        """Create an AST node that checks and increments the loop counter."""
        # Increment counter
        increment = ast.AugAssign(
            target=ast.Name(id=self.counter_name, ctx=ast.Store()),
            op=ast.Add(),
            value=ast.Constant(value=1)
        )
        
        # Check if counter exceeds limit
        check = ast.If(
            test=ast.Compare(
                left=ast.Name(id=self.counter_name, ctx=ast.Load()),
                ops=[ast.Gt()],
                comparators=[ast.Constant(value=self.max_iterations)]
            ),
            body=[
                ast.Raise(
                    exc=ast.Call(
                        func=ast.Name(id='RuntimeError', ctx=ast.Load()),
                        args=[ast.Constant(value=f"Infinite loop detected: exceeded {self.max_iterations} iterations")],
                        keywords=[]
                    )
                )
            ],
            orelse=[]
        )
        
        return [increment, check]
    
    def visit_For(self, node):
        # Transform the loop body first
        node = self.generic_visit(node)
        
        # Inject counter check at the beginning of the loop body
        counter_checks = self._create_counter_check()
        node.body = counter_checks + node.body
        
        return node
    
    def visit_While(self, node):
        # Transform the loop body first
        node = self.generic_visit(node)
        
        # Inject counter check at the beginning of the loop body
        counter_checks = self._create_counter_check()
        node.body = counter_checks + node.body
        
        return node


def inject_loop_counters_string(code: str, max_iterations: int = 10000) -> str:
    """
    Simple string-based loop counter injection that's more reliable than AST transformation.
    """
    lines = code.split('\n')
    result_lines = []
    counter_name = "_lamia_loop_counter"
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Add counter initialization at the start of function definitions
        if stripped.startswith('def '):
            result_lines.append(line)
            # Find the indentation level
            indent = len(line) - len(line.lstrip())
            counter_init = ' ' * (indent + 4) + f"{counter_name} = 0"
            result_lines.append(counter_init)
            continue
            
        # Inject counter checks for loops
        if stripped.startswith('for ') or stripped.startswith('while '):
            result_lines.append(line)
            # Find the indentation level for the loop body
            indent = len(line) - len(line.lstrip())
            body_indent = ' ' * (indent + 4)
            
            # Add counter increment and check
            counter_increment = body_indent + f"{counter_name} += 1"
            counter_check = body_indent + f"if {counter_name} > {max_iterations}:"
            counter_raise = body_indent + f"    raise RuntimeError('Infinite loop detected: exceeded {max_iterations} iterations')"
            
            result_lines.extend([counter_increment, counter_check, counter_raise])
            continue
            
        result_lines.append(line)
    
    return '\n'.join(result_lines)


class RecursionTracker:
    """Runtime recursion depth tracker to detect infinite recursion."""
    
    def __init__(self, max_depth: int = 100):
        self.max_depth = max_depth
        self.current_depth = 0
        self.original_trace_func = None
    
    def __enter__(self):
        self.original_trace_func = sys.gettrace()
        sys.settrace(self._trace_calls)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.settrace(self.original_trace_func)
    
    def _trace_calls(self, frame, event, arg):
        if event == 'call':
            self.current_depth += 1
            if self.current_depth > self.max_depth:
                raise RecursionError(f"Infinite recursion detected: exceeded {self.max_depth} call depth")
        elif event == 'return':
            self.current_depth = max(0, self.current_depth - 1)
        
        return self._trace_calls


class FunctionalValidator(BaseValidator):
    def __init__(self, 
                 test_cases: List[Tuple[Tuple[Any, ...], Union[Any, Type[Exception]]]], 
                 strict: bool = True, 
                 execution_timeout: int = 5,
                 use_docker: bool = False,
                 docker_image: str = "python:3.11-alpine",
                 docker_memory_limit: str = "128m",
                 max_loop_iterations: int = 10000,
                 max_recursion_depth: int = 100):
        self.test_cases = test_cases
        self.strict = strict
        self.execution_timeout = execution_timeout
        self.docker_image = docker_image
        self.docker_memory_limit = docker_memory_limit
        self.max_loop_iterations = max_loop_iterations
        self.max_recursion_depth = max_recursion_depth
        
        # Check Docker availability if requested
        if use_docker:
            if self._check_docker_available():
                self.use_docker = True
                print("Docker is available - using containerized execution")
            else:
                self.use_docker = False
                print("Docker is not available - falling back to namespace execution")
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
        return "functional_validator"

    @property
    def initial_hint(self) -> str:
        """Generate a clear hint with formatted test cases for LLM understanding."""
        hint_parts = [
            "Please provide a Python function that satisfies all the given test cases.",
            "",
            "IMPORTANT FORMATTING REQUIREMENTS:",
            "- Use triple backticks with 'python' language identifier: ```python",
            "- Do NOT include any explanations, comments, or text outside the code block",
            "- Provide ONLY the function definition inside the code block",
            "- Use only standard Python built-ins (no external imports)",
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

    def _inject_loop_counters(self, code: str) -> str:
        """
        Inject loop counters into the code to detect infinite loops.
        Returns the modified code with loop counters.
        """
        try:
            tree = ast.parse(code)
            transformer = LoopCounterTransformer(self.max_loop_iterations)
            transformed_tree = transformer.visit(tree)
            
            # Fix missing line numbers and column offsets
            ast.fix_missing_locations(transformed_tree)
            
            # Return the compiled code object instead of trying to convert back to string
            return compile(transformed_tree, '<injected>', 'exec')
        except Exception as e:
            # If transformation fails, fall back to original code
            print(f"Warning: Could not inject loop counters: {e}")
            return code

    def _inject_simple_loop_counters(self, code: str) -> str:
        """
        Simple string-based loop counter injection that's more reliable than AST transformation.
        """
        lines = code.split('\n')
        result_lines = []
        counter_name = "_lamia_loop_counter"
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Add counter initialization at the start of function definitions
            if stripped.startswith('def '):
                result_lines.append(line)
                # Find the indentation level
                indent = len(line) - len(line.lstrip())
                counter_init = ' ' * (indent + 4) + f"{counter_name} = 0"
                result_lines.append(counter_init)
                continue
                
            # Inject counter checks for loops
            if stripped.startswith('for ') or stripped.startswith('while '):
                result_lines.append(line)
                # Find the indentation level for the loop body
                indent = len(line) - len(line.lstrip())
                body_indent = ' ' * (indent + 4)
                
                # Add counter increment and check
                counter_increment = body_indent + f"{counter_name} += 1"
                counter_check = body_indent + f"if {counter_name} > {self.max_loop_iterations}:"
                counter_raise = body_indent + f"    raise RuntimeError('Infinite loop detected: exceeded {self.max_loop_iterations} iterations')"
                
                result_lines.extend([counter_increment, counter_check, counter_raise])
                continue
                
            result_lines.append(line)
        
        return '\n'.join(result_lines)

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
            'OverflowError', 'FloatingPointError', 'AssertionError', 'RecursionError'
        }
        
        # Create restricted built-ins
        restricted_builtins = {}
        namespace = {'__name__': '__restricted__'}
        
        # Handle different types of __builtins__ (can be dict or module)
        builtins_source = __builtins__ if isinstance(__builtins__, dict) else __builtins__.__dict__
        
        for name in safe_builtins:
            if name in builtins_source:
                builtin_obj = builtins_source[name]
                restricted_builtins[name] = builtin_obj
                # Also make exceptions directly available in namespace
                if name.endswith('Error') or name in ['StopIteration']:
                    namespace[name] = builtin_obj
        
        namespace['__builtins__'] = restricted_builtins
        return namespace

    def _execute_with_timeout(self, func: Callable, args: tuple, timeout: int = 5) -> Any:
        """Execute function with timeout protection and recursion tracking (for in-process execution)."""
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Function execution exceeded {timeout} seconds")
        
        # Set up timeout (Unix systems only)
        if hasattr(signal, 'SIGALRM'):
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout)
        
        try:
            # Use recursion tracker to detect infinite recursion
            with RecursionTracker(self.max_recursion_depth):
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
        
        # Inject loop counters even for Docker execution
        try:
            tree = ast.parse(func_code)
            transformer = LoopCounterTransformer(self.max_loop_iterations)
            transformed_tree = transformer.visit(tree)
            ast.fix_missing_locations(transformed_tree)
            
            # Convert back to source code for Docker execution
            enhanced_func_code = ast.unparse(transformed_tree)
        except Exception as e:
            print(f"Warning: Could not inject loop counters for Docker execution: {e}")
            enhanced_func_code = func_code
        
        # Write enhanced function code to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(enhanced_func_code)
            func_file_path = f.name

        # Get path to docker runner script
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        docker_runner_path = os.path.join(script_dir, 'utils', 'docker_runner.py')
        
        if not os.path.exists(docker_runner_path):
            return {
                'success': False,
                'error': f"Docker runner script not found at {docker_runner_path}"
            }

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
                '-v', f'{docker_runner_path}:/docker_runner.py:ro',  # Mount runner script
                '-v', f'{func_file_path}:/func.py:ro',  # Mount function file
                self.docker_image,
                'python', '/docker_runner.py', '/func.py', repr(test_inputs)
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
            # Clean up temporary files
            try:
                os.unlink(func_file_path)
            except OSError:
                pass  # Ignore cleanup errors

    def _execute_function(self, func: Union[Callable, str], inputs: tuple, use_docker: bool) -> dict:
        """Execute function with given inputs. Returns dict with 'success', 'result', and 'error' keys."""
        if use_docker:
            return self._execute_in_docker(func, inputs, self.execution_timeout)
        else:
            try:
                result = self._execute_with_timeout(func, inputs, self.execution_timeout)
                return {'success': True, 'result': result, 'error': None}
            except Exception as e:
                return {'success': False, 'result': None, 'error': f"{type(e).__name__}: {str(e)}"}

    def _parse_function(self, response: str, is_strict: bool = True) -> Union[Callable, str]:
        """Parse function from response - returns either executable function or code string for Docker."""
        response = response.strip()
        
        if not is_strict:
            # Try to extract function from markdown code blocks first
            code_block_patterns = [
                r'```python\s*\n(.*?)\n```',
                r'```\s*\n(.*?)\n```',
            ]
            
            extracted_code = None
            for pattern in code_block_patterns:
                match = re.search(pattern, response, re.DOTALL)
                if match:
                    extracted_code = match.group(1).strip()
                    break
            
            if not extracted_code:
                def_matches = re.findall(r'def\s+\w+\s*\([^)]*\):[^def]*?(?=def|\Z)', response, re.DOTALL | re.MULTILINE)
                if def_matches:
                    extracted_code = def_matches[0].strip()
                else:
                    extracted_code = response
            
            # Normalize indentation
            lines = extracted_code.split('\n')
            if lines:
                min_indent = float('inf')
                for line in lines:
                    if line.strip():
                        indent = len(line) - len(line.lstrip())
                        min_indent = min(min_indent, indent)
                
                if min_indent != float('inf') and min_indent > 0:
                    normalized_lines = []
                    for line in lines:
                        if line.strip():
                            normalized_lines.append(line[min_indent:] if len(line) >= min_indent else line)
                        else:
                            normalized_lines.append('')
                    extracted_code = '\n'.join(normalized_lines)
            
            response = extracted_code
        
        # Extract function definition
        lines = response.split('\n')
        func_lines = []
        in_function = False
        
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith('def '):
                in_function = True
                func_lines = [line]
            elif in_function:
                func_lines.append(line)
                if (stripped_line and 
                    not line.startswith(' ') and 
                    not line.startswith('\t') and 
                    not stripped_line.startswith('def') and
                    not stripped_line.startswith('#')):
                    func_lines.pop()
                    break
        
        if not func_lines:
            raise ValueError("No function definition found in the response")
        
        func_code = '\n'.join(func_lines)
        
        # If using Docker, just return the code string
        if self.use_docker:
            self._validate_code_safety(func_code)  # Only security check for Docker
            return func_code
        
        # Otherwise, execute in safe namespace with enhanced protection
        self._validate_code_safety(func_code)  # Security check for non-Docker too
        
        # Try simple string-based loop counter injection as fallback
        try:
            enhanced_func_code = self._inject_simple_loop_counters(func_code)
        except Exception as e:
            print(f"Warning: Loop counter injection failed, using original code: {e}")
            enhanced_func_code = func_code
        
        namespace = self._create_safe_namespace()
        try:
            exec(enhanced_func_code, namespace)
        except Exception as e:
            # If enhanced version fails, try original
            try:
                exec(func_code, namespace)
            except Exception as e:
                raise ValueError(f"Failed to parse function from response: {e}")
        
        functions = [v for k, v in namespace.items() 
                    if callable(v) and not k.startswith('__') and not k.endswith('Error') 
                    and k not in ['StopIteration'] and hasattr(v, '__code__')]
        
        if not functions:
            raise ValueError("No function found in the response")
        
        if len(functions) > 1:
            function_names = [name for name, obj in namespace.items() 
                            if callable(obj) and not name.startswith('__') and not name.endswith('Error') 
                            and name not in ['StopIteration'] and hasattr(obj, '__code__')]
            raise ValueError(f"Multiple functions found in response: {', '.join(function_names)}. Please provide only one function")
        
        return functions[0]

    def _parse_clean_function(self, response: str) -> Union[Callable, str]:
        """Parse function from clean code (strict mode)."""
        return self._parse_function(response, is_strict=True)

    def _parse_chatty_function(self, response: str) -> Union[Callable, str]:
        """Parse function from chatty LLM response (permissive mode)."""
        return self._parse_function(response, is_strict=False)

    def _test_function(self, func: Union[Callable, str]) -> ValidationResult:
        """Test the function against all test cases."""
        # Determine execution mode once
        use_docker = self.use_docker and isinstance(func, str)
        
        for i, (inputs, expected) in enumerate(self.test_cases):
            try:
                # Execute the function
                exec_result = self._execute_function(func, inputs, use_docker)
                
                if inspect.isclass(expected) and issubclass(expected, Exception):
                    # Expecting an exception
                    if exec_result['success']:
                        return ValidationResult(
                            is_valid=False,
                            error_message=f"Test case {i+1}: Expected {expected.__name__} but got result: {exec_result['result']}",
                            hint=self.initial_hint
                        )
                    else:
                        # Check if the error matches expected exception
                        if expected.__name__ in exec_result['error']:
                            continue  # Expected exception occurred
                        else:
                            return ValidationResult(
                                is_valid=False,
                                error_message=f"Test case {i+1}: Expected {expected.__name__} but got: {exec_result['error']}",
                                hint=self.initial_hint
                            )
                else:
                    # Expecting a normal return value
                    if not exec_result['success']:
                        return ValidationResult(
                            is_valid=False,
                            error_message=f"Test case {i+1}: Execution failed: {exec_result['error']}",
                            hint=self.initial_hint
                        )
                    
                    if exec_result['result'] != expected:
                        return ValidationResult(
                            is_valid=False,
                            error_message=f"Test case {i+1}: Expected {expected} but got {exec_result['result']} for inputs {inputs}",
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
        
        return ValidationResult(
            is_valid=True,
            validated_text=getattr(func, '__name__', 'function') if callable(func) else 'function',
            hint=self.initial_hint
        )

    def _validate(self, response: Union[str, Callable], parse_func: Callable) -> ValidationResult:
        """Common validation logic for both strict and permissive modes."""
        try:
            if callable(response):
                return self._test_function(response)
            else:
                func = parse_func(response)
                return self._test_function(func)
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

    async def validate_strict(self, response: Union[str, Callable], **kwargs) -> ValidationResult:
        return self._validate(response, self._parse_clean_function)

    async def validate_permissive(self, response: Union[str, Callable], **kwargs) -> ValidationResult:
        return self._validate(response, self._parse_chatty_function)