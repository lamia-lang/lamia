"""
Runtime contract checker for custom LLM adapters.

Validates that custom adapter implementations follow the BaseLLMAdapter
contract. Runs automatically when adapters are loaded from the extensions
folder, providing early detection of common implementation mistakes.

Key checks:
- Required methods exist and have correct signatures
- name() returns a non-empty string
- is_remote() returns a boolean
- env_var_names() returns a list of strings
- generate() has the correct signature
- close() exists and is callable
"""

import inspect
from dataclasses import dataclass
from typing import Type, List, Tuple, Any, Optional

from .base import BaseLLMAdapter
import logging

logger = logging.getLogger(__name__)


@dataclass
class AdapterContractViolation:
    """A single contract violation found during adapter checking."""
    method_name: str
    expected: str
    actual: str
    error_message: str


class AdapterContractChecker:
    """Validates custom LLM adapter implementations against the BaseLLMAdapter contract."""

    def __init__(self, adapter_class: Type[BaseLLMAdapter]):
        self.adapter_class = adapter_class
        self.violations: List[AdapterContractViolation] = []

    def check_contracts(self) -> Tuple[bool, List[AdapterContractViolation]]:
        """Run all contract checks. Returns (passed, violations)."""
        self.violations = []
        self._check_name()
        self._check_is_remote()
        self._check_env_var_names()
        self._check_generate_signature()
        self._check_close_exists()
        return len(self.violations) == 0, self.violations

    def _check_name(self):
        try:
            name = self.adapter_class.name()
            if not isinstance(name, str):
                self.violations.append(AdapterContractViolation(
                    method_name="name()",
                    expected="str",
                    actual=type(name).__name__,
                    error_message="name() must return a string"
                ))
            elif not name.strip():
                self.violations.append(AdapterContractViolation(
                    method_name="name()",
                    expected="non-empty string",
                    actual=repr(name),
                    error_message="name() must return a non-empty string"
                ))
        except NotImplementedError:
            self.violations.append(AdapterContractViolation(
                method_name="name()",
                expected="implemented classmethod",
                actual="NotImplementedError",
                error_message="name() must be implemented"
            ))
        except Exception as e:
            self.violations.append(AdapterContractViolation(
                method_name="name()",
                expected="str",
                actual="Exception",
                error_message=f"name() raised: {e}"
            ))

    def _check_is_remote(self):
        try:
            result = self.adapter_class.is_remote()
            if not isinstance(result, bool):
                self.violations.append(AdapterContractViolation(
                    method_name="is_remote()",
                    expected="bool",
                    actual=type(result).__name__,
                    error_message="is_remote() must return True or False"
                ))
        except NotImplementedError:
            self.violations.append(AdapterContractViolation(
                method_name="is_remote()",
                expected="implemented classmethod",
                actual="NotImplementedError",
                error_message="is_remote() must be implemented"
            ))
        except Exception as e:
            self.violations.append(AdapterContractViolation(
                method_name="is_remote()",
                expected="bool",
                actual="Exception",
                error_message=f"is_remote() raised: {e}"
            ))

    def _check_env_var_names(self):
        try:
            result = self.adapter_class.env_var_names()
            if not isinstance(result, list):
                self.violations.append(AdapterContractViolation(
                    method_name="env_var_names()",
                    expected="list[str]",
                    actual=type(result).__name__,
                    error_message="env_var_names() must return a list"
                ))
            elif not all(isinstance(v, str) for v in result):
                self.violations.append(AdapterContractViolation(
                    method_name="env_var_names()",
                    expected="list[str]",
                    actual="list with non-string elements",
                    error_message="env_var_names() must return a list of strings"
                ))
        except Exception as e:
            self.violations.append(AdapterContractViolation(
                method_name="env_var_names()",
                expected="list[str]",
                actual="Exception",
                error_message=f"env_var_names() raised: {e}"
            ))

    def _check_generate_signature(self):
        if not hasattr(self.adapter_class, 'generate'):
            self.violations.append(AdapterContractViolation(
                method_name="generate()",
                expected="async method",
                actual="missing",
                error_message="generate() method must be implemented"
            ))
            return

        method = getattr(self.adapter_class, 'generate')
        if not callable(method):
            self.violations.append(AdapterContractViolation(
                method_name="generate()",
                expected="callable",
                actual="not callable",
                error_message="generate must be a callable method"
            ))
            return

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        if 'prompt' not in params or 'model' not in params:
            self.violations.append(AdapterContractViolation(
                method_name="generate()",
                expected="parameters: prompt, model",
                actual=f"parameters: {', '.join(params)}",
                error_message="generate() must accept 'prompt' and 'model' parameters"
            ))

    def _check_close_exists(self):
        if not hasattr(self.adapter_class, 'close') or not callable(getattr(self.adapter_class, 'close')):
            self.violations.append(AdapterContractViolation(
                method_name="close()",
                expected="async method",
                actual="missing or not callable",
                error_message="close() method must be implemented"
            ))


def check_adapter_contracts(adapter_class: Type[BaseLLMAdapter]) -> Tuple[bool, List[AdapterContractViolation]]:
    """Check adapter contracts and return (passed, violations).

    Called automatically when custom adapters are loaded from extensions/adapters/.
    """
    checker = AdapterContractChecker(adapter_class)
    return checker.check_contracts()


def check_and_warn(adapter_class: Type[BaseLLMAdapter], source_path: str) -> bool:
    """Check contracts and log warnings for violations. Returns True if passed."""
    passed, violations = check_adapter_contracts(adapter_class)
    if not passed:
        adapter_name = getattr(adapter_class, 'name', lambda: adapter_class.__name__)()
        logger.warning(
            "Custom adapter '%s' (%s) has contract violations:",
            adapter_name, source_path
        )
        for v in violations:
            logger.warning("  - %s: %s (expected %s, got %s)",
                           v.method_name, v.error_message, v.expected, v.actual)

    overrides_generate = "generate" in adapter_class.__dict__
    has_api_url = hasattr(adapter_class, "API_URL") or any(
        "API_URL" in getattr(c, "__dict__", {}) for c in adapter_class.__mro__
    )
    if overrides_generate and not has_api_url:
        adapter_name = getattr(adapter_class, 'name', lambda: adapter_class.__name__)()
        logger.info(
            "Custom adapter '%s' overrides generate() — ensure it raises "
            "ExternalOperationError on HTTP failures via raise_for_status() "
            "or raise_for_sdk_error().",
            adapter_name,
        )

    return passed
