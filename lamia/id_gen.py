"""Shared ID generation for schedules, triggers, and other named resources.

Format: <script-slug>-<4-char-hash>
Example: 'publish-pins-a3f2', 'pricing-reply-7bc1'

The slug is derived from the script filename. The hash suffix ensures
uniqueness when the same script name is used from different project
directories.
"""

import hashlib
import re


def slugify(name: str) -> str:
    """Convert a script filename into a clean kebab-case slug.

    'publish_pins.lm' → 'publish-pins'
    'My Complex Script (v2).lm' → 'my-complex-script-v2'
    """
    stem = name.rsplit(".", 1)[0] if "." in name else name
    slug = stem.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if len(slug) > 16:
        slug = slug[:16].rstrip("-")
    return slug if slug else "script"


def generate_id(script: str, project_root: str) -> str:
    """Generate a human-readable resource ID from script name + project hash.

    Used for both schedule IDs and trigger IDs — same deterministic logic.
    Same script from same project always produces the same ID.
    """
    slug = slugify(script)
    root_hash = hashlib.sha256(project_root.encode()).hexdigest()[:4]
    return f"{slug}-{root_hash}"
