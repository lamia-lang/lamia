"""Guard against conditional local imports shadowing a name used elsewhere.

An import inside a function makes the bound name local to the *whole*
function.  When that import sits in a branch, every use of the name on a path
that skips the branch raises UnboundLocalError -- a failure that unit tests of
the surrounding helpers never see, because the name resolves fine whenever the
branch happens to run.

Imports that are guaranteed to have executed are not flagged: a ``try`` whose
handlers all return or raise, and uses that sit inside the same branch as an
import of the same name.
"""

import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "lamia"

FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
IMPORTS = (ast.Import, ast.ImportFrom)
TERMINATORS = (ast.Return, ast.Raise, ast.Continue, ast.Break)


def _bound_names(node):
    """Names an import statement binds into the enclosing scope."""
    for alias in node.names:
        if alias.name != "*":
            yield alias.asname or alias.name.split(".")[0]


def _blocks(node):
    """Yield every statement list directly held by a node."""
    for field in ("body", "orelse", "finalbody"):
        block = getattr(node, field, None)
        if isinstance(block, list):
            yield block
    for handler in getattr(node, "handlers", []):
        yield handler.body


def _terminates(block):
    """True when a statement list cannot fall through to the next statement."""
    return bool(block) and isinstance(block[-1], TERMINATORS)


def _index_blocks(func):
    """Map each statement to (enclosing_block, owning_node)."""
    location = {}
    pending = [(func, block) for block in _blocks(func)]
    while pending:
        owner, block = pending.pop()
        for stmt in block:
            location[stmt] = (block, owner)
            if isinstance(stmt, FUNCTIONS):
                continue
            pending.extend((stmt, inner) for inner in _blocks(stmt))
    return location


def _statement_of(node, location):
    """Innermost statement containing node, or None."""
    for stmt in location:
        if node is not stmt and node in ast.walk(stmt):
            return stmt
    return None


def _shadowing_in_function(func):
    """Yield (name, lineno) for branch imports usable before they run."""
    location = _index_blocks(func)
    nested = {n for stmt in location if isinstance(stmt, FUNCTIONS) for n in ast.walk(stmt)}

    imports_by_name = {}
    for stmt, (block, owner) in location.items():
        if isinstance(stmt, IMPORTS) and stmt not in nested:
            for name in _bound_names(stmt):
                imports_by_name.setdefault(name, []).append((stmt, block, owner))

    for name, sites in imports_by_name.items():
        safe = set()
        guaranteed_after = None

        for stmt, block, owner in sites:
            safe.update(n for s in block for n in ast.walk(s))
            top_level = block is func.body
            settled_try = isinstance(owner, ast.Try) and all(
                _terminates(h.body) for h in owner.handlers
            )
            if top_level or settled_try:
                end = owner.end_lineno if settled_try else stmt.end_lineno
                guaranteed_after = min(guaranteed_after or end, end)

        uses = [
            n for n in ast.walk(func)
            if isinstance(n, ast.Name)
            and n.id == name
            and isinstance(n.ctx, ast.Load)
            and n not in nested
            and n not in safe
        ]
        for use in uses:
            if guaranteed_after is not None and use.lineno > guaranteed_after:
                continue
            yield name, sites[0][0].lineno, use.lineno


def _python_files():
    return sorted(
        p for p in PACKAGE_ROOT.rglob("*.py") if "__pycache__" not in p.parts
    )


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_no_conditional_import_shadowing(path):
    tree = ast.parse(path.read_text(), filename=str(path))

    offenders = sorted({
        f"{path.name}: '{name}' imported in a branch at line {imported}, "
        f"but used at line {used} in {func.name}()"
        for func in ast.walk(tree)
        if isinstance(func, FUNCTIONS)
        for name, imported, used in _shadowing_in_function(func)
    })

    assert not offenders, (
        "Local import shadows a name reachable before the import runs; move "
        "the import to module scope:\n  " + "\n  ".join(offenders)
    )
