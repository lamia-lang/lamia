from pydantic import BaseModel, ValidationError, create_model
from bs4 import BeautifulSoup
import importlib
from ..base import BaseValidator, ValidationResult

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

class HTMLStructureValidator(BaseValidator):
    """Validates if the HTML matches a given Pydantic model structure.
    - Accepts a Pydantic model class or a string (model name or full dotted path).
    - Can be used from config (with model name or full path) or from Lamia(...) constructor (with model class).
    """
    def __init__(self, model: BaseModel = None, model_name: str = None, schema: dict = None, strict: bool = True, model_module: str = "models"):
        super().__init__(strict=strict)
        if model is not None:
            self.model = model
        elif model_name is not None:
            self.model = import_model_from_path(model_name, default_module=model_module)
        elif schema is not None:
            self.model = create_model("HTMLStructureModel", **schema)
        else:
            raise ValueError("HTMLStructureValidator requires a Pydantic model, model_name, or a schema dict.")

    @classmethod
    def name(cls) -> str:
        return "html_structure"

    @property
    def initial_hint(self) -> str:
        return "Please ensure the HTML matches the required structure (tags and nesting)."

    def _html_to_dict(self, soup, model):
        result = {}
        for field, field_info in model.model_fields.items():
            tag = field
            submodel = field_info.annotation
            if hasattr(submodel, "model_fields"):
                tag_elem = soup.find(tag)
                if tag_elem:
                    result[field] = self._html_to_dict(tag_elem, submodel)
                else:
                    result[field] = None
            else:
                tag_elem = soup.find(tag)
                result[field] = tag_elem.get_text(strip=True) if tag_elem else None
        return result

    async def validate_strict(self, response: str, **kwargs) -> ValidationResult:
        soup = BeautifulSoup(response, "html.parser")
        html_dict = self._html_to_dict(soup, self.model)
        try:
            self.model.model_validate(html_dict)
            return ValidationResult(is_valid=True)
        except ValidationError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"HTML does not match structure: {e}",
                hint=self.initial_hint
            )

    async def validate_restrictive(self, response: str, **kwargs) -> ValidationResult:
        return await self.validate_strict(response, **kwargs) 