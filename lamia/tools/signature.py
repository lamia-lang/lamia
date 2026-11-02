"""Render tool schemas as typed, Python-style prompt lines."""

_PY_TYPES = {"string": "str", "integer": "int", "number": "float", "boolean": "bool"}


def render_signature(name: str, schema: dict) -> str:
    """Return ``name(a: str, b: int = 0)`` for a JSON-schema ``object``."""
    required = set(schema.get("required", []))
    params = []
    for pname, prop in schema.get("properties", {}).items():
        py_type = _PY_TYPES.get(prop.get("type", ""), "any")
        if pname in required:
            params.append(f"{pname}: {py_type}")
        elif "default" in prop:
            params.append(f"{pname}: {py_type} = {prop['default']!r}")
        else:
            params.append(f"{pname}: {py_type} | None = None")  # no default: omit
    return f"{name}({', '.join(params)})"
