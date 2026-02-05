import ast
import sys
from pathlib import Path
from typing import Any
import logging

logger = logging.getLogger(__name__)

def run_python_code(code: str, mode: str = 'interactive', show_banner: bool = True) -> Any:
    """
    Returns:
        Any: The result of the Python code execution
    """
    try:
        expr_ast = ast.parse(code, mode='eval')
        logger.debug(f"Expression AST: {ast.dump(expr_ast, indent=4)}")
        result = eval(compile(expr_ast, '<string>', mode='eval'))
        return result
    except SyntaxError as e:
        pass
    except Exception:
        pass

    try:
        code_ast = ast.parse(code, mode='exec')
        logger.debug(f"Code AST: {ast.dump(code_ast, indent=4)}")
        namespace = {}
        exec(compile(code_ast, '<string>', mode='exec'), namespace, namespace)
        if mode == 'interactive' and code_ast.body and isinstance(code_ast.body[-1], ast.Expr):
            last_expr = code_ast.body[-1]
            if not (isinstance(last_expr.value, ast.Call) and getattr(last_expr.value.func, 'id', None) == 'print'):
                result = eval(compile(ast.Expression(last_expr.value), '<string>', mode='eval'), namespace, namespace)
                return result
        return None
    except SyntaxError as e:
        raise e
    except Exception as e:
        raise e

# New helper -------------------------------------------------------------

def run_python_file(file_path: str, mode: str = 'interactive') -> Any:
    """Execute a Python script located at *file_path* in an isolated namespace.

    The script's directory is temporarily added to ``sys.path`` so that any
    sibling modules (``import foo`` where ``foo.py`` is next to the script)
    can be resolved by the standard import machinery.

    Args:
        file_path: Path to the ``.py`` file to execute.
        mode:   Execution mode passed to :pyfunc:`run_python_code`.

    Returns
    -------
    Any
        Result of the last expression in interactive mode, or ``None``.
    """

    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Python file not found: {file_path}")

    # Ensure the script's directory is on sys.path for local imports.
    script_dir = str(path.parent)
    added_to_syspath = False
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
        added_to_syspath = True

    try:
        source = path.read_text(encoding='utf-8')
        return run_python_code(source, mode=mode)
    finally:
        # Clean up sys.path to avoid side-effects across multiple calls.
        if added_to_syspath and script_dir in sys.path:
            sys.path.remove(script_dir)