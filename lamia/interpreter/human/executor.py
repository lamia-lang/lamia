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

from lamia.engine.managers.llm.files_context_manager import (
    get_active_files_context,
    resolve_standalone_file_references,
)
from lamia.interpreter.human.parser import HuFunction

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

        # Escape ALL braces first so .format() ignores arbitrary
        # curly-brace content (CSS, JSON, JS, etc.) in the template,
        # then selectively un-escape only the declared parameter
        # placeholders so .format() substitutes them.
        safe = self._fn.template.replace("{", "{{").replace("}", "}}")
        for param in self._fn.params:
            safe = safe.replace("{{" + param + "}}", "{" + param + "}")
        result = safe.format(**substitutions)

        # When no FilesContext is active, resolve {@...} relative to this
        # .hu file now -- by the time LLMManager sees the string the
        # source path would be lost.
        if not get_active_files_context() and self._fn.source_path:
            result = resolve_standalone_file_references(result, self._fn.source_path)

        return result