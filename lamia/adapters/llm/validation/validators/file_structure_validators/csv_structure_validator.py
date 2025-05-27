import csv
import io
import importlib
from pydantic import BaseModel, create_model, ValidationError
from .document_structure_validator import DocumentStructureValidator
from ...base import ValidationResult

def import_model_from_path(path: str, default_module: str = "models"):
    if "." in path:
        parts = path.split('.')
        module_path = '.'.join(parts[:-1])
        class_name = parts[-1]
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)
    else:
        mod = importlib.import_module(default_module)
        return getattr(mod, path)

def describe_model_structure(model, indent=0):
    lines = []
    prefix = '  ' * indent
    for field, field_info in model.model_fields.items():
        lines.append(f'{prefix}{field}: {field_info.annotation.__name__}')
    return lines

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
        structure_lines = describe_model_structure(self.model)
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
        # Not used for CSV
        return None

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

    def validate_strict_recursive(self, tree, model):
        header, rows = tree
        model_fields = list(model.model_fields.keys())
        # Strict: header must match model fields exactly (order and names)
        if header != model_fields:
            return False, f"CSV header {header} does not match required columns {model_fields} (order and names must match)."
        for i, row in enumerate(rows):
            try:
                model.model_validate(row)
            except ValidationError as e:
                return False, f"Row {i+1} does not match schema: {e}"
        return True, None

    def validate_permissive_recursive(self, tree, model):
        header, rows = tree
        model_fields = list(model.model_fields.keys())
        # Permissive: all model fields must be present in the correct order, extra columns allowed
        # Find the indices of model fields in the header
        try:
            indices = [header.index(field) for field in model_fields]
        except ValueError:
            return False, f"CSV header {header} does not contain all required columns {model_fields}."
        # Check that indices are strictly increasing (correct order)
        if indices != sorted(indices):
            return False, f"CSV header {header} does not have required columns {model_fields} in the correct order."
        for i, row in enumerate(rows):
            # Only validate required fields, and strip whitespace from all string values
            filtered_row = {k: v.strip() for k, v in row.items() if k in model_fields}
            try:
                model.model_validate(filtered_row)
            except ValidationError as e:
                return False, f"Row {i+1} does not match schema: {e}"
        return True, None 