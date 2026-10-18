"""Tests for lamia.serialization."""

from datetime import date
from typing import List

import pytest
from pydantic import BaseModel

from lamia.serialization import serialize
from lamia.type_converter import create_validator
from lamia.types import CSV, HTML, JSON, TEXT, XML, YAML, Markdown
from lamia.validation.validators.file_validators.file_structure.markdown_structure_validator import (
    Heading1,
    Heading2,
    Paragraph,
)


class Row(BaseModel):
    name: str
    qty: int
    ok: bool


class Inner(BaseModel):
    city: str


class Doc(BaseModel):
    title: str
    count: int
    inner: Inner
    tags: List[Inner]


class Article(BaseModel):
    title: Heading1
    body: Paragraph


ROWS = [Row(name="a, b", qty=1, ok=True), Row(name="c", qty=2, ok=False)]
DOC = Doc(title="x & <y>", count=3, inner=Inner(city="P"), tags=[Inner(city="A"), Inner(city="B")])
ARTICLE = Article(title="Hello", body="World text")


class TestRoundTrip:
    """Serialized text passes the validator of the same return type."""

    @pytest.mark.parametrize(
        "value,return_type",
        [
            (ROWS, CSV[Row]),
            (ROWS, CSV[Row, True]),
            (ROWS[0], CSV[Row]),
            (ROWS, CSV),
            ([row.model_dump() for row in ROWS], CSV),
            (DOC, JSON),
            (DOC, JSON[Doc]),
            (DOC, JSON[Doc, True]),
            (DOC, YAML),
            (DOC, YAML[Doc, True]),
            (DOC, XML),
            (DOC, XML[Doc, True]),
            (DOC, HTML),
            (DOC, HTML[Doc, True]),
            (ARTICLE, Markdown),
            (ARTICLE, Markdown[Article, True]),
            (DOC, TEXT),
        ],
    )
    @pytest.mark.asyncio
    async def test_serialized_text_validates(self, value, return_type):
        text = serialize(value, return_type)
        result = await create_validator(return_type).validate(text)
        assert result.is_valid, f"{return_type}: {result.error_message}\n{text}"

    @pytest.mark.parametrize(
        "value,return_type",
        [
            (ROWS, CSV[Row, True]),
            (DOC, JSON[Doc, True]),
            (DOC, YAML[Doc, True]),
            (DOC, XML[Doc, True]),
            (DOC, HTML[Doc, True]),
            (ARTICLE, Markdown[Article, True]),
        ],
    )
    @pytest.mark.asyncio
    async def test_typed_result_equals_original(self, value, return_type):
        result = await create_validator(return_type).validate(serialize(value, return_type))
        assert result.typed_result == value


class TestStrings:
    @pytest.mark.parametrize("return_type", [CSV, JSON, YAML, XML, HTML, Markdown, TEXT, None])
    def test_string_returned_unchanged(self, return_type):
        assert serialize("already,text\n", return_type) == "already,text\n"


class TestCSV:
    def test_header_follows_model_field_order(self):
        rows = [{"qty": 1, "name": "a", "ok": True}]
        assert serialize(rows, CSV[Row]).splitlines()[0] == "name,qty,ok"

    def test_empty_list_with_model_writes_header_only(self):
        assert serialize([], CSV[Row]) == "name,qty,ok\n"

    def test_values_with_commas_are_quoted(self):
        assert serialize(ROWS, CSV[Row]).splitlines()[1] == '"a, b",1,true'

    def test_columns_missing_from_first_row_are_kept(self):
        rows = [{"name": "apple"}, {"name": "pear", "qty": 5}]
        assert serialize(rows, CSV) == "name,qty\napple,\npear,5\n"

    def test_scalar_items_rejected(self):
        with pytest.raises(ValueError, match="CSV serialization requires"):
            serialize([1, 2], CSV)


class TestFormats:
    def test_json_handles_non_primitive_fields(self):
        class Event(BaseModel):
            day: date

        assert '"day": "2026-01-02"' in serialize(Event(day=date(2026, 1, 2)), JSON)

    def test_yaml_preserves_field_order(self):
        assert serialize({"b": 1, "a": 2}, YAML) == "b: 1\na: 2\n"

    def test_xml_keeps_every_list_item(self):
        assert serialize({"tags": ["x", "y"]}, XML) == "<root><tags><item>x</item><item>y</item></tags></root>"

    def test_html_escapes_values(self):
        assert serialize({"title": "<b>&"}, HTML) == "<html><title>&lt;b&gt;&amp;</title></html>"

    def test_markdown_uses_field_types(self):
        class Section(BaseModel):
            title: Heading2
            body: Paragraph

        assert serialize(Section(title="T", body="B"), Markdown) == "## T\n\nB\n"

    def test_unsupported_type_rejected(self):
        with pytest.raises(ValueError, match="unsupported type"):
            serialize({"a": 1}, int)
