import ast
from typing import Any

def is_python_code(code: str) -> bool:
    """
    Check if the input string is likely Python code.
    Args:
        code: The input string to check
    Returns:
        bool: True if the string is likely Python code
    """
    try:
        ast.parse(code, mode='eval')
        return True
    except Exception:
        pass
    try:
        ast.parse(code, mode='exec')
        return True
    except Exception:
        return False

def run_python_code(code: str, mode: str = 'interactive', show_banner: bool = True) -> tuple[bool, Any]:
    """
    Execute Python code or expression.
    Args:
        code: The Python code to execute
        mode: 'interactive' or 'file' - controls output behavior
        show_banner: Whether to show result banner
    Returns:
        tuple: (success: bool, result: Any)
    """
    try:
        expr_ast = ast.parse(code, mode='eval')
        result = eval(compile(expr_ast, '<string>', mode='eval'))
        return True, result
    except Exception:
        pass
    try:
        code_ast = ast.parse(code, mode='exec')
        local_vars = {}
        exec(compile(code_ast, '<string>', mode='exec'), {}, local_vars)
        if mode == 'interactive' and code_ast.body and isinstance(code_ast.body[-1], ast.Expr):
            last_expr = code_ast.body[-1]
            if not (isinstance(last_expr.value, ast.Call) and getattr(last_expr.value.func, 'id', None) == 'print'):
                result = eval(compile(ast.Expression(last_expr.value), '<string>', mode='eval'), {}, local_vars)
                return True, result
        return True, None
    except Exception as e:
        return False, e 