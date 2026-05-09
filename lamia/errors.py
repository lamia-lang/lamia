"""User-facing error classes for the Lamia library.

This module contains all exceptions that users of Lamia may encounter when
using the library. These errors provide specific information about failures
and guide users on appropriate responses.

Import these exceptions from the main lamia module:
    from lamia import MissingAPIKeysError, ExternalOperationPermanentError
    from lamia import FileNotFoundError, AmbiguousFileError
"""

from enum import Enum
import re
from typing import List, Optional


class MultipleSelectableInputsError(Exception):
    """Raised when get_options() finds multiple radio/checkbox/select groups in scope.
    
    This helps identify ambiguous situations where the scope contains multiple
    option groups and Lamia can't determine which one you want.
    
    Solution: Narrow the scope or provide a specific selector.
    """
    pass


class NoSelectableInputError(Exception):
    """Raised when get_options() finds no radio/checkbox/select in scope.
    
    This means the current scope doesn't contain any selectable input elements.
    
    Solution: Check the scope or use a different selector.
    """
    pass


class MissingAPIKeysError(Exception):
    """Raised when one or more required API keys are missing for LLM engines."""
    
    def __init__(self, missing):
        def get_api_keys_constructor_string(provider_names: List[str]) -> str:
            return "Lamia(..., api_keys={" + \
                ", ".join([f'"{provider_name}": "my-api-key"' for provider_name in provider_names]) + \
                "}"

        # Import here to avoid circular imports
        from lamia.adapters.llm.lamia_adapter import LamiaAdapter
        
        self.missing = missing
        missing_providers = [model_provider for model_provider, _ in missing]
        # Build example export commands from the actual missing env vars
        example_exports = ", ".join(
            f"export {env_vars[0]}=..." if isinstance(env_vars, list) and env_vars else f"export {env_vars}=..."
            for _, env_vars in missing[:2]
        )
        lamia_env_vars = LamiaAdapter.env_var_names()
        lamia_key_name = lamia_env_vars[0]
        message = (
            "The following engines are missing required API keys:\n" +
            "\n".join([f"- {model_provider}: missing {env_vars}" for model_provider, env_vars in missing]) +
            "\n\nPlease provide the missing API keys in one of the following ways:\n" +
            f"- As environment variables (e.g., {example_exports})\n"
            #"- As a parameter to the Lamia() constructor like this: " + get_api_keys_constructor_string([provider for provider, _ in missing]) + "\n" +
            #(f"You can also use {lamia_key_name} or {get_api_keys_constructor_string(['lamia'])} to proxy remote adapters ({', '.join(LamiaAdapter.get_supported_providers())}).\n" if all(provider in LamiaAdapter.get_supported_providers() for provider in missing_providers) else "") +
            #"Alternatively, remove these engines from your model_chain in the config."
        )
        super().__init__(message)


class ExternalOperationError(Exception):
    """Base exception for external operation failures.
    
    This is the base class for all external system operation errors. When you see
    this error or its subclasses, it means an external service (LLM API, filesystem, etc.)
    failed to complete the requested operation.
    
    Attributes:
        retry_history: List of all retry attempts made before failing
        original_error: The underlying exception that caused the failure
    
    Example:
        try:
            result = await lamia.run_async("What is the weather?")
        except ExternalOperationError as e:
            print(f"External system failed: {e}")
            print(f"Retry attempts: {len(e.retry_history)}")
            print(f"Original cause: {e.original_error}")
    """
    
    def __init__(self, message: str, retry_history: Optional[List[str]] = None, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.retry_history = retry_history
        self.original_error = original_error


class ExternalOperationFailedError(ExternalOperationError):
    """Raised when external operation fails with unclassified error.
    
    This is the fallback error for failures that don't fit into specific
    categories (permanent, rate limit, transient). It indicates the operation
    failed but the exact cause couldn't be determined from error classification.
    
    What to do:
    - Check the original_error for specific details
    - Review retry_history to understand failure pattern  
    - Consider if this is a service issue or request problem
    - May require manual investigation of the underlying error
    
    Example:
        try:
            result = await lamia.run_async("Generate text")
        except ExternalOperationFailedError as e:
            print(f"Operation failed: {e.original_error}")
            print(f"Attempts made: {len(e.retry_history)}")
            # Investigate the specific error details
    """
    pass


class ExternalOperationTransientError(ExternalOperationError):
    """Raised when an external operation fails due to a transient error.
    
    These are temporary failures that are safe to retry. Examples include
    network timeouts, temporary service overload, or connection issues.
    
    What to do:
    - Safe to retry immediately or after a short delay
    - These errors are already automatically retried, so if you see this,
      all automatic retries have been exhausted
    - Consider implementing your own retry with exponential backoff
    
    Example:
        try:
            result = await lamia.run_async("Generate summary")
        except ExternalOperationTransientError as e:
            print("Temporary network issue, retrying in 30 seconds...")
            await asyncio.sleep(30)
            # Retry the operation
    """
    pass


class ExternalOperationRateLimitError(ExternalOperationError):
    """Raised when an external operation fails due to rate limiting.
    
    You've exceeded the API rate limits for the external service. This is common
    with LLM APIs that have requests-per-minute or tokens-per-minute limits.
    
    What to do:
    - Wait before retrying (check the service's rate limit documentation)
    - Reduce your request frequency  
    - Consider upgrading your API plan for higher limits
    - Implement request batching or queuing
    - Switch to a different model with higher limits
    
    Example:
        try:
            result = await lamia.run_async("Process this text") 
        except ExternalOperationRateLimitError as e:
            print("Rate limited, waiting 60 seconds...")
            await asyncio.sleep(60)
            # Consider reducing request frequency
    """
    pass


class ExternalOperationPermanentError(ExternalOperationError):
    """Raised when an external operation fails due to a permanent error.
    
    These are errors that won't be resolved by retrying, such as invalid API keys,
    malformed requests, insufficient permissions, or unsupported operations.
    
    What to do:
    - DON'T retry - the same error will occur
    - Check your API keys and configuration
    - Verify the request format and parameters
    - Check service documentation for supported features
    - Review permissions and account status
    
    Example:
        try:
            result = await lamia.run_async("Generate response")
        except ExternalOperationPermanentError as e:
            print("Configuration error - check API keys and permissions")
            print(f"Error details: {e.original_error}")
            # Fix configuration before retrying
    """
    pass


class LLMErrorType(str, Enum):
    """Classification of LLM provider errors for UI/protocol consumers."""
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    QUOTA = "quota"
    TIMEOUT = "timeout"
    NETWORK = "network"
    PROVIDER = "provider"


_AUTH_PATTERNS = [
    re.compile(r"invalid.{0,5}api.{0,3}key", re.I),
    re.compile(r"incorrect api key", re.I),
    re.compile(r"invalid x-api-key", re.I),
    re.compile(r"authentication.{0,5}failed", re.I),
    re.compile(r"(?:^|\b)unauthorized\b", re.I),
    re.compile(r"\b401\b.*(?:api.?key|unauthorized)", re.I),
]

_RATE_LIMIT_PATTERNS = [
    re.compile(r"rate.?limit", re.I),
    re.compile(r"too many requests", re.I),
    re.compile(r"\b429\b", re.I),
    re.compile(r"resource.?exhausted", re.I),
]

_QUOTA_PATTERNS = [
    re.compile(r"insufficient.{0,5}quota", re.I),
    re.compile(r"insufficient.{0,5}credits", re.I),
    re.compile(r"billing.{0,10}(hard|limit)", re.I),
    re.compile(r"\b402\b", re.I),
]

_TIMEOUT_PATTERNS = [
    re.compile(r"time.?out", re.I),
    re.compile(r"timed.?out", re.I),
    re.compile(r"\b408\b", re.I),
]

_NETWORK_PATTERNS = [
    re.compile(r"connection.{0,5}(refused|reset|error)", re.I),
    re.compile(r"name.{0,5}resolution", re.I),
    re.compile(r"dns", re.I),
    re.compile(r"network.{0,5}(error|unreachable)", re.I),
]

_USER_MESSAGES = {
    LLMErrorType.AUTH: "Authentication failed: invalid API key. Update your API key in settings.",
    LLMErrorType.RATE_LIMIT: "Rate limit reached. Please retry in a moment.",
    LLMErrorType.QUOTA: "Insufficient quota or credits for this provider.",
    LLMErrorType.TIMEOUT: "Provider request timed out. Please retry.",
    LLMErrorType.NETWORK: "Could not connect to the provider. Check your network connection.",
    LLMErrorType.PROVIDER: "Provider request failed.",
}


def _classify_error(text: str) -> LLMErrorType:
    """Classify an error message into an LLMErrorType via pattern matching."""
    for pat in _AUTH_PATTERNS:
        if pat.search(text):
            return LLMErrorType.AUTH
    for pat in _RATE_LIMIT_PATTERNS:
        if pat.search(text):
            return LLMErrorType.RATE_LIMIT
    for pat in _QUOTA_PATTERNS:
        if pat.search(text):
            return LLMErrorType.QUOTA
    for pat in _TIMEOUT_PATTERNS:
        if pat.search(text):
            return LLMErrorType.TIMEOUT
    for pat in _NETWORK_PATTERNS:
        if pat.search(text):
            return LLMErrorType.NETWORK
    return LLMErrorType.PROVIDER


def _extract_nested_message(text: str) -> str:
    """Best-effort extraction of a nested 'message' value from raw payload text."""
    m = re.search(r'"message"\s*:\s*"([^"]+)"', text)
    if m:
        return m.group(1).strip()
    m = re.search(r"'message'\s*:\s*'([^']+)'", text)
    if m:
        return m.group(1).strip()
    return ""


class LLMProviderError(ExternalOperationError):
    """Typed, UI-safe wrapper around raw LLM provider / SDK errors.

    Attributes:
        error_type: classified category (auth, rate_limit, etc.)
        status_code: HTTP status when available
        provider: provider name when available
        user_message: concise UI-safe text for end-users
        sanitized_detail: full sanitized detail string for logs
    """

    def __init__(
        self,
        user_message: str,
        *,
        error_type: LLMErrorType = LLMErrorType.PROVIDER,
        status_code: Optional[int] = None,
        provider: Optional[str] = None,
        sanitized_detail: str = "",
        original_error: Optional[Exception] = None,
    ):
        super().__init__(user_message, original_error=original_error)
        self.error_type = error_type
        self.status_code = status_code
        self.provider = provider
        self.user_message = user_message
        self.sanitized_detail = sanitized_detail

    @classmethod
    def from_exception(cls, exc: Exception, *, provider: str | None = None) -> "LLMProviderError":
        """Classify any exception into a typed LLMProviderError.

        This is the single boundary function that JSON mode / IDE should call.
        Adapters (including custom ones) do NOT need to use this — the framework
        applies it at the protocol boundary.
        """
        from lamia.adapters.llm.base import sanitize_api_error

        raw = str(exc)
        safe = sanitize_api_error(raw)
        error_type = _classify_error(safe)

        if error_type != LLMErrorType.PROVIDER:
            user_msg = _USER_MESSAGES[error_type]
        else:
            extracted = _extract_nested_message(safe)
            user_msg = extracted or safe or _USER_MESSAGES[LLMErrorType.PROVIDER]

        status = None
        status_match = re.search(r"\b(\d{3})\b", safe)
        if status_match:
            code = int(status_match.group(1))
            if 400 <= code <= 599:
                status = code

        return cls(
            user_message=user_msg,
            error_type=error_type,
            status_code=status,
            provider=provider,
            sanitized_detail=safe,
            original_error=exc,
        )


class OllamaNotInstalledError(ExternalOperationPermanentError):
    """Raised when the Ollama binary is not found on the system.
    
    Lamia requires Ollama to be installed separately for local model support.
    Ollama is a free, open-source tool for running LLMs locally.
    
    What to do:
    - Install Ollama from https://ollama.ai/download
    - After installation, restart your terminal or shell
    - Then re-run your Lamia command
    
    Example:
        try:
            result = await lamia.run_async("Hello")
        except OllamaNotInstalledError:
            print("Please install Ollama: https://ollama.ai/download")
    """
    
    def __init__(self):
        super().__init__(
            "Ollama is not installed. Install it from https://ollama.ai/download\n"
            "After installation, restart your terminal and try again."
        )


class AmbiguousFileError(Exception):
    """Raised when multiple files match a file reference with similar scores.
    
    This occurs when using {@filename} syntax in a files context and multiple
    files have similar match scores, making it unclear which file was intended.
    
    What to do:
    - Be more specific with the filename (include more of the path)
    - Use the full filename with extension
    - Check the suggested matches in the error message
    
    Example:
        with files("~/Documents/"):
            try:
                result = lamia.run("Extract from {@config}")
            except AmbiguousFileError as e:
                print(f"Multiple files match '{e.query}':")
                for path, score in e.matches:
                    print(f"  - {path} (score: {score:.2f})")
    """
    
    def __init__(self, query: str, matches: List[tuple]):
        import os
        self.query = query
        self.matches = matches
        
        match_list = "\n".join([
            f"  {i+1}. {os.path.basename(path)} (score: {score:.2f})"
            for i, (path, score) in enumerate(matches[:5])
        ])
        
        message = (
            f"Multiple files match '{query}':\n{match_list}\n\n"
            f"Please be more specific with the filename or path."
        )
        super().__init__(message)


class FileReferenceError(Exception):
    """Raised when a file reference cannot be resolved.
    
    This occurs when using {@filename} syntax in a files context but the
    file cannot be found in the indexed files.
    
    What to do:
    - Check the filename spelling
    - Verify the file exists in the paths provided to files()
    - Check the suggested similar filenames in the error message
    - Use with files() to include the directory containing the file
    
    Example:
        with files("~/Documents/"):
            try:
                result = lamia.run("Extract from {@resum.pdf}")
            except FileReferenceError as e:
                print(f"File not found: {e.query}")
                print(f"Did you mean: {e.suggestions}")
    """
    
    def __init__(self, query: str, suggestions: List[str], hint: str = ""):
        self.query = query
        self.suggestions = suggestions
        self.hint = hint
        
        if suggestions:
            suggestion_list = "\n".join([f"  - {s}" for s in suggestions[:3]])
            message = f"File '{query}' not found.\n\nDid you mean:\n{suggestion_list}"
        else:
            message = f"File '{query}' not found in files context."
        if hint:
            message = f"{message}\n\nHint: {hint}"
        
        super().__init__(message)
