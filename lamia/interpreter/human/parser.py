"""
Parser for .hu (human) files.

Reads a .hu file as a plain-text prompt template and extracts
{param} placeholders (with optional defaults) and {@file} context
references.

Supported placeholder syntax::

    {param}              -- required parameter
    {param:None}         -- optional, empty string when omitted
    {param:default text} -- optional, uses "default text" when omitted
    {@filename}          -- file context reference (literal path)
    {@variable}          -- file context via optional parameter; if the
                            caller provides a kwarg with that name its
                            value is used as the filepath, otherwise the
                            name is treated as a literal filename
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

_PARAM_RE = re.compile(r'\{(\w+)(?::([^}]*))?\}')
_FILE_CONTEXT_RE = re.compile(r'\{@([^}]+)\}')


@dataclass(frozen=True)
class HuFunction:
    name: str
    template: str
    params: frozenset[str] = field(default_factory=frozenset)
    defaults: Dict[str, str] = field(default_factory=dict)
    file_contexts: frozenset[str] = field(default_factory=frozenset)
    source_path: str = ""


def parse_hu_file(file_path: str) -> HuFunction:
    """Parse a .hu file into a HuFunction.

    The filename (without extension) becomes the function name.
    ``{param}`` placeholders (excluding ``{@...}``) become parameters.
    ``{param:default}`` placeholders register a default value (``None``
    is treated as empty string).
    ``{@filename}`` references are collected as file contexts.
    """
    path = Path(file_path).resolve()
    template = path.read_text(encoding="utf-8")
    name = path.stem

    params: set[str] = set()
    defaults: dict[str, str] = {}
    for m in _PARAM_RE.finditer(template):
        pname = m.group(1)
        default_val = m.group(2)
        if pname.startswith("@"):
            continue
        params.add(pname)
        if default_val is not None and pname not in defaults:
            defaults[pname] = "" if default_val == "None" else default_val

    file_contexts = frozenset(_FILE_CONTEXT_RE.findall(template))

    for ref in file_contexts:
        if ref.isidentifier() and ref not in params:
            params.add(ref)
            defaults.setdefault(ref, "")

    return HuFunction(
        name=name,
        template=template,
        params=frozenset(params),
        defaults=defaults,
        file_contexts=file_contexts,
        source_path=str(path),
    )