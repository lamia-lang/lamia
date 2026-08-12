"""Git remote detection and canonical identity parsing."""

from lamia.git.remote import (
    canonical_remote_identity,
    get_canonical_remote,
    get_remote_origin,
)
from lamia.git.github_ci import set_repository_ci_variables

__all__ = [
    "canonical_remote_identity",
    "get_canonical_remote",
    "get_remote_origin",
    "set_repository_ci_variables",
]
