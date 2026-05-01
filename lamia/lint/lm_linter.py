""".lm file linter.

.lm files are Python + Lamia syntax.

Rule index (code format: LM{severity}{NNN}, sorted by severity):
  ── Errors (must fix) ──
  LME002  E  missing-required-params   .hu call missing required params
  LME014  E  unknown-hu-kwargs         .hu call passes kwargs the .hu file doesn't accept
  ── Warnings (should fix) ──
  LMW001  W  excessive-growth          content grew >2x original
  LMW005  W  tab-indentation           use 4 spaces, not tabs (PEP 8)
  LMW006  W  positional-hu-args        .hu calls must use keyword arguments
  LMW007  W  empty-file                .lm file has no content
  LMW008  W  trailing-whitespace       trailing whitespace on lines
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

_LONG_SCRIPT_THRESHOLD = 5000

_GENERIC_LM_NAMES = {
    "process", "run", "main", "script", "pipeline", "workflow",
    "agent", "worker", "task", "job", "handler", "manager",
}

ALL_RULES = [
    MISSING_REQUIRED_PARAMS, UNKNOWN_HU_KWARGS,
    EXCESSIVE_GROWTH, TAB_INDENTATION, POSITIONAL_HU_ARGS,
    EMPTY_FILE, TRAILING_WHITESPACE,
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
