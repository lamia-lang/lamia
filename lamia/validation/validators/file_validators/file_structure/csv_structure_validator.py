import csv
import io
from collections import Counter
from typing import get_origin, get_args, Union
from pydantic import BaseModel, create_model
from .document_structure_validator import DocumentStructureValidator, BaseValidationError
from ....base import ValidationResult       
from .utils import import_model_from_path, describe_model_structure

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
        super().__init__(model=resolved_model, strict=strict, generate_hints=generate_hints)

    @classmethod
    def name(cls) -> str:
        return "csv_structure"

    @property
    def initial_hint(self) -> str:
        if self.model is not None:
            structure_lines = describe_model_structure(self.model, format_type="csv")
            return (
                "Please ensure the CSV matches the required structure.\n"
                "Expected columns and types:\n"
                + '\n'.join(structure_lines)
            )
        else:
            return "Please return only the CSV code, starting with the header row and ending with the last row, with no explanation or extra text."

    def parse(self, response: str):
        # Returns a tuple: (header, list of row dicts)
        f = io.StringIO(response)
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
            error_message=error_message
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
            error_message=error_message
        )