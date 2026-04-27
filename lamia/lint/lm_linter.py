""".lm file linter.

.lm files are Python + Lamia syntax. Checks:
  LM001 - excessive growth (>2x original)
  LM002 - missing required params when calling .hu functions
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from lamia.interpreter.human.parser import parse_hu_file
from lamia.lint.base import BaseLinter, LintRule, LintViolation, LintResult

_GROWTH_RATIO = 2.0

EXCESSIVE_GROWTH = LintRule(
    code="LM001",
    name="excessive-growth",
    description="Content grew disproportionately — make minimal, targeted changes",
)

MISSING_REQUIRED_PARAMS = LintRule(
    code="LM002",
    name="missing-required-params",
    description="Call to .hu function is missing required parameters",
)

_HU_CALL_RE = re.compile(
    r'(\w+)\s*\(([^)]*)\)\s*(?:->|$)',
    re.MULTILINE,
)

_KWARG_RE = re.compile(r'(\w+)\s*=')


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


class LmLinter(BaseLinter):
    """Linter for .lm (Lamia script) files."""

    def __init__(self) -> None:
        super().__init__()
        self.rules = [EXCESSIVE_GROWTH, MISSING_REQUIRED_PARAMS]

    def lint(self, content: str, original: Optional[str] = None, cwd: Optional[str] = None) -> LintResult:
        violations: list[LintViolation] = []

        if original is not None and len(original) > 0:
            ratio = len(content) / len(original)
            if ratio > _GROWTH_RATIO:
                violations.append(LintViolation(
                    rule=EXCESSIVE_GROWTH, line=0,
                    message=f"Content grew {ratio:.1f}x ({len(original)} -> {len(content)} chars)",
                ))

        if cwd:
            hu_files = _find_hu_files(cwd)
            for m in _HU_CALL_RE.finditer(content):
                func_name = m.group(1)
                if func_name not in hu_files:
                    continue
                lineno = content[:m.start()].count("\n") + 1
                all_params, required = _parse_hu_params(hu_files[func_name])
                if not all_params:
                    continue
                passed = _extract_call_kwargs(m.group(2))
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

        return LintResult(violations=violations)
