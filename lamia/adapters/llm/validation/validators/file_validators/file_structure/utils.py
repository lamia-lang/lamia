import importlib
from pydantic import BaseModel, create_model

def import_model_from_path(path: str, default_module: str = "models"):
    """Import a Pydantic model from a dotted path or module name."""
    if "." in path:
        parts = path.split('.')
        module_path = '.'.join(parts[:-1])
        class_name = parts[-1]
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)
    else:
        mod = importlib.import_module(default_module)
        return getattr(mod, path)

def describe_model_structure(model, indent=0, format_type="generic"):
    """
    Recursively describe the expected structure from a Pydantic model.
    
    Args:
        model: The Pydantic model to describe
        indent: Indentation level (number of spaces)
        format_type: The format to use (generic, json, xml, html, yaml, markdown, csv)
    
    Returns:
        list: Lines describing the model structure
    """
    lines = []
    prefix = '  ' * indent
    
    for field, field_info in model.model_fields.items():
        submodel = field_info.annotation
        
        if format_type == "json":
            if hasattr(submodel, "model_fields"):
                lines.append(f'{prefix}"{field}": {{')
                lines.extend(describe_model_structure(submodel, indent + 1, format_type))
                lines.append(f"{prefix}}}")
            else:
                lines.append(f'{prefix}"{field}": ...')
        
        elif format_type == "xml" or format_type == "html":
            if hasattr(submodel, "model_fields"):
                lines.append(f"{prefix}<{field}>")
                lines.extend(describe_model_structure(submodel, indent + 1, format_type))
                lines.append(f"{prefix}</{field}>")
            else:
                lines.append(f"{prefix}<{field}>...text...</{field}>")
        
        elif format_type == "yaml" or format_type == "markdown":
            if hasattr(submodel, "model_fields"):
                lines.append(f'{prefix}{field}:')
                lines.extend(describe_model_structure(submodel, indent + 1, format_type))
            else:
                lines.append(f'{prefix}{field}: ...')
        
        elif format_type == "csv":
            lines.append(f'{prefix}{field}: {field_info.annotation.__name__}')
        
        else:  # generic
            if hasattr(submodel, "model_fields"):
                lines.append(f'{prefix}{field}:')
                lines.extend(describe_model_structure(submodel, indent + 1, format_type))
            else:
                type_name = getattr(submodel, "__name__", str(submodel))
                lines.append(f'{prefix}{field}: {type_name}')
    
    return lines 