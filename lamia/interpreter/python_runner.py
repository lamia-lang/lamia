import ast
from typing import Any

def run_python_code(code: str, mode: str = 'interactive', show_banner: bool = True) -> Any:
    """
    Returns:
        Any: The result of the Python code execution
    """
    try:
        expr_ast = ast.parse(code, mode='eval')
        print(ast.dump(expr_ast, indent=4))
        result = eval(compile(expr_ast, '<string>', mode='eval'))
        return result
    except SyntaxError as e:
        pass
    except Exception:
        pass
    try:
        code_ast = ast.parse(code, mode='exec')
        print(ast.dump(code_ast, indent=4))
        local_vars = {}
        exec(compile(code_ast, '<string>', mode='exec'), {}, local_vars)
        if mode == 'interactive' and code_ast.body and isinstance(code_ast.body[-1], ast.Expr):
            last_expr = code_ast.body[-1]
            if not (isinstance(last_expr.value, ast.Call) and getattr(last_expr.value.func, 'id', None) == 'print'):
                result = eval(compile(ast.Expression(last_expr.value), '<string>', mode='eval'), {}, local_vars)
                return result
        return None
    except SyntaxError as e:
        raise e
    except Exception as e:
        raise e