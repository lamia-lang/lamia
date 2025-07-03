import importlib

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