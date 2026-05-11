"""
Executor for .hu (human) files.

Provides ``HuCallable`` -- a wrapper that behaves like a regular Python
callable.  When invoked it substitutes ``{param}`` placeholders with
the supplied keyword arguments and returns the resulting prompt string.

The caller in the .lm file handles the ``-> Type`` annotation via the
existing hybrid syntax transformer, so HuCallable only needs to produce
the final prompt text.  ``{@file}`` references are left in the string
and resolved later by the engine's FilesContextManager at execution time.

``{@variable}`` references (where *variable* is a valid identifier) are
optional: if the caller passed a kwarg with that name, its value replaces
the reference as a filepath (``{@var}`` → ``{@value}``).  If no kwarg is
provided, the name is treated as a literal filename for search.
"""

import logging
import re

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

    def __init__(self, hu_function: HuFunction, lamia=None) -> None:
        self._fn = hu_function
        self._lamia = lamia

    @property
    def __name__(self) -> str:
        return self._fn.name

    def __repr__(self) -> str:
        return f"<HuCallable '{self._fn.name}' params={set(self._fn.params)}>"

    def __call__(self, *, _return_type=None, **kwargs: object):
        prompt = self._build_prompt(**kwargs)
        if self._lamia is not None:
            return self._lamia.run(prompt, return_type=_return_type)
        return prompt

    def _build_prompt(self, **kwargs: object) -> str:
        missing = self._fn.params - set(kwargs)
        required_missing = missing - set(self._fn.defaults)
        if required_missing:
            raise TypeError(
                f"{self._fn.name}() missing required keyword arguments: "
                f"{', '.join(sorted(required_missing))}"
            )

        substitutions = {k: str(v) for k, v in kwargs.items() if k in self._fn.params}
        for p in missing:
            substitutions[p] = self._fn.defaults.get(p, "")

        empty_file_refs = [
            k for k in self._fn.file_contexts
            if k in substitutions and not substitutions[k].strip()
        ]
        if empty_file_refs:
            raise TypeError(
                f"{self._fn.name}() received empty value for file reference parameter(s): "
                f"{', '.join(sorted(empty_file_refs))}. "
                f"File references must point to an actual file path."
            )

        # Escape ALL braces first so .format() ignores arbitrary
        # curly-brace content (CSS, JSON, JS, etc.) in the template,
        # then selectively un-escape only the declared parameter
        # placeholders so .format() substitutes them.
        safe = self._fn.template.replace("{", "{{").replace("}", "}}")
        for param in self._fn.params:
            safe = re.sub(
                r"\{\{" + re.escape(param) + r"(?::[^}]*)?\}\}",
                "{" + param + "}",
                safe,
            )
        result = safe.format(**substitutions)

        # {@variable} where variable is a kwarg: replace with {@<value>}
        # so file resolution uses the caller-provided filepath.
        def _resolve_var_ref(m):
            ref = m.group(1)
            if ref in kwargs:
                return '{@' + str(kwargs[ref]) + '}'
            return m.group(0)
        result = re.sub(r'\{@(\w+)\}', _resolve_var_ref, result)

        # When no FilesContext is active, resolve {@...} relative to this
        # .hu file now -- by the time LLMManager sees the string the
        # source path would be lost.
        if not get_active_files_context() and self._fn.source_path:
            result = resolve_standalone_file_references(result, self._fn.source_path)

        return result