"""
Executor for .hu (human) files.

Provides ``HuCallable`` -- a wrapper that behaves like a regular Python
callable.  When invoked it substitutes ``{param}`` placeholders with
the supplied keyword arguments and returns the resulting prompt string.

The caller in the .lm file handles the ``-> Type`` annotation via the
existing hybrid syntax transformer, so HuCallable only needs to produce
the final prompt text.  ``{@file}`` references are left in the string
and resolved later by the engine's FilesContextManager at execution time.
"""

import logging
import re

from lamia.interpreter.human.parser import HuFunction

_FILE_CTX_RE = re.compile(r'\{@([^}]+)\}')

logger = logging.getLogger(__name__)


class HuCallable:
    """A callable built from a ``.hu`` file template.

    Usage from a ``.lm`` file::

        result = summarize(aspect="key findings", max_words=200) -> HTML
    """

    def __init__(self, hu_function: HuFunction) -> None:
        self._fn = hu_function

    @property
    def __name__(self) -> str:
        return self._fn.name

    def __repr__(self) -> str:
        return f"<HuCallable '{self._fn.name}' params={set(self._fn.params)}>"

    def __call__(self, **kwargs: object) -> str:
        missing = self._fn.params - set(kwargs)
        if missing:
            raise TypeError(
                f"{self._fn.name}() missing required keyword arguments: "
                f"{', '.join(sorted(missing))}"
            )

        substitutions = {k: str(v) for k, v in kwargs.items() if k in self._fn.params}

        # Temporarily escape {@...} file-context references so .format()
        # doesn't choke on them, then restore after substitution.
        escaped = _FILE_CTX_RE.sub(r"{{@\1}}", self._fn.template)
        result = escaped.format(**substitutions)
        return result