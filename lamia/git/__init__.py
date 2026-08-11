"""Git remote detection and canonical identity parsing."""

from lamia.git.remote import (
    canonical_remote_identity,
    get_canonical_remote,
    get_remote_origin,
)

__all__ = [
    "canonical_remote_identity",
    "get_canonical_remote",
    "get_remote_origin",
]
