""".lm file linter.

.lm files are Python + Lamia syntax.

Rule index (code format: LM{severity}{NNN}, sorted by severity):
  ── Errors (must fix) ──
  LME002  E  missing-required-params   .hu call missing required params
  LME014  E  unknown-hu-kwargs         .hu call passes kwargs the .hu file doesn't accept
  LME016  E  unknown-namespace         uses a namespace that is not part of Lamia
  LME017  E  unknown-namespace-method  calls a method that does not exist on a Lamia namespace
  LME020  E  global-web-no-selector    web.action() without a selector on global web
  ── Warnings (should fix) ──
  LMW001  W  excessive-growth          content grew >2x original
  LMW005  W  tab-indentation           use 4 spaces, not tabs (PEP 8)
  LMW006  W  positional-hu-args        .hu calls must use keyword arguments
  LMW007  W  empty-file                .lm file has no content
  LMW008  W  trailing-whitespace       trailing whitespace on lines
  LMW018  W  single-file-in-files-ctx  files() with a single file path is an anti-pattern
  LMW019  W  prefer-atomic-web-action  prefer web.action(sel) over get_element + .action()
  ── Convention ──
  LMC009  C  variable-naming           variables should use snake_case
  LMC010  C  filename-naming           .lm filename should be snake_case
  LMC011  C  leading-blank-lines       file starts with blank lines
  LMC015  C  generic-filename          generic names like process.lm say nothing
  ── Refactor ──
  LMR003  R  output-format-hint        use -> Type[Model], not inline schemas
  LMR012  R  inline-pydantic-model     large projects: extract models to models/
  LMR013  R  long-script               script is very long (>5000 chars)
"""
from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path
from typing import Optional

from lamia.interpreter.human.parser import parse_hu_file
from lamia.lint.base import BaseLinter, LintRule, LintViolation, LintResult, Severity

_GROWTH_RATIO = 2.0

# ── Rules ───────────────────────────────────────────────────────────────────

EXCESSIVE_GROWTH = LintRule(
    code="LMW001",
    severity=Severity.Warning,
    name="excessive-growth",
    description="Content grew disproportionately -- make minimal, targeted changes",
)

MISSING_REQUIRED_PARAMS = LintRule(
    code="LME002",
    severity=Severity.Error,
    name="missing-required-params",
    description="Call to .hu function is missing required parameters",
)

OUTPUT_FORMAT_HINT = LintRule(
    code="LMR003",
    severity=Severity.Refactor,
    name="output-format-hint",
    description=(
        "Don't embed output schema in comments or strings. "
        "Define a Pydantic model and use -> Type[Model] return type "
        "(JSON, HTML, YAML, XML, CSV, Markdown)"
    ),
    pattern=re.compile(
        r"(?:output|response|return|expected)\s+"
        r"(?:json|format|schema|structure|type)"
        r"\s*:?\s*:",
        re.IGNORECASE,
    ),
)

TAB_INDENTATION = LintRule(
    code="LMW005",
    severity=Severity.Warning,
    name="tab-indentation",
    description="Use 4 spaces for indentation, not tabs (PEP 8)",
    pattern=re.compile(r"^\t+", re.MULTILINE),
)

POSITIONAL_HU_ARGS = LintRule(
    code="LMW006",
    severity=Severity.Warning,
    name="positional-hu-args",
    description="Call to %s() uses positional arguments -- .hu calls require keyword arguments",
)

EMPTY_FILE = LintRule(
    code="LMW007",
    severity=Severity.Warning,
    name="empty-file",
    description=".lm file has no meaningful content",
)

TRAILING_WHITESPACE = LintRule(
    code="LMW008",
    severity=Severity.Warning,
    name="trailing-whitespace",
    description="Line has trailing whitespace",
    pattern=re.compile(r"[ \t]+$", re.MULTILINE),
)

VARIABLE_NAMING = LintRule(
    code="LMC009",
    severity=Severity.Convention,
    name="variable-naming",
    description="Variable '%s' should use snake_case (PEP 8)",
)

FILENAME_NAMING = LintRule(
    code="LMC010",
    severity=Severity.Convention,
    name="filename-naming",
    description=".lm filename '%s' should be snake_case (e.g. '%s')",
)

LEADING_BLANK_LINES = LintRule(
    code="LMC011",
    severity=Severity.Convention,
    name="leading-blank-lines",
    description="File starts with blank lines -- code should begin on line 1",
    pattern=re.compile(r"\A\s*\n"),
)

INLINE_PYDANTIC_MODEL = LintRule(
    code="LMR012",
    severity=Severity.Refactor,
    name="inline-pydantic-model",
    description=(
        "Pydantic model '%s' defined inline -- for larger projects, "
        "extract shared models to a models/ directory"
    ),
)

LONG_SCRIPT = LintRule(
    code="LMR013",
    severity=Severity.Refactor,
    name="long-script",
    description=(
        "Script is %d chars -- consider splitting into focused sub-scripts "
        "or moving orchestration to separate pipeline .lm files"
    ),
)

UNKNOWN_HU_KWARGS = LintRule(
    code="LME014",
    severity=Severity.Error,
    name="unknown-hu-kwargs",
    description="Call to %s() passes unknown kwargs: %s. Accepted params: %s",
)

GENERIC_FILENAME = LintRule(
    code="LMC015",
    severity=Severity.Convention,
    name="generic-filename",
    description=(
        ".lm filename '%s' is too generic -- use a descriptive name "
        "that explains what the script does"
    ),
)

UNKNOWN_NAMESPACE = LintRule(
    code="LME016",
    severity=Severity.Error,
    name="unknown-namespace",
    description=(
        "'%s' is not a Lamia namespace. "
        "Valid namespaces: %s"
    ),
)

UNKNOWN_NAMESPACE_METHOD = LintRule(
    code="LME017",
    severity=Severity.Error,
    name="unknown-namespace-method",
    description=(
        "'%s.%s()' does not exist. "
        "Valid methods on '%s': %s"
    ),
)

SINGLE_FILE_IN_FILES_CONTEXT = LintRule(
    code="LMW018",
    severity=Severity.Warning,
    name="single-file-in-files-context",
    description=(
        "files() is for directory-based discovery. "
        "Pass the file path directly as a kwarg to the .hu function instead."
    ),
)

PREFER_ATOMIC_WEB_ACTION = LintRule(
    code="LMW019",
    severity=Severity.Warning,
    name="prefer-atomic-web-action",
    description=(
        "Prefer %s over get_element + .%s() for atomicity and readability"
    ),
)

GLOBAL_WEB_NO_SELECTOR = LintRule(
    code="LME020",
    severity=Severity.Error,
    name="global-web-no-selector",
    description=(
        "web.%s() called without a selector — "
        "provide a selector: web.%s(\"selector\")"
    ),
)

_LONG_SCRIPT_THRESHOLD = 5000

_GENERIC_LM_NAMES = {
    "process", "run", "main", "script", "pipeline", "workflow",
    "agent", "worker", "task", "job", "handler", "manager",
}

ALL_RULES = [
    MISSING_REQUIRED_PARAMS, UNKNOWN_HU_KWARGS,
    UNKNOWN_NAMESPACE, UNKNOWN_NAMESPACE_METHOD,
    GLOBAL_WEB_NO_SELECTOR,
    EXCESSIVE_GROWTH, TAB_INDENTATION, POSITIONAL_HU_ARGS,
    EMPTY_FILE, TRAILING_WHITESPACE,
    SINGLE_FILE_IN_FILES_CONTEXT, PREFER_ATOMIC_WEB_ACTION,
    VARIABLE_NAMING, FILENAME_NAMING, LEADING_BLANK_LINES, GENERIC_FILENAME,
    OUTPUT_FORMAT_HINT, INLINE_PYDANTIC_MODEL, LONG_SCRIPT,
]

_HU_CALL_RE = re.compile(
    r'(\w+)\s*\(([^)]*)\)\s*(?:->|$)',
    re.MULTILINE,
)

_KWARG_RE = re.compile(r'(\w+)\s*=')

_ASSIGNMENT_RE = re.compile(
    r'^([A-Za-z_]\w*)\s*=\s*(?!.*class\b)',
    re.MULTILINE,
)

_SNAKE_CASE_RE = re.compile(r'^[a-z_][a-z0-9_]*$')
_PASCAL_CASE_RE = re.compile(r'^[A-Z][a-zA-Z0-9]*$')
_FILENAME_SNAKE_RE = re.compile(r'^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$')

_PYDANTIC_MODEL_RE = re.compile(
    r'^class\s+(\w+)\s*\(\s*(?:BaseModel|Base)\s*\)',
    re.MULTILINE,
)

_SINGLE_FILE_FILES_RE = re.compile(
    r'\bfiles\s*\(\s*(["\'])([^"\']+)\1\s*\)',
)

_FILE_EXTENSION_RE = re.compile(r'\.\w{1,10}$')


def _extract_call_kwargs(args_text: str) -> set[str]:
    return set(_KWARG_RE.findall(args_text))


def _find_hu_files(cwd: str) -> dict[str, Path]:
    """Map .hu stem names to their paths under cwd."""
    skip = {"node_modules", "__pycache__", ".git", "venv", ".venv",
            ".tox", ".mypy_cache", "dist", "build", ".lamia_sessions"}
    result: dict[str, Path] = {}
    root = Path(cwd)
    for p in root.rglob("*.hu"):
        if any(part in skip for part in p.parts):
            continue
        result[p.stem] = p
    return result


def _parse_hu_params(hu_path: Path) -> tuple[set[str], set[str]]:
    """Return (all_params, required_params) from a .hu file."""
    try:
        fn = parse_hu_file(str(hu_path))
        required = fn.params - set(fn.defaults)
        return set(fn.params), required
    except Exception:
        return set(), set()


def _has_positional_args(args_text: str) -> bool:
    """Check if a function call's args string has non-keyword arguments."""
    args_text = args_text.strip()
    if not args_text:
        return False
    for arg in _split_args(args_text):
        arg = arg.strip()
        if not arg:
            continue
        if '=' not in arg or arg.startswith('"') or arg.startswith("'"):
            if not re.match(r'^\w+\s*=', arg):
                return True
    return False


def _split_args(args_text: str) -> list[str]:
    """Split function arguments respecting nested parens/brackets/quotes."""
    args: list[str] = []
    depth = 0
    current: list[str] = []
    in_str: Optional[str] = None
    for ch in args_text:
        if in_str:
            current.append(ch)
            if ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'"):
            in_str = ch
            current.append(ch)
        elif ch in ('(', '[', '{'):
            depth += 1
            current.append(ch)
        elif ch in (')', ']', '}'):
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            args.append(''.join(current))
            current = []
        else:
            current.append(ch)
    if current:
        args.append(''.join(current))
    return args


def _build_namespace_registry() -> dict[str, set[str]]:
    """Dynamically discover valid Lamia namespaces and their public methods.

    Collects methods from two sources so additions are picked up automatically:
    1. Public methods on the action class (e.g. WebActions.click)
    2. Enum values on the action-type enum (e.g. WebActionType.NAVIGATE)
       — the syntax transformer maps web.navigate() to a WebCommand even
       though WebActions has no navigate() method.
    """
    registry: dict[str, set[str]] = {}

    try:
        from lamia.actions.web import WebActions
        from lamia.interpreter.commands import WebActionType
        class_methods = {
            name for name, _ in inspect.getmembers(
                WebActions, predicate=inspect.isfunction,
            )
            if not name.startswith("_")
        }
        enum_methods = {e.value for e in WebActionType}
        registry["web"] = class_methods | enum_methods
    except Exception:
        registry["web"] = set()

    try:
        from lamia.actions.http import HttpActions
        registry["http"] = {
            name for name, _ in inspect.getmembers(
                HttpActions, predicate=inspect.isfunction,
            )
            if not name.startswith("_")
        }
    except Exception:
        registry["http"] = set()

    try:
        from lamia.actions.file import FileActions
        from lamia.interpreter.commands import FileActionType
        class_methods = {
            name for name, _ in inspect.getmembers(
                FileActions, predicate=inspect.isfunction,
            )
            if not name.startswith("_")
        }
        enum_methods = {e.value for e in FileActionType}
        registry["file"] = class_methods | enum_methods
    except Exception:
        registry["file"] = set()

    # Placeholder namespaces that are recognised but not yet implemented
    for ns in ("db", "email"):
        if ns not in registry:
            registry[ns] = set()

    return registry


# Computed once at import time; automatically picks up new namespaces/methods.
_NAMESPACE_REGISTRY: dict[str, set[str]] = _build_namespace_registry()

def _build_lamia_auto_imports() -> set[str]:
    """Names that Lamia auto-injects into .lm execution globals.

    These never need an explicit import statement.  Built dynamically
    from the same sources the runtime uses (ast_analyzer / types).
    """
    names: set[str] = set()

    # Namespaces: web, http, file, db, email
    names.update(_NAMESPACE_REGISTRY.keys())

    # Context managers / builtins
    names.update({"session", "files", "File", "capture_files_context"})

    # Validation types from lamia.types (JSON, HTML, YAML, …)
    try:
        from lamia.types import BaseType
        import lamia.types as lamia_types
        for attr_name, attr in vars(lamia_types).items():
            if isinstance(attr, type) and attr is not BaseType and issubclass(attr, BaseType):
                names.add(attr_name)
    except Exception:
        pass

    # Pydantic / typing essentials the runtime always injects
    names.update({
        "BaseModel", "Field", "List", "Dict", "Optional", "Any",
        "InputType", "TXT",
    })

    return names


_LAMIA_AUTO_IMPORTS: set[str] = _build_lamia_auto_imports()


def _extract_explicit_imports(tree: ast.AST) -> set[str]:
    """Collect all names brought into scope by import / from … import statements."""
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.asname or alias.name)
    return imported


def _extract_local_definitions(tree: ast.AST) -> set[str]:
    """Collect names defined locally: functions, classes, assignments, for-targets."""
    defined: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(node.name)
            for arg in node.args.args:
                defined.add(arg.arg)
        elif isinstance(node, ast.ClassDef):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined.add(target.id)
        elif isinstance(node, ast.For):
            if isinstance(node.target, ast.Name):
                defined.add(node.target.id)
            elif isinstance(node.target, ast.Tuple):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name):
                        defined.add(elt.id)
    return defined


def _find_project_pydantic_models(cwd: str) -> set[str]:
    """Scan *.py files under cwd for Pydantic model class names.

    In Lamia projects, Pydantic models defined in .py files (typically
    models/) are automatically importable without explicit imports.
    """
    skip = {"node_modules", "__pycache__", ".git", "venv", ".venv",
            ".tox", ".mypy_cache", "dist", "build", ".lamia_sessions"}
    model_names: set[str] = set()
    model_re = re.compile(r"^class\s+(\w+)\s*\(.*\bBaseModel\b", re.MULTILINE)
    root = Path(cwd)
    for py_file in root.rglob("*.py"):
        if any(part in skip for part in py_file.parts):
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
            for m in model_re.finditer(text):
                model_names.add(m.group(1))
        except Exception:
            continue
    return model_names


def _collect_call_targets(tree: ast.AST) -> set[int]:
    """Return the set of AST node ids that are the .func of a Call."""
    targets: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            targets.add(id(node.func))
    return targets


def _check_namespace_usage(
    content: str,
    cwd: Optional[str] = None,
) -> list[LintViolation]:
    """Parse .lm code and flag unknown namespaces or methods.

    Logic: In .lm files, Lamia namespaces (web, http, file, …) and types
    (JSON, HTML, …) are auto-imported.  Everything else must be either
    explicitly imported, defined locally, or be a Pydantic model from the
    project.  Any namespace-style call (lowercase.method()) that is not
    covered by any of these sources is flagged.
    """
    violations: list[LintViolation] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return violations

    explicitly_imported = _extract_explicit_imports(tree)
    locally_defined = _extract_local_definitions(tree)
    project_models = _find_project_pydantic_models(cwd) if cwd else set()

    # All names that are "known" and should not be flagged
    known_names = _LAMIA_AUTO_IMPORTS | explicitly_imported | locally_defined | project_models

    call_targets = _collect_call_targets(tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if not isinstance(node.value, ast.Name):
            continue
        if id(node) not in call_targets:
            continue

        ns_name = node.value.id
        method_name = node.attr
        lineno = getattr(node, "lineno", 0)

        # Skip anything that is explicitly imported, locally defined, or
        # uppercase (class attribute access like BaseModel.parse()).
        if ns_name in known_names:
            # Name is known — but if it's a Lamia namespace, also check
            # that the method exists.
            if ns_name in _NAMESPACE_REGISTRY:
                known_methods = _NAMESPACE_REGISTRY[ns_name]
                if known_methods and method_name not in known_methods:
                    methods_list = ", ".join(sorted(known_methods))
                    violations.append(LintViolation(
                        rule=UNKNOWN_NAMESPACE_METHOD,
                        line=lineno,
                        message=UNKNOWN_NAMESPACE_METHOD.description % (
                            ns_name, method_name, ns_name, methods_list,
                        ),
                        snippet=f"{ns_name}.{method_name}()",
                    ))
            continue

        if ns_name[0].isupper():
            continue

        # Name is not imported, not defined, not a Lamia auto-import.
        # If it looks like it *could* be a Lamia namespace (lowercase,
        # used as ns.method()), flag it.
        valid_ns = ", ".join(sorted(_NAMESPACE_REGISTRY.keys()))
        violations.append(LintViolation(
            rule=UNKNOWN_NAMESPACE,
            line=lineno,
            message=UNKNOWN_NAMESPACE.description % (ns_name, valid_ns),
            snippet=f"{ns_name}.{method_name}()",
        ))

    return violations


_WEB_SELF_TARGET_METHODS = frozenset([
    "click", "get_text", "hover", "scroll_to", "is_visible",
    "is_enabled", "is_checked", "submit_form", "wait_for",
    "type_text", "get_attribute", "select_option", "upload_file",
])


def _check_web_action_patterns(content: str) -> list[LintViolation]:
    """Lint web action usage patterns for atomicity and correctness.

    LMW019: prefer web.action(selector) over get_element(sel) + .action()
            when the variable is only used for a single no-arg action.
    LME020: forbid calling action methods without a selector on global web.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    violations: list[LintViolation] = []

    get_elem_vars: dict[str, tuple] = {}
    var_usage_count: dict[str, int] = {}

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "web"
            and node.value.func.attr == "get_element"
            and node.value.args
        ):
            var_name = node.targets[0].id
            selector_node = node.value.args[0]
            selector_str = ast.literal_eval(selector_node) if isinstance(selector_node, ast.Constant) else None
            get_elem_vars[var_name] = (selector_str, node.lineno)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue

        method_name = node.func.attr
        if method_name not in _WEB_SELF_TARGET_METHODS:
            continue

        # LME020: web.action() without selector on global web
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "web":
            if not node.args:
                violations.append(LintViolation(
                    rule=GLOBAL_WEB_NO_SELECTOR,
                    line=node.lineno,
                    message=GLOBAL_WEB_NO_SELECTOR.description % (method_name, method_name),
                    snippet=f"web.{method_name}()",
                ))
            continue

        # Count usages for LMW019
        if isinstance(node.func.value, ast.Name):
            var_name = node.func.value.id
            if var_name in get_elem_vars:
                var_usage_count[var_name] = var_usage_count.get(var_name, 0) + 1

    # LMW019: single-use get_element + no-arg action
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in _WEB_SELF_TARGET_METHODS:
            continue
        if not isinstance(node.func.value, ast.Name):
            continue

        var_name = node.func.value.id
        if var_name not in get_elem_vars:
            continue
        if var_usage_count.get(var_name, 0) != 1:
            continue
        if node.args:
            continue

        selector_str, _ = get_elem_vars[var_name]
        method_name = node.func.attr
        suggestion = f"web.{method_name}(\"{selector_str}\")" if selector_str else f"web.{method_name}(selector)"
        violations.append(LintViolation(
            rule=PREFER_ATOMIC_WEB_ACTION,
            line=node.lineno,
            message=PREFER_ATOMIC_WEB_ACTION.description % (suggestion, method_name),
            snippet=f"{var_name}.{method_name}()",
        ))

    return violations


class LmLinter(BaseLinter):
    """Linter for .lm (Lamia script) files."""

    def __init__(self) -> None:
        super().__init__()
        self.rules = list(ALL_RULES)

    def lint(
        self,
        content: str,
        original: Optional[str] = None,
        cwd: Optional[str] = None,
        filepath: Optional[str] = None,
    ) -> LintResult:
        violations: list[LintViolation] = []

        # ── Empty file ──────────────────────────────────────────────────
        if not content.strip():
            violations.append(LintViolation(
                rule=EMPTY_FILE, line=0, message=EMPTY_FILE.description,
            ))

        # ── Excessive growth ────────────────────────────────────────────
        if original is not None and len(original) > 0:
            ratio = len(content) / len(original)
            if ratio > _GROWTH_RATIO:
                violations.append(LintViolation(
                    rule=EXCESSIVE_GROWTH, line=0,
                    message=f"Content grew {ratio:.1f}x ({len(original)} -> {len(content)} chars)",
                ))

        # ── Pattern-based rules ─────────────────────────────────────────
        if OUTPUT_FORMAT_HINT.pattern:
            for m in OUTPUT_FORMAT_HINT.pattern.finditer(content):
                lineno = content[:m.start()].count("\n") + 1
                violations.append(LintViolation(
                    rule=OUTPUT_FORMAT_HINT, line=lineno,
                    message=OUTPUT_FORMAT_HINT.description,
                    snippet=m.group().strip()[:60],
                ))

        if TAB_INDENTATION.pattern:
            tab_lines = list(TAB_INDENTATION.pattern.finditer(content))
            if tab_lines:
                first_line = content[:tab_lines[0].start()].count("\n") + 1
                violations.append(LintViolation(
                    rule=TAB_INDENTATION, line=first_line,
                    message=f"{len(tab_lines)} line(s) use tab indentation",
                ))

        if TRAILING_WHITESPACE.pattern:
            count = len(list(TRAILING_WHITESPACE.pattern.finditer(content)))
            if count:
                violations.append(LintViolation(
                    rule=TRAILING_WHITESPACE, line=0,
                    message=f"{count} line(s) have trailing whitespace",
                ))

        if LEADING_BLANK_LINES.pattern and LEADING_BLANK_LINES.pattern.match(content):
            violations.append(LintViolation(
                rule=LEADING_BLANK_LINES, line=1,
                message=LEADING_BLANK_LINES.description,
            ))

        # ── Variable naming ─────────────────────────────────────────────
        for m in _ASSIGNMENT_RE.finditer(content):
            var_name = m.group(1)
            if var_name.startswith('_'):
                continue
            if _PASCAL_CASE_RE.match(var_name):
                continue
            if not _SNAKE_CASE_RE.match(var_name):
                lineno = content[:m.start()].count("\n") + 1
                violations.append(LintViolation(
                    rule=VARIABLE_NAMING, line=lineno,
                    message=VARIABLE_NAMING.description % var_name,
                    snippet=m.group()[:60],
                ))

        # ── Inline Pydantic models ──────────────────────────────────────
        model_matches = list(_PYDANTIC_MODEL_RE.finditer(content))
        if len(model_matches) > 2:
            for m in model_matches:
                lineno = content[:m.start()].count("\n") + 1
                violations.append(LintViolation(
                    rule=INLINE_PYDANTIC_MODEL, line=lineno,
                    message=INLINE_PYDANTIC_MODEL.description % m.group(1),
                    snippet=m.group()[:60],
                ))

        # ── Long script ─────────────────────────────────────────────────
        if len(content) > _LONG_SCRIPT_THRESHOLD:
            violations.append(LintViolation(
                rule=LONG_SCRIPT, line=0,
                message=LONG_SCRIPT.description % len(content),
            ))

        # ── Filename checks ─────────────────────────────────────────────
        if filepath:
            stem = Path(filepath).stem
            if not _FILENAME_SNAKE_RE.match(stem):
                suggested = re.sub(r'(?<=[a-z0-9])([A-Z])', r'_\1', stem)
                suggested = re.sub(r'[-\s]+', '_', suggested).lower()
                violations.append(LintViolation(
                    rule=FILENAME_NAMING, line=0,
                    message=FILENAME_NAMING.description % (stem + ".lm", suggested + ".lm"),
                ))
            if stem in _GENERIC_LM_NAMES:
                violations.append(LintViolation(
                    rule=GENERIC_FILENAME, line=0,
                    message=GENERIC_FILENAME.description % (stem + ".lm"),
                ))

        # ── Single file in files() anti-pattern ──────────────────────────
        for m in _SINGLE_FILE_FILES_RE.finditer(content):
            path_arg = m.group(2)
            if _FILE_EXTENSION_RE.search(path_arg):
                lineno = content[:m.start()].count("\n") + 1
                violations.append(LintViolation(
                    rule=SINGLE_FILE_IN_FILES_CONTEXT, line=lineno,
                    message=(
                        f"files(\"{path_arg}\") passes a single file. "
                        f"{SINGLE_FILE_IN_FILES_CONTEXT.description}"
                    ),
                    snippet=m.group()[:60],
                ))

        # ── Namespace / method validation ─────────────────────────────────
        violations.extend(_check_namespace_usage(content, cwd=cwd))

        # ── Web action patterns ───────────────────────────────────────────
        violations.extend(_check_web_action_patterns(content))

        # ── Cross-file checks (require cwd) ─────────────────────────────
        if cwd:
            hu_files = _find_hu_files(cwd)
            for m in _HU_CALL_RE.finditer(content):
                func_name = m.group(1)
                if func_name not in hu_files:
                    continue
                lineno = content[:m.start()].count("\n") + 1
                args_text = m.group(2)

                all_params, required = _parse_hu_params(hu_files[func_name])
                if all_params:
                    passed = _extract_call_kwargs(args_text)
                    missing = required - passed
                    if missing:
                        violations.append(LintViolation(
                            rule=MISSING_REQUIRED_PARAMS, line=lineno,
                            message=(
                                f"{func_name}() missing required params: "
                                f"{', '.join(sorted(missing))}. "
                                f"Expected: {', '.join(sorted(all_params))}"
                            ),
                            snippet=m.group(0),
                        ))

                    unknown = passed - all_params
                    if unknown:
                        violations.append(LintViolation(
                            rule=UNKNOWN_HU_KWARGS, line=lineno,
                            message=UNKNOWN_HU_KWARGS.description % (
                                func_name,
                                ', '.join(sorted(unknown)),
                                ', '.join(sorted(all_params)),
                            ),
                            snippet=m.group(0)[:60],
                        ))

                if _has_positional_args(args_text):
                    violations.append(LintViolation(
                        rule=POSITIONAL_HU_ARGS, line=lineno,
                        message=POSITIONAL_HU_ARGS.description % func_name,
                        snippet=m.group(0)[:60],
                    ))

        return LintResult(violations=violations)
