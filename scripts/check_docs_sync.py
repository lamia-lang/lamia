#!/usr/bin/env python3
"""Validate that every doc in mkdocs.yml nav has a mapping in TOPIC_TO_FILE.

Run from the repository root:
    python scripts/check_docs_sync.py

Exits with code 1 if any nav docs are missing from TOPIC_TO_FILE.
"""

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lamia.tools.definitions import TOPIC_TO_FILE  # noqa: E402

SKIP_PATTERNS = {"index.md", "reference/"}


def _extract_nav_files(nav: list) -> list[str]:
    """Recursively extract .md file paths from the mkdocs nav structure."""
    files: list[str] = []
    for entry in nav:
        if isinstance(entry, str):
            if entry.endswith(".md"):
                files.append(entry)
        elif isinstance(entry, dict):
            for value in entry.values():
                if isinstance(value, str) and value.endswith(".md"):
                    files.append(value)
                elif isinstance(value, list):
                    files.extend(_extract_nav_files(value))
    return files


def main() -> int:
    mkdocs_path = REPO_ROOT / "mkdocs.yml"
    if not mkdocs_path.is_file():
        print("ERROR: mkdocs.yml not found at repo root")
        return 1

    with open(mkdocs_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    nav = config.get("nav", [])
    nav_files = _extract_nav_files(nav)

    mapped_files = set(TOPIC_TO_FILE.values())

    missing: list[str] = []
    for doc_file in nav_files:
        if any(doc_file.startswith(skip) or doc_file == skip for skip in SKIP_PATTERNS):
            continue
        if doc_file not in mapped_files:
            missing.append(doc_file)

    if not missing:
        print(f"OK: all {len(nav_files)} nav docs are mapped in TOPIC_TO_FILE")
        return 0

    print(f"FAIL: {len(missing)} doc(s) in mkdocs.yml nav are not mapped in TOPIC_TO_FILE:")
    for doc_file in missing:
        stem = Path(doc_file).stem
        print(f'  - {doc_file}  (suggested alias: "{stem}")')
    print()
    print("Add mappings to lamia/tools/definitions.py TOPIC_TO_FILE dict.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
