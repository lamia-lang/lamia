""".lm file linter (stub).

.lm files are Python + Lamia syntax. Rules TBD.
"""
from __future__ import annotations

from typing import Optional

from lamia.lint.base import BaseLinter, LintResult


class LmLinter(BaseLinter):
    """Linter for .lm (Lamia script) files — placeholder."""

    def lint(self, content: str, original: Optional[str] = None) -> LintResult:
        return LintResult()
