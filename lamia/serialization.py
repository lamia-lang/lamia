"""Serialization of Python values into the text format of a Lamia return type."""

import csv
import html
import io
import json
from typing import Any, Optional, Tuple, Type, Union, get_args, get_origin
from xml.etree import ElementTree as ET

import yaml
from pydantic import BaseModel

from lamia.types import CSV, HTML, JSON, TEXT, XML, YAML, Markdown, SerializableValue
from lamia.validation.validators.file_validators.file_structure.markdown_structure_validator import (
    Blockquote,
    CodeBlock,
    FencedCode,
    Heading1,
    Heading2,
    Heading3,
    Heading4,
    Heading5,
    Heading6,
    HorizontalRule,
    IndentedCode,
    OrderedList,
    UnorderedList,
)

_HEADING_LEVELS = {
    Heading1: 1,
    Heading2: 2,
    Heading3: 3,
    Heading4: 4,
    Heading5: 5,
    Heading6: 6,
}
_LIST_ITEM_TAG = "item"
_XML_ROOT_TAG = "root"


def serialize(value: Union[str, SerializableValue], return_type: Optional[Type] = None) -> str:
    """Convert *value* to text in the format of *return_type*.

    Strings are returned unchanged. Pydantic models, dicts and lists are converted to the format of the base type (``CSV``, ``JSON``, ``YAML``, ``XML``, ``HTML``, ``Markdown``, ``TEXT``, ``BaseModel``). The inner model of a parametric type such as ``CSV[Model]`` sets the CSV column order and the Markdown element types.
    """
    if isinstance(value, str):
        return value
    base_type, model = _split_type(return_type)
    if base_type is CSV:
        return _to_csv(value, model)
    if base_type is YAML:
        return _to_yaml(value)
    if base_type is XML:
        return _to_xml(value)
    if base_type is HTML:
        return _to_html(value)
    if base_type is Markdown:
        return _to_markdown(value, model)
    if base_type in (JSON, BaseModel, TEXT, str, None):
        return _to_json(value)
    raise ValueError(f"Cannot serialize to unsupported type: {return_type}")


def _to_csv(value: Any, model: Optional[Type[BaseModel]]) -> str:
    items = list(value) if isinstance(value, (list, tuple)) else [value]
    rows = [_to_data(item) for item in items]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("CSV serialization requires a Pydantic model, a dict, or a list of them")
    if model is not None:
        fieldnames = list(model.model_fields.keys())
    elif items and isinstance(items[0], BaseModel):
        fieldnames = list(type(items[0]).model_fields.keys())
    else:
        fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _scalar_text(row.get(key)) for key in fieldnames})
    return buffer.getvalue()


def _to_yaml(value: Any) -> str:
    return yaml.safe_dump(json.loads(_to_json(value)), allow_unicode=True, sort_keys=False)


def _to_xml(value: Any) -> str:
    root = ET.Element(_XML_ROOT_TAG)
    _fill_xml(root, _to_data(value))
    return ET.tostring(root, encoding="unicode")


def _fill_xml(element: ET.Element, data: Any) -> None:
    if isinstance(data, dict):
        for key, child_data in data.items():
            _fill_xml(ET.SubElement(element, key), child_data)
    elif isinstance(data, list):
        for item in data:
            _fill_xml(ET.SubElement(element, _LIST_ITEM_TAG), item)
    else:
        element.text = _scalar_text(data)


def _to_html(value: Any) -> str:
    data = _to_data(value)
    if not isinstance(data, (dict, list)):
        return f"<html><body>{html.escape(_scalar_text(data))}</body></html>"
    return f"<html>{_html_children(data)}</html>"


def _html_children(data: Any) -> str:
    if isinstance(data, dict):
        return "".join(f"<{key}>{_html_children(child)}</{key}>" for key, child in data.items())
    if isinstance(data, list):
        return "".join(f"<{_LIST_ITEM_TAG}>{_html_children(item)}</{_LIST_ITEM_TAG}>" for item in data)
    return html.escape(_scalar_text(data))


def _to_markdown(value: Any, model: Optional[Type[BaseModel]]) -> str:
    if model is None and isinstance(value, BaseModel):
        model = type(value)
    data = _to_data(value)
    if not isinstance(data, dict):
        return _to_json(data)
    blocks = []
    for key, field_value in data.items():
        field_info = model.model_fields.get(key) if model is not None else None
        if field_info is not None:
            blocks.append(_markdown_block(field_info.annotation, _scalar_text(field_value)))
        else:
            blocks.append(f"## {key}\n\n{_markdown_value(field_value)}")
    return "\n\n".join(blocks) + "\n"


def _markdown_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return f"```json\n{_to_json(value)}\n```"
    return _scalar_text(value)


def _markdown_block(annotation: Any, text: str) -> str:
    if annotation in _HEADING_LEVELS:
        return f"{'#' * _HEADING_LEVELS[annotation]} {text}"
    if annotation is Blockquote:
        return "\n".join(f"> {line}" for line in text.splitlines() or [""])
    if annotation is UnorderedList:
        return "\n".join(f"- {line}" for line in text.splitlines())
    if annotation is OrderedList:
        return "\n".join(f"{index}. {line}" for index, line in enumerate(text.splitlines(), start=1))
    if annotation in (CodeBlock, FencedCode):
        return f"```\n{text}\n```"
    if annotation is IndentedCode:
        return "\n".join(f"    {line}" for line in text.splitlines())
    if annotation is HorizontalRule:
        return "---"
    return text


def _to_json(value: Any) -> str:
    return json.dumps(_to_data(value), indent=2, ensure_ascii=False, default=str)


def _split_type(return_type: Optional[Type]) -> Tuple[Optional[Type], Optional[Type[BaseModel]]]:
    origin = get_origin(return_type)
    if origin is None:
        return return_type, None
    args = get_args(return_type)
    model = args[0] if args and isinstance(args[0], type) and issubclass(args[0], BaseModel) else None
    return origin, model


def _to_data(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): _to_data(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_data(item) for item in value]
    return value


def _scalar_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
