"""Shared validation helpers for inline Lamia template functions."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Set

_INLINE_DEF_PARAM_RE = re.compile(r"\{(\w+)(?::[^}]*)?\}")
_INLINE_DEF_FILEREF_RE = re.compile(r"\{@(\w+)\}")


@dataclass(frozen=True)
class InlineFunctionIssues:
    missing_placeholders: Set[str]
    typed_params_in_placeholders: Set[str]


def extract_template_placeholders(template: str) -> Set[str]:
    """Extract {param} and {@file_ref} names from template text."""
    refs: Set[str] = set()
    for match in _INLINE_DEF_PARAM_RE.finditer(template):
        refs.add(match.group(1))
    for match in _INLINE_DEF_FILEREF_RE.finditer(template):
        refs.add(match.group(1))
    return refs


def analyze_inline_template(
    template: str,
    signature_params: Set[str],
    typed_signature_params: Set[str],
) -> InlineFunctionIssues:
    """Analyze placeholder/signature consistency for one inline function."""
    placeholders = extract_template_placeholders(template)
    missing = placeholders - signature_params
    typed_used = placeholders & typed_signature_params
    return InlineFunctionIssues(
        missing_placeholders=missing,
        typed_params_in_placeholders=typed_used,
    )


def typed_params_message(function_name: str, typed_params: Set[str]) -> str:
    """Build a consistent message for typed inline params."""
    return (
        f"{function_name}() uses typed parameters: "
        f"{', '.join(sorted(typed_params))}. "
        "Lamia inline functions currently require untyped params."
    )


def missing_placeholders_message(function_name: str, missing: Set[str]) -> str:
    """Build a consistent message for placeholder/signature mismatches."""
    return (
        f"{function_name}() template uses placeholders not present in function params: "
        f"{', '.join(sorted(missing))}"
    )
