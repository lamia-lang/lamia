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

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        """Validate if the response is well-formed HTML."""
        try:
            # Try parsing as XML first (stricter)
            ET.fromstring(f"<root>{response}</root>")
            return ValidationResult(is_valid=True)
        except ET.ParseError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid HTML: {str(e)}",
                validation_data={"error_type": "parse_error"}
            )

class JSONValidator(BaseValidator):
    """Validates if the response is valid JSON."""
    
    @property
    def name(self) -> str:
        return "json"

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        """Validate if the response is valid JSON."""
        try:
            json.loads(response)
            return ValidationResult(is_valid=True)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid JSON: {str(e)}",
                validation_data={"error_type": "json_decode_error"}
            )

class RegexValidator(BaseValidator):
    """Validates if the response matches a regex pattern."""
    
    def __init__(self, pattern: str):
        """Initialize with regex pattern.
        
        Args:
            pattern: Regular expression pattern to match
        """
        self.pattern = re.compile(pattern)
    
    @property
    def name(self) -> str:
        return "regex"

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        """Validate if the response matches the pattern."""
        if self.pattern.search(response):
            return ValidationResult(is_valid=True)
        return ValidationResult(
            is_valid=False,
            error_message=f"Response does not match pattern: {self.pattern.pattern}",
            validation_data={"pattern": self.pattern.pattern}
        )

class LengthValidator(BaseValidator):
    """Validates the response length."""
    
    def __init__(self, min_length: Optional[int] = None, max_length: Optional[int] = None):
        """Initialize with length constraints.
        
        Args:
            min_length: Minimum allowed length
            max_length: Maximum allowed length
        """
        self.min_length = min_length
        self.max_length = max_length
    
    @property
    def name(self) -> str:
        return "length"

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        """Validate if the response length is within bounds."""
        length = len(response)
        
        if self.min_length and length < self.min_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response too short: {length} < {self.min_length}",
                validation_data={"actual_length": length, "min_length": self.min_length}
            )
            
        if self.max_length and length > self.max_length:
            return ValidationResult(
                is_valid=False,
                error_message=f"Response too long: {length} > {self.max_length}",
                validation_data={"actual_length": length, "max_length": self.max_length}
            )
            
        return ValidationResult(is_valid=True) 