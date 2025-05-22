import re
import json
from typing import Optional, Dict, Any
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

from .base import BaseValidator, ValidationResult

class HTMLValidator(BaseValidator):
    """Validates if the response is valid HTML."""
    
    @property
    def name(self) -> str:
        return "html"

    @property
    def initial_hint(self) -> str:
        return "Please return only the HTML code, starting with <html> and ending with </html>, with no explanation or extra text."

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        # Strict: must start with <html> and end with </html>, and be well-formed, no extra text
        stripped = response.strip()
        if not (stripped.lower().startswith("<html") and stripped.lower().endswith("</html>")):
            return ValidationResult(
                is_valid=False,
                error_message="Response does not start with <html> and end with </html>.",
                hint=self.initial_hint
            )
        try:
            ET.fromstring(stripped)
            return ValidationResult(is_valid=True)
        except ET.ParseError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid HTML: {str(e)}",
                hint="Please ensure the response is valid HTML and all tags are properly closed."
            )

    async def validate_restrictive(self, response: str, **kwargs) -> ValidationResult:
        # Forgiving: extract first <html>...</html> block, accept if valid
        stripped = response.strip()
        match = re.search(r'(<html[\s\S]*?</html>)', stripped, re.IGNORECASE)
        if not match:
            return ValidationResult(
                is_valid=False,
                error_message="No valid <html>...</html> block found.",
                hint=self.initial_hint
            )
        html_block = match.group(1)
        try:
            ET.fromstring(html_block)
            return ValidationResult(is_valid=True)
        except ET.ParseError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid HTML: {str(e)}",
                hint="Please ensure the response is valid HTML and all tags are properly closed."
            )

class JSONValidator(BaseValidator):
    """Validates if the response is valid JSON."""
    
    @property
    def name(self) -> str:
        return "json"

    @property
    def initial_hint(self) -> str:
        return "Please return only valid JSON, with no explanation or extra text. The response must be a single JSON object or array."

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        """Validate if the response is valid JSON."""
        try:
            json.loads(response)
            return ValidationResult(is_valid=True)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid JSON: {str(e)}",
                hint="Please ensure the response is valid JSON. All keys and string values must be in double quotes, and the structure must be correct."
            )

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        # Strict: must be valid JSON, no extra text
        stripped = response.strip()
        try:
            json.loads(stripped)
            return ValidationResult(is_valid=True)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid JSON: {str(e)}",
                hint=self.initial_hint
            )

    async def validate_restrictive(self, response: str, **kwargs) -> ValidationResult:
        # Forgiving: extract first JSON object or array from the text
        stripped = response.strip()
        # Try to find the first {...} or [...] block
        match = re.search(r'({[\s\S]*})|\[([\s\S]*)\]', stripped)
        if not match:
            return ValidationResult(
                is_valid=False,
                error_message="No valid JSON object or array found.",
                hint=self.initial_hint
            )
        json_block = match.group(0)
        try:
            json.loads(json_block)
            return ValidationResult(is_valid=True)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid JSON: {str(e)}",
                hint=self.initial_hint
            )

class RegexValidator(BaseValidator):
    """Validates if the response matches a regex pattern."""
    
    def __init__(self, pattern: str, strict: bool = True):
        super().__init__(strict=strict)
        self.pattern = re.compile(pattern)
    
    @property
    def name(self) -> str:
        return "regex"

    @property
    def initial_hint(self) -> str:
        return f"Please ensure the response matches the required pattern: {self.pattern.pattern}, with no explanation or extra text."

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        """Validate if the response matches the pattern."""
        if self.pattern.search(response):
            return ValidationResult(is_valid=True)
        return ValidationResult(
            is_valid=False,
            error_message=f"Response does not match pattern: {self.pattern.pattern}",
            hint=f"Please ensure the response matches the required pattern: {self.pattern.pattern}"
        )

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        # Strict: response must match the pattern exactly (no extra text)
        if self.pattern.fullmatch(response.strip()):
            return ValidationResult(is_valid=True)
        return ValidationResult(
            is_valid=False,
            error_message=f"Response does not exactly match pattern: {self.pattern.pattern}",
            hint=self.initial_hint
        )

    async def validate_restrictive(self, response: str, **kwargs) -> ValidationResult:
        # Forgiving: accept if any substring matches the pattern
        if self.pattern.search(response):
            return ValidationResult(is_valid=True)
        return ValidationResult(
            is_valid=False,
            error_message=f"Response does not contain a match for pattern: {self.pattern.pattern}",
            hint=self.initial_hint
        )

class LengthValidator(BaseValidator):
    """Validates the response length."""
    
    def __init__(self, min_length: Optional[int] = None, max_length: Optional[int] = None, strict: bool = True):
        super().__init__(strict=strict)
        self.min_length = min_length
        self.max_length = max_length
    
    @property
    def name(self) -> str:
        return "length"

    @property
    def initial_hint(self) -> str:
        parts = []
        if self.min_length:
            parts.append(f"at least {self.min_length} characters long")
        if self.max_length:
            parts.append(f"no more than {self.max_length} characters long")
        if parts:
            return f"Please ensure the response is {' and '.join(parts)}, with no explanation or extra text."
        return "Please ensure the response meets the required length constraints, with no explanation or extra text."

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        """Validate if the response length is within bounds."""
        length = len(response)
        
        if self.min_length and length < self.min_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response too short: {length} < {self.min_length}",
                hint=f"Please ensure the response is at least {self.min_length} characters long."
            )
            
        if self.max_length and length > self.max_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response too long: {length} > {self.max_length}",
                hint=f"Please ensure the response is no more than {self.max_length} characters long."
            )
            
        return ValidationResult(is_valid=True)

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        # Strict: check length of the whole response
        length = len(response)
        if self.min_length and length < self.min_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response too short: {length} < {self.min_length}",
                hint=self.initial_hint
            )
        if self.max_length and length > self.max_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response too long: {length} > {self.max_length}",
                hint=self.initial_hint
            )
        return ValidationResult(is_valid=True)

    async def validate_restrictive(self, response: str, **kwargs) -> ValidationResult:
        # Forgiving: accept if any substring of the response meets the length constraints
        length = len(response)
        if self.min_length and length < self.min_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response too short: {length} < {self.min_length}",
                hint=self.initial_hint
            )
        if self.max_length and length > self.max_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response too long: {length} > {self.max_length}",
                hint=self.initial_hint
            )
        return ValidationResult(is_valid=True) 