"""Base classes for Lamia source-file linters.

Post-write feedback (Cursor-style): files are always written first,
then the linter result is appended so the LLM can fix issues with patch_file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class LintRule:
    """A single lint rule."""
    code: str
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


@dataclass
class LintResult:
    """Lint output for a file — just a list of violations."""
    violations: list[LintViolation] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return len(self.violations) == 0

    def feedback_message(self) -> str:
        """Post-write feedback with line numbers for targeted fixes.

        Returns empty string if no violations.
        """
        if not self.violations:
            return ""
        lines = [f"LINT ({len(self.violations)} issues):"]
        for v in self.violations:
            loc = f"line {v.line}" if v.line > 0 else "file"
            lines.append(f"  [{v.rule.code}] {loc}: {v.message}")
        lines.append(
            "If any of these are intentional (e.g. markdown content that is part "
            "of the prompt), you can leave them. Otherwise fix with patch_file."
        )
        return "\n".join(lines)


class BaseLinter:
    """Base linter with rule registration."""

    rules: list[LintRule]

    def __init__(self) -> None:
        self.rules = []

    def lint(self, content: str, original: Optional[str] = None) -> LintResult:
        raise NotImplementedError
