import csv
import io
from collections import Counter, OrderedDict
from typing import get_origin, get_args, Union
from pydantic import BaseModel, create_model
from .document_structure_validator import DocumentStructureValidator, BaseValidationError
from ....base import ValidationResult       
from .utils import import_model_from_path
from typing import Any, Optional, Type
import re
from typing import Callable
from ....utils.pydantic_utils import get_ordered_dict_fields

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
    def __init__(self, model: Optional[Type[BaseModel]] = None, model_name: str = None, schema: dict = None, strict: bool = True, model_module: str = "models", generate_hints: bool = False):
        if model is not None:
            resolved_model = model
            # Validate OrderedDict patterns early
            try:
                get_ordered_dict_fields(model)  # This will raise if invalid patterns are used
            except ValueError as e:
                # Re-raise with context that this happened during CSV validator initialization
                raise e
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

    def _get_model_fields(self):
        """Get model fields as a list from Pydantic models, preferring ordered fields if available"""
        # If model has ordered fields, use only those (don't combine with regular fields)
        if hasattr(self.model, '__ordered_fields__') and isinstance(self.model.__ordered_fields__, OrderedDict):
            return list(self.model.__ordered_fields__.keys())
        else:
            return list(self.model.model_fields.keys())

    def _get_model_field_items(self):
        """Get model field items (name, type) as iterator from Pydantic models, preferring ordered fields if available"""
        # If model has ordered fields, use only those (don't combine with regular fields)
        if hasattr(self.model, '__ordered_fields__') and isinstance(self.model.__ordered_fields__, OrderedDict):
            for field, field_type in self.model.__ordered_fields__.items():
                yield (field, field_type)
        else:
            # Regular Pydantic fields
            for field, field_info in self.model.model_fields.items():
                yield (field, field_info.annotation)

    def _is_field_optional(self, field_name):
        """Check if a field is optional in Pydantic models"""
        field_info = self.model.model_fields.get(field_name)
        return field_info and is_optional(field_info)

    def _validate_model_is_flat(self, model):
        """Ensure model only contains primitive types, Any, or Optional primitive types"""
        from typing import get_origin, get_args
        non_primitive_fields = []
        
        def is_supported_type(field_type):
            """Check if a type is supported for CSV validation"""
            # Direct primitive types
            if field_type in (str, int, float, bool):
                return True
            
            # Any type
            if field_type is Any:
                return True
                
            # Check by name for cases where type comparison fails
            if hasattr(field_type, '__name__') and field_type.__name__ in ('str', 'int', 'float', 'bool', 'Any'):
                return True
            
            # Optional types (Union with None)
            origin = get_origin(field_type)
            if origin is Union:
                args = get_args(field_type)
                # Check if it's Optional[T] (Union[T, None])
                if len(args) == 2 and type(None) in args:
                    # Get the non-None type
                    non_none_type = next(arg for arg in args if arg is not type(None))
                    return is_supported_type(non_none_type)
            
            return False
        
        # Handle Pydantic models only
        for field, field_info in model.model_fields.items():
            field_type = field_info.annotation
            if not is_supported_type(field_type):
                type_name = getattr(field_type, '__name__', str(field_type))
                non_primitive_fields.append(f"'{field}': {type_name}")
        
        if non_primitive_fields:
            raise ValueError(
                f"CSV validation only supports primitive types (str, int, float, bool), Any, and Optional[primitive]. "
                f"Non-primitive fields found: {', '.join(non_primitive_fields)}. "
            )

    @classmethod
    def name(cls) -> str:
        return "csv_structure"

    @classmethod
    def file_type(cls) -> str:
        return "csv"

    def prepare_content_for_write(self, existing_content: str, new_content: str) -> str:
        if not existing_content or self.model is None:
            return existing_content + new_content
        model_fields = self._get_model_fields()
        expected_header = ",".join(model_fields)
        first_line = new_content.split("\n", 1)[0].strip()
        if first_line == expected_header:
            rest = new_content.split("\n", 1)
            return existing_content + (rest[1] if len(rest) > 1 else "")
        return existing_content + new_content

    @property
    def initial_hint(self) -> str:
        hint = ""
        
        # Only provide model-specific hints when generate_hints is True
        if self.model is not None and self.generate_hints:
            primitive_fields = []
            structure_lines = []
            
            for field, field_type in self._get_model_field_items():
                primitive_fields.append(field)
                structure_lines.append(f'{field}: {field_type.__name__}')
            
            expected_header = ','.join(primitive_fields)
            hint = (
                    "Please ensure the CSV matches the required structure exactly.\n"
                    f"Expected header row: {expected_header}\n"
                    "Expected columns and types:\n"
                    + '\n'.join(structure_lines) + "\n"
                )
            
            # Add clean ordering information
            ordering_hint = self._generate_field_ordering_hint(self.model)
            if ordering_hint:
                # For CSV, convert the generic ordering hint to CSV-specific language
                csv_ordering_hint = ordering_hint.replace("ORDERING:", "COLUMN ORDERING:")
                csv_ordering_hint = csv_ordering_hint.replace("key order within these fields must be preserved", "CSV columns must appear in exactly this order")
                hint += f"\n{csv_ordering_hint}\n"
            
            hint += "\n"
        
        # Always provide basic CSV format instructions
        hint += "Please return only the CSV table, starting with the header row and ending with the last row, with no explanation or extra text and without extra whitespaces in the header and content rows."
        hint += " Please use commas as separators. If any of the cells of a string type contains a comma, please surround the cell with double quotes."

        return hint

    def extract_payload(self, response: str) -> str:
        markdown_match = re.search(r'```(?:csv)?\s*\n?(.*?)\n?```', response, re.DOTALL | re.IGNORECASE)
        if markdown_match:
            csv_candidate = markdown_match.group(1).strip()
            if self._is_valid_csv(csv_candidate):
                return csv_candidate
            else:
                return None

        if self.model is not None:
            return self._extract_csv_with_model(response)
        else:
            return self._extract_csv_generic(response)
    
    def _extract_csv_with_model(self, response: str) -> str:
        """Extract CSV by looking for expected header - strict or permissive depending on mode, enforce order if OrderedDict model"""
        model_fields = self._get_model_fields()
        model_fields_set = set(model_fields)
        lines = response.split('\n')

        for i, line in enumerate(lines):
            header_line = line.strip()
            # Determine separator
            if ',' in header_line:
                separator = ','
            elif ';' in header_line:
                separator = ';'
            else:
                continue
            header_fields = [h.strip() for h in header_line.split(separator)]

            if self.strict:
                # Check if model has ordered fields that need order preservation
                
                ordered_fields = get_ordered_dict_fields(self.model)
                
                if ordered_fields:
                    # For models with ordered fields, enforce exact order for those fields
                    # Regular fields order doesn't matter
                    if set(header_fields) != model_fields_set or len(header_fields) != len(model_fields):
                        continue
                    
                    # Check that ordered fields appear in correct relative order
                    ordered_positions = []
                    for field in ordered_fields:
                        if field in header_fields:
                            ordered_positions.append(header_fields.index(field))
                    
                    # Verify ordered fields appear in ascending order (maintaining relative order)
                    if ordered_positions != sorted(ordered_positions):
                        continue  # Skip this header - ordered fields not in correct order
                else:
                    # Only require all fields present, no extras, order doesn't matter
                    if set(header_fields) != model_fields_set or len(header_fields) != len(model_fields):
                        continue
                csv_lines = [header_line]
                header_sep_count = self._count_separators_outside_quotes(header_line, separator)
                for j in range(i + 1, len(lines)):
                    line_stripped = lines[j].strip()
                    if not line_stripped:
                        break
                    if self._count_separators_outside_quotes(line_stripped, separator) != header_sep_count:
                        break
                    csv_lines.append(line_stripped)
                if len(csv_lines) > 1:
                    extracted_csv = '\n'.join(csv_lines)
                    return extracted_csv
            else:
                # Permissive: header must contain all required model fields (order and extras don't matter)
                required_fields = [field for field in model_fields if not self._is_field_optional(field)]
                if not set(required_fields).issubset(set(header_fields)):
                    continue
                csv_lines = [header_line]
                header_sep_count = self._count_separators_outside_quotes(header_line, separator)
                for j in range(i + 1, len(lines)):
                    line_stripped = lines[j].strip()
                    if not line_stripped:
                        break
                    # Row must have at least as many separators as required fields minus one
                    min_required_separators = len(required_fields) - 1 if required_fields else 0
                    if self._count_separators_outside_quotes(line_stripped, separator) < min_required_separators:
                        break
                    csv_lines.append(line_stripped)
                if len(csv_lines) > 1:
                    extracted_csv = '\n'.join(csv_lines)
                    return extracted_csv
        return None

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
        
        if csv_lines:
            extracted_csv = '\n'.join(csv_lines)
            if self._is_valid_csv(extracted_csv):
                return extracted_csv
        
        return None

    def _is_valid_csv(self, csv_text: str) -> bool:
        """Check if the CSV text can be parsed as CSV format (basic format check only)"""
        try:
            # Basic check: ensure it has at least 2 lines (header + data)
            lines = csv_text.strip().split('\n')
            if len(lines) < 2:
                return False
                
            # Check if we can at least detect a CSV dialect
            f = io.StringIO(csv_text)
            sample = f.read(1024)
            f.seek(0)
            
            # Try to sniff dialect - this will fail if it's not CSV-like
            dialect = csv.Sniffer().sniff(sample, delimiters=[',', ';'])
            
            # Try to create a reader - this will fail for completely malformed CSV
            reader = csv.reader(f, dialect=dialect)
            
            # Try to read at least one row to ensure basic parseability
            first_row = next(reader, None)
            if first_row is None:
                return False
                
            # Basic sanity check: header should have at least one field
            if len(first_row) == 0:
                return False
                
            return True
        except Exception:
            return False

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
        return self._validate_csv_recursive(tree, model)

    # Overrides the base class method because of the flat nature of CSV
    def validate_permissive_recursive(self, tree, model):
        return self._validate_csv_recursive(tree, model)

    def _validate_csv_recursive(self, tree, model):
        """Common validation logic for both strict and permissive modes."""
        header, rows = tree
        model_fields = self._get_model_fields()
        errors = []
        values = {}
        is_valid = True
        info_loss = {}
        
        # Check field order enforcement for models with __ordered_fields__
        if hasattr(model, '__ordered_fields__') and isinstance(model.__ordered_fields__, OrderedDict):
            # Extract only the ordered fields and their positions in the header
            ordered_field_names = list(model.__ordered_fields__.keys())
            ordered_positions = []
            for field in ordered_field_names:
                if field in header:
                    ordered_positions.append(header.index(field))
                else:
                    # If an ordered field is missing, we'll catch it later in missing_fields check
                    pass
            
            # Verify ordered fields appear in ascending order (maintaining relative order)
            if len(ordered_positions) > 1 and ordered_positions != sorted(ordered_positions):
                actual_order = [header[pos] for pos in ordered_positions]
                expected_order = [field for field in ordered_field_names if field in header]
                errors.append(f"Field order mismatch: ordered fields appear as {actual_order} but must be in order {expected_order}")
                is_valid = False
                
        # For pure OrderedDict models, check complete order enforcement  
        elif isinstance(model, OrderedDict) and header != model_fields:
            errors.append(f"Field order mismatch: CSV header {header} does not match expected order {model_fields}")
            is_valid = False
        
        # Build list of all fields to validate: regular model fields + ordered fields
        all_fields_to_validate = []
        
        # Start with regular model fields
        for field, field_info in model.model_fields.items():
            field_type = field_info.annotation
            all_fields_to_validate.append((field, field_type, True))  # True = from model
        
        # Add ordered fields that are not already in regular fields
        if hasattr(model, '__ordered_fields__') and isinstance(model.__ordered_fields__, OrderedDict):
            for field, field_type in model.__ordered_fields__.items():
                if field not in model.model_fields:
                    all_fields_to_validate.append((field, field_type, False))  # False = from ordered_fields
        
        # Check that all required fields are present in the header
        missing_fields = []
        for field, field_type, is_model_field in all_fields_to_validate:
            if field not in header:
                if is_model_field and not self._is_field_optional(field):
                    missing_fields.append(field)
                elif not is_model_field:  # ordered fields are always required
                    missing_fields.append(field)
        
        if missing_fields:
            errors.append(f"CSV header {header} is missing required columns {missing_fields}.")
            is_valid = False
            
        if not rows:
            errors.append("CSV has no data rows.")
            is_valid = False
        else:
            row = rows[0]
            for field, expected_type, is_model_field in all_fields_to_validate:
                value = row.get(field)
                # Handle empty cells: None or empty string should be treated as None for optional fields
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    if is_model_field and not self._is_field_optional(field):
                        if value is None:
                            errors.append(f"Row 1 is missing required field '{field}'")
                        else:
                            errors.append(f"Row 1, field '{field}' cannot be empty (required field)")
                        is_valid = False
                    elif not is_model_field:  # ordered fields are always required
                        errors.append(f"Row 1 is missing required field '{field}' from __ordered_fields__")
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
                    # Collect type conversion info loss only in permissive mode
                    if match_result.info_loss:
                        info_loss[field] = match_result.info_loss
                        
        model_instance = None
        if is_valid:
            try:
                if isinstance(model, (dict, OrderedDict)):
                    # For OrderedDict, return the OrderedDict with validated values
                    model_instance = OrderedDict((field, values[field]) for field in model_fields)
                else:
                    # For Pydantic models, only pass fields that exist in the static model
                    model_kwargs = {k: v for k, v in values.items() if k in model.model_fields}
                    model_instance = model(**model_kwargs)
                    
                    # Add ordered fields as dynamic attributes
                    if hasattr(model, '__ordered_fields__') and isinstance(model.__ordered_fields__, OrderedDict):
                        for field_name in model.__ordered_fields__.keys():
                            if field_name in values and not hasattr(model_instance, field_name):
                                # Use __dict__ to bypass Pydantic's field validation
                                model_instance.__dict__[field_name] = values[field_name]
            except Exception as e:
                errors.append(f"Model fill error: {e}")
                is_valid = False
                
        error_message = '; '.join(errors) if errors else None
        return ValidationResult(
            is_valid=is_valid,
            validated_text=self.get_subtree_string(tree),
            typed_result=model_instance,
            error_message=error_message,
            info_loss=info_loss if info_loss else None
        )

    def get_subtree_string(self, elem):
        # For CSV, elem is (header, rows) tuple
        # Return the validated data as CSV string format
        if not elem:
            return ""
            
        header, rows = elem
        if not header:
            return ""
            
        # Use csv.writer to properly handle escaping and quoting
        # Force Unix line endings for consistency across platforms
        output = io.StringIO()
        writer = csv.writer(output, lineterminator='\n')
        
        # Write header
        writer.writerow(header)
        
        # Write all rows (for CSV validation, we typically validate first row only)
        for row in rows:
            # Convert dict row back to ordered list based on header
            row_values = [row.get(col, '') for col in header]
            writer.writerow(row_values)
            
        return output.getvalue().strip()

    def get_field_order(self, tree):
        """Get the order of columns as they appear in the CSV header."""
        if tree and len(tree) >= 1:
            header, _ = tree
            return header if header else []
        return []

    def _describe_structure(self, model, indent=0):
        lines = []
        prefix = '  ' * indent
        for field, field_info in model.model_fields.items():
            lines.append(f'{prefix}{field}: {field_info.annotation.__name__}')
        return lines



