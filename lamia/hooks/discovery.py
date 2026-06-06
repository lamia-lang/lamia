"""Discover hook functions from .lm files in the project."""

import ast
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from lamia.hooks import HookDefinition, HookEvent

logger = logging.getLogger(__name__)


def discover_hooks(project_root: Path) -> List[HookDefinition]:
    """Scan all .lm files in the project and extract Hook() function definitions."""
    hooks: List[HookDefinition] = []

    if not project_root.exists():
        return hooks

    for lm_file in project_root.rglob("*.lm"):
        if _should_skip(lm_file, project_root):
            continue
        try:
            source = lm_file.read_text(encoding="utf-8")
            file_hooks = _extract_hooks_from_source(source, str(lm_file))
            hooks.extend(file_hooks)
        except (SyntaxError, OSError) as e:
            logger.debug(f"Skipping {lm_file}: {e}")

    if hooks:
        logger.info(f"Discovered {len(hooks)} hook(s) from project files")
    return hooks


def _should_skip(path: Path, project_root: Path) -> bool:
    """Skip hidden directories, __pycache__, node_modules, etc."""
    rel = path.relative_to(project_root)
    parts = rel.parts
    return any(p.startswith(".") or p == "__pycache__" or p == "node_modules" for p in parts)


def _extract_hooks_from_source(source: str, filepath: str) -> List[HookDefinition]:
    """Parse source and find functions with -> Hook(...) return annotations."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    hooks = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            hook_info = _parse_hook_annotation(node)
            if hook_info is not None:
                func = _compile_hook_function(node, source, filepath)
                if func is not None:
                    hooks.append(HookDefinition(
                        event=hook_info["event"],
                        function=func,
                        name=node.name,
                        source_file=filepath,
                        filter_return_type=hook_info.get("return_type"),
                        filter_function=hook_info.get("function"),
                    ))
    return hooks


def _parse_hook_annotation(node: ast.FunctionDef) -> Optional[Dict[str, Any]]:
    """Check if function has -> Hook(...) return annotation and extract params."""
    returns = node.returns
    if returns is None:
        return None

    if not (isinstance(returns, ast.Call)
            and isinstance(returns.func, ast.Name)
            and returns.func.id == "Hook"):
        return None

    args = returns.args
    kwargs = {kw.arg: kw.value for kw in returns.keywords}

    if not args:
        return None

    event = _ast_to_string(args[0])
    if not HookEvent.is_valid(event):
        logger.warning(f"Unknown hook event '{event}' in {node.name}, skipping")
        return None

    result: Dict[str, Any] = {"event": event}

    if len(args) >= 2:
        result["return_type"] = _ast_to_string(args[1])

    if "function" in kwargs:
        result["function"] = _ast_to_string(kwargs["function"])

    return result


def _ast_to_string(node: ast.expr) -> Optional[str]:
    """Extract a string value from an AST node (Name, Constant, or Attribute)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _compile_hook_function(node: ast.FunctionDef, source: str, filepath: str):
    """Compile a hook function from its AST node into a callable."""
    module = ast.parse(source)

    imports = [n for n in ast.iter_child_nodes(module)
               if isinstance(n, (ast.Import, ast.ImportFrom))]
    top_level_assigns = [n for n in ast.iter_child_nodes(module)
                         if isinstance(n, (ast.Assign, ast.AnnAssign))]

    func_copy = ast.copy_location(
        ast.FunctionDef(
            name=node.name,
            args=node.args,
            body=node.body,
            decorator_list=[],
            returns=None,
            type_comment=getattr(node, "type_comment", None),
        ),
        node,
    )

    wrapper_module = ast.Module(
        body=imports + top_level_assigns + [func_copy],
        type_ignores=[],
    )
    ast.fix_missing_locations(wrapper_module)

    try:
        code = compile(wrapper_module, filepath, "exec")
        namespace: Dict[str, Any] = {}
        exec(code, namespace)
        return namespace.get(node.name)
    except Exception as e:
        logger.warning(f"Failed to compile hook '{node.name}' from {filepath}: {e}")
        return None
