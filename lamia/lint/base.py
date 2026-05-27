"""Base classes for Lamia source-file linters.

Post-write feedback (Cursor-style): files are always written first,
then the linter result is appended so the LLM can fix issues with patch_file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(Enum):
    """Lint rule severity — codes appear in rule IDs (e.g. HUE001, LMW002)."""
    Error = "E"       # must fix
    Warning = "W"     # should fix
    Convention = "C"  # convention
    Refactor = "R"    # refactor suggestion

    @property
    def order(self) -> int:
        """Lower = more critical. Used to sort feedback (E first)."""
        return _SEVERITY_ORDER[self]


_SEVERITY_ORDER = {
    Severity.Error: 0,
    Severity.Warning: 1,
    Severity.Convention: 2,
    Severity.Refactor: 3,
}


@dataclass(frozen=True)
class LintRule:
    """A single lint rule."""
    code: str
    severity: Severity
    name: str
    description: str
    pattern: Optional[re.Pattern] = None


@dataclass
class LintViolation:
    """One occurrence of a rule being triggered."""
    rule: LintRule
    line: int
    message: str
    snippet: str = ""
    col: int = 0


@dataclass
class LintResult:
    """Lint output for a file — just a list of violations."""
    violations: list[LintViolation] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return len(self.violations) == 0

    def feedback_message(self) -> str:
        """Post-write feedback with line numbers for targeted fixes.

        Violations are sorted by severity (errors first) so the LLM
        addresses the most critical issues first.
        Returns empty string if no violations.
        """
        if not self.violations:
            return ""
        sorted_violations = sorted(
            self.violations,
            key=lambda v: (v.rule.severity.order, v.line),
        )
        errors = [v for v in sorted_violations if v.rule.severity == Severity.Error]
        others = [v for v in sorted_violations if v.rule.severity != Severity.Error]

        lines: list[str] = []
        if errors:
            lines.append(f"ERRORS ({len(errors)} -- you MUST fix these with patch_file):")
            for v in errors:
                loc = f"line {v.line}" if v.line > 0 else "file"
                lines.append(f"  [{v.rule.code}] {loc}: {v.message}")
        if others:
            lines.append(f"WARNINGS ({len(others)} -- fix unless intentional):")
            for v in others:
                loc = f"line {v.line}" if v.line > 0 else "file"
                lines.append(f"  [{v.rule.code}] {loc}: {v.message}")
        return "\n".join(lines)


class BaseLinter:
    """Base linter with rule registration."""

    rules: list[LintRule]

    def __init__(self) -> None:
        self.rules = []

    def lint(
        self,
        content: str,
        original: Optional[str] = None,
        cwd: Optional[str] = None,
        filepath: Optional[str] = None,
    ) -> LintResult:
        raise NotImplementedError
