import re
import xml.etree.ElementTree as ET
from ..base import BaseValidator, ValidationResult

class HTMLValidator(BaseValidator):
    """Validates if the response is valid HTML."""
    @classmethod
    def name(cls) -> str:
        return "html"

    @property
    def initial_hint(self) -> str:
        return "Please return only the HTML code, starting with <html> and ending with </html>, with no explanation or extra text."

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
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
            return ValidationResult(is_valid=True, validated_text=html_block)
        except ET.ParseError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid HTML: {str(e)}",
                hint="Please ensure the response is valid HTML and all tags are properly closed."
            ) 