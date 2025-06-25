import csv
import io
from collections import Counter
from typing import get_origin, get_args, Union
from pydantic import BaseModel, create_model
from .document_structure_validator import DocumentStructureValidator, BaseValidationError
from ....base import ValidationResult       
from .utils import import_model_from_path
from typing import Any
import re

class DuplicateHeaderError(BaseValidationError):
    """Exception for duplicate headers in structured data."""
    def __init__(self, duplicate_header: str):
        message = f"Duplicate header found: {duplicate_header}"
        hint = "Duplicate headers are not supported. Please ensure each header appears only once."
        super().__init__(message, hint=hint)

def is_optional(field_info):
    annotation = field_info.annotation
    return (
        get_origin(annotation) is Union and type(None) in get_args(annotation)
    )

class CSVStructureValidator(DocumentStructureValidator):
    """Validates if the CSV matches a given Pydantic model structure (one field per column)."""
    def __init__(self, model: BaseModel = None, model_name: str = None, schema: dict = None, strict: bool = True, model_module: str = "models", generate_hints: bool = False):
        if model is not None:
            resolved_model = model
        elif model_name is not None:
            resolved_model = import_model_from_path(model_name, default_module=model_module)
        elif schema is not None:
            resolved_model = create_model("CSVStructureModel", **schema)
        else:
            resolved_model = None
        
        # Validate that model only contains primitive types
        if resolved_model is not None:
            self._validate_model_is_flat(resolved_model)
            
        super().__init__(model=resolved_model, strict=strict, generate_hints=generate_hints)

    def _validate_model_is_flat(self, model):
        """Ensure model only contains primitive types"""
        non_primitive_fields = []
        
        for field, field_info in model.model_fields.items():
            field_type = field_info.annotation
            # Check if it's a primitive type
            if not (field_type in (str, int, float, bool) or field_type.__name__ in ('str', 'int', 'float', 'bool')):
                non_primitive_fields.append(f"'{field}': {field_info.annotation.__name__}")
        
        if non_primitive_fields:
            raise ValueError(
                f"CSV validation only supports primitive types (str, int, float, bool). "
                f"Non-primitive fields found: {', '.join(non_primitive_fields)}. "
            )

    @classmethod
    def name(cls) -> str:
        return "csv_structure"

    @classmethod
    def file_type(cls) -> str:
        return "csv"

    @property
    def initial_hint(self) -> str:
        if self.model is not None:
            # Check for non-primitive types and provide better hint
            primitive_fields = []
            non_primitive_fields = []
            
            for field, field_info in self.model.model_fields.items():
                field_type = field_info.annotation
                # Check if it's a primitive type
                if field_type in (str, int, float, bool) or field_type.__name__ in ('str', 'int', 'float', 'bool'):
                    primitive_fields.append(field)
                else:
                    non_primitive_fields.append(f"{field}: {field_info.annotation.__name__}")
            
            if non_primitive_fields:
                return (
                    "CSV validation error: CSV files only support primitive types (str, int, float, bool).\n"
                    f"Non-primitive fields found: {', '.join(non_primitive_fields)}\n"
                    "Please use a different validator for complex data structures."
                )
            
            expected_header = ', '.join(primitive_fields)
            structure_lines = [f'{field}: {field_info.annotation.__name__}' for field, field_info in self.model.model_fields.items()]
            
            hint = (
                "Please ensure the CSV matches the required structure.\n"
                f"Expected header row: {expected_header}\n"
                "Expected columns and types:\n"
                + '\n'.join(structure_lines) + "\n\n"
            )
        else:
            hint = ""
        hint += "Please return only the CSV table, starting with the header row and ending with the last row, with no explanation or extra text and without extra whitespaces in the header and content rows."
        hint += " Please use commas as separators. If any of the cells of a string type contains a comma, please surround the cell with double quotes."

        return hint

    def extract_payload(self, response: str) -> str:
        markdown_match = re.search(r'```(?:csv)?\s*\n?(.*?)\n?```', response, re.DOTALL | re.IGNORECASE)
        if markdown_match:
            return markdown_match.group(1).strip()
        
        if self.model is not None:
            return self._extract_csv_with_model(response)
        else:
            return self._extract_csv_generic(response)
    
    def _extract_csv_with_model(self, response: str) -> str:
        """Extract CSV by looking for expected header"""
        expected_headers = [",".join(self.model.model_fields.keys()),";".join(self.model.model_fields.keys())]
        lines = response.split('\n')
        
        for i, line in enumerate(lines):
            if line.strip() in expected_headers:
                separator = ',' if ',' in line else ';'
                # Found header, extract from here until empty line or end
                csv_lines = []
                for j in range(i, len(lines)):
                    line_stripped = lines[j].strip()
                    if not line_stripped:
                        break
                    # Count separators outside of quotes
                    expected_sep_count = len(self.model.model_fields.keys()) - 1
                    actual_sep_count = self._count_separators_outside_quotes(line_stripped, separator)
                    if actual_sep_count != expected_sep_count:
                        break
                    csv_lines.append(line_stripped)
                return '\n'.join(csv_lines)
        
        return response
    
    def _count_separators_outside_quotes(self, line: str, separator: str) -> int:
        """Count separators that are not inside double quotes"""
        count = 0
        in_quotes = False
        for char in line:
            if char == '"':
                in_quotes = not in_quotes
            elif char == separator and not in_quotes:
                count += 1
        return count
    
    def _extract_csv_generic(self, response: str) -> str:
        """Extract CSV - look for lines with commas or semicolons"""
        lines = response.split('\n')
        csv_lines = []
        
        for line in lines:
            line = line.strip()
            if ',' in line:
                csv_lines.append(line)
            elif csv_lines:  # Found CSV block, stop at first non-CSV line
                break
                
        return '\n'.join(csv_lines) if csv_lines else response

    def load_payload(self, payload: str) -> Any:
        # Returns a tuple: (header, list of row dicts)
        f = io.StringIO(payload)
        sample = f.read(1024)  # Read a sample to detect the delimiter
        f.seek(0)  # Reset file pointer to the beginning
        dialect = csv.Sniffer().sniff(sample, delimiters=[',', ';'])
        reader = csv.DictReader(f, dialect=dialect)
        rows = list(reader)

        # Check for duplicate headers
        if reader.fieldnames:
            header_counts = Counter(reader.fieldnames)
            duplicates = [h for h, count in header_counts.items() if count > 1]
            if duplicates:
                raise DuplicateHeaderError(duplicates[0])

        # For strict mode, do not strip whitespace from header fields
        # For permissive mode, strip whitespace from header fields and remap rows
        if self.strict:
            return (reader.fieldnames, rows)
        else:
            if reader.fieldnames:
                stripped_fieldnames = [h.strip() for h in reader.fieldnames]
                # Remap each row to use stripped header keys
                new_rows = []
                for row in rows:
                    new_row = {h.strip(): v for h, v in row.items()}
                    new_rows.append(new_row)
                return (stripped_fieldnames, new_rows)
            return (reader.fieldnames, rows)

    def find_element(self, tree, key):
        # Not used for CSV, as validation is row-based
        return None

    def get_text(self, element):
        # For CSV validation, element is the cell value (already a string)
        return element

    def has_nested(self, element):
        # CSV is always flat
        return False

    def iter_direct_children(self, tree):
        # tree is (header, rows)
        _, rows = tree
        return iter(rows)

    def get_name(self, element):
        # Not used for CSV
        return None

    def find_all(self, tree, key):
        # Return all values for a column
        _, rows = tree
        return [row.get(key) for row in rows if key in row]

    # Helper method to get user-friendly row number (1-indexed)
    def _user_row_num(self, index):
        return index + 1

    # Overrides the base class method because of the flat nature of CSV
    def validate_strict_recursive(self, tree, model):
        header, rows = tree
        model_fields = list(model.model_fields.keys())
        errors = []
        values = {}
        is_valid = True
        info_loss = {}
        # Check that all required fields are present in the header (order does not matter)
        missing_fields = [
            field for field, field_info in model.model_fields.items()
            if field not in header and not is_optional(field_info)
        ]
        if missing_fields:
            errors.append(f"CSV header {header} is missing required columns {missing_fields}.")
            is_valid = False
        if not rows:
            errors.append("CSV has no data rows.")
            is_valid = False
        else:
            row = rows[0]
            for field, field_info in model.model_fields.items():
                expected_type = field_info.annotation
                value = row.get(field)
                if value is None:
                    if not is_optional(field_info):
                        errors.append(f"Row 1 is missing required field '{field}'")
                        is_valid = False
                    values[field] = None
                    continue
                match_result = self.type_matcher.validate_and_convert(value, expected_type)
                if not match_result.is_valid:
                    errors.append(f"Row 1, field '{field}': {match_result.error}")
                    is_valid = False
                    values[field] = None
                else:
                    values[field] = match_result.value
                    # No info loss can be here when match_result.is_valid is True
        model_instance = None
        if is_valid:
            try:
                model_instance = model(**values)
            except Exception as e:
                errors.append(f"Model fill error: {e}")
                is_valid = False
        error_message = '; '.join(errors) if errors else None
        return ValidationResult(
            is_valid=is_valid,
            result_type=model_instance,
            error_message=error_message,
            info_loss=info_loss if info_loss else None
        )

    # Overrides the base class method because of the flat nature of CSV
    def validate_permissive_recursive(self, tree, model):
        header, rows = tree
        model_fields = list(model.model_fields.keys())
        errors = []
        values = {}
        is_valid = True
        info_loss = {}
        # Check that all required fields are present in the header (order does not matter)
        missing_fields = [
            field for field, field_info in model.model_fields.items()
            if field not in header and not is_optional(field_info)
        ]
        if missing_fields:
            errors.append(f"CSV header {header} is missing required columns {missing_fields}.")
            is_valid = False
        if not rows:
            errors.append("CSV has no data rows.")
            is_valid = False
        else:
            row = rows[0]
            for field, field_info in model.model_fields.items():
                expected_type = field_info.annotation
                value = row.get(field)
                if value is None:
                    if not is_optional(field_info):
                        errors.append(f"Row 1 is missing required field '{field}'")
                        is_valid = False
                    values[field] = None
                    continue
                match_result = self.type_matcher.validate_and_convert(value, expected_type)
                if not match_result.is_valid:
                    errors.append(f"Row 1, field '{field}': {match_result.error}")
                    is_valid = False
                    values[field] = None
                else:
                    values[field] = match_result.value
                    # Collect type conversion info loss
                    if match_result.info_loss:
                        info_loss[field] = match_result.info_loss
        model_instance = None
        if is_valid:
            try:
                model_instance = model(**values)
            except Exception as e:
                errors.append(f"Model fill error: {e}")
                is_valid = False
        error_message = '; '.join(errors) if errors else None
        return ValidationResult(
            is_valid=is_valid,
            result_type=model_instance,
            error_message=error_message,
            info_loss=info_loss if info_loss else None
        )

    def _describe_structure(self, model, indent=0):
        lines = []
        for field, field_info in model.model_fields.items():
            lines.append(f'{field}: {field_info.annotation.__name__}')
        return lines