"""
Parser for .hu (human) files.

Reads a .hu file as a plain-text prompt template and extracts
{param} placeholders and {@file} context references.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

_PARAM_RE = re.compile(r'\{(\w+)\}')
_FILE_CONTEXT_RE = re.compile(r'\{@([^}]+)\}')


@dataclass(frozen=True)
class HuFunction:
    name: str
    template: str
    params: frozenset[str] = field(default_factory=frozenset)
    file_contexts: frozenset[str] = field(default_factory=frozenset)
    source_path: str = ""


def parse_hu_file(file_path: str) -> HuFunction:
    """Parse a .hu file into a HuFunction.

    The filename (without extension) becomes the function name.
    ``{param}`` placeholders (excluding ``{@...}``) become parameters.
    ``{@filename}`` references are collected as file contexts.
    """
    path = Path(file_path).resolve()
    template = path.read_text(encoding="utf-8")
    name = path.stem

    raw_placeholders = _PARAM_RE.findall(template)
    params = frozenset(p for p in raw_placeholders if not p.startswith("@"))
    file_contexts = frozenset(_FILE_CONTEXT_RE.findall(template))

    return HuFunction(
        name=name,
        template=template,
        params=params,
        file_contexts=file_contexts,
        source_path=str(path),
    )