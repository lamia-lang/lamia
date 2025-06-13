import csv
import io
from pydantic import BaseModel, create_model
from .document_structure_validator import DocumentStructureValidator
from ....base import ValidationResult
from .utils import import_model_from_path, describe_model_structure

class CSVStructureValidator(DocumentStructureValidator):
    """Validates if the CSV matches a given Pydantic model structure (one field per column)."""
    def __init__(self, model: BaseModel = None, model_name: str = None, schema: dict = None, strict: bool = True, model_module: str = "models"):
        if model is not None:
            resolved_model = model
        elif model_name is not None:
            resolved_model = import_model_from_path(model_name, default_module=model_module)
        elif schema is not None:
            resolved_model = create_model("CSVStructureModel", **schema)
        else:
            raise ValueError("CSVStructureValidator requires a Pydantic model, model_name, or a schema dict.")
        super().__init__(model=resolved_model, strict=strict)

    @classmethod
    def name(cls) -> str:
        return "csv_structure"

    @property
    def initial_hint(self) -> str:
        structure_lines = describe_model_structure(self.model, format_type="csv")
        return (
            "Please ensure the CSV matches the required structure.\n"
            "Expected columns and types:\n"
            + '\n'.join(structure_lines)
        )

    def parse(self, response: str):
        # Returns a tuple: (header, list of row dicts)
        f = io.StringIO(response)
        sample = f.read(1024)  # Read a sample to detect the delimiter
        f.seek(0)  # Reset file pointer to the beginning
        dialect = csv.Sniffer().sniff(sample, delimiters=[',', ';'])
        reader = csv.DictReader(f, dialect=dialect)
        rows = list(reader)
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
        if header != model_fields:
            return False, f"CSV header {header} does not match required columns {model_fields} (order and names must match)."
        for i, row in enumerate(rows):
            for field, field_info in model.model_fields.items():
                submodel = self._normalize_primitive_type(field_info.annotation)
                value = row.get(field)
                if value is None:
                    return False, f"Row {self._user_row_num(i)} is missing field '{field}'"
                if not self.type_matcher._is_type_match(value, submodel):
                    return False, f"Row {self._user_row_num(i)}, field '{field}' has value {value!r} that doesn't match expected type {submodel.__name__ if hasattr(submodel, '__name__') else submodel}"
        return True, None

    # Overrides the base class method because of the flat nature of CSV
    def validate_permissive_recursive(self, tree, model):
        header, rows = tree
        model_fields = list(model.model_fields.keys())
        try:
            indices = [header.index(field) for field in model_fields]
        except ValueError:
            return False, f"CSV header {header} does not contain all required columns {model_fields}."
        if indices != sorted(indices):
            return False, f"CSV header {header} does not have required columns {model_fields} in the correct order."
        for i, row in enumerate(rows):
            for field, field_info in model.model_fields.items():
                submodel = self._normalize_primitive_type(field_info.annotation)
                value = row.get(field)
                if value is None:
                    return False, f"Row {self._user_row_num(i)} is missing field '{field}'"
                if not self.type_matcher._is_type_match(value, submodel):
                    return False, f"Row {self._user_row_num(i)}, field '{field}' has value {value!r} that doesn't match expected type {submodel.__name__ if hasattr(submodel, '__name__') else submodel}"
        return True, None

    def _fill_model_from_tree(self, tree, model, permissive=False, info_loss=None):
        from pydantic import ValidationError
        header, rows = tree
        info_loss = info_loss or {}
        if not rows:
            return None, info_loss
        row = rows[0]
        values = {}
        for field, field_info in model.model_fields.items():
            submodel = self._normalize_primitive_type(field_info.annotation)
            value = row.get(field)
            if value is None:
                values[field] = None
                continue
            try:
                values[field] = self.type_matcher._get_primitive_value(value, submodel)
            except Exception:
                values[field] = None
        try:
            model_instance = model(**values)
        except ValidationError:
            model_instance = None
        return model_instance, info_loss 