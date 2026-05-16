"""Cross-type validation tests for local file reading.

Ensures that validators correctly reject content whose format doesn't match
the declared return type, and accept content that does.

Known legitimate cross-type passes (not bugs):
- JSON content → YAML type: YAML is a superset of JSON by specification.
- Any content  → TEXT type: TEXT performs no format validation.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lamia.facade.lamia import Lamia
from lamia.type_converter import create_validator
from lamia.types import JSON, YAML, XML, HTML, CSV, Markdown, TEXT

SAMPLE_JSON = '{"name": "Alice", "age": 30}'
SAMPLE_YAML = "name: Alice\nage: 30\n"
SAMPLE_XML = "<root><name>Alice</name><age>30</age></root>"
SAMPLE_HTML = "<html><body><p>hello</p></body></html>"
SAMPLE_CSV = "name,age\nAlice,30\nBob,25\n"
SAMPLE_MARKDOWN = "# Title\n\nSome paragraph content here.\n"
SAMPLE_TEXT = "Just some plain text that is not structured."
SAMPLE_YAML_UNQUOTED_KEYS = "x: 1\ny:\n  - a\n  - b\n"
SAMPLE_YAML_BOOLEAN_YES = "name: John\nactive: yes\n"
SAMPLE_JSON_CANONICAL = '{"a":[1,2,true,null]}'

FORMAT_SAMPLES = {
    "json": SAMPLE_JSON,
    "yaml": SAMPLE_YAML,
    "xml": SAMPLE_XML,
    "html": SAMPLE_HTML,
    "csv": SAMPLE_CSV,
    "markdown": SAMPLE_MARKDOWN,
    "text": SAMPLE_TEXT,
}

RETURN_TYPES = {
    "json": JSON,
    "yaml": YAML,
    "xml": XML,
    "html": HTML,
    "csv": CSV,
    "markdown": Markdown,
    "text": TEXT,
}

KNOWN_VALID_CROSS = {
    ("json", "yaml"),      # YAML is a superset of JSON
    ("html", "xml"),       # well-formed HTML can be valid XML
    ("html", "markdown"),  # Markdown supports inline HTML blocks
}


def _type_label(fmt: str) -> str:
    return fmt.upper()


class TestIdentityValidation:
    """Each format validated as its own type must succeed."""

    @pytest.mark.parametrize("fmt", list(FORMAT_SAMPLES))
    @pytest.mark.asyncio
    async def test_identity_succeeds(self, fmt):
        content = FORMAT_SAMPLES[fmt]
        return_type = RETURN_TYPES[fmt]
        validator = create_validator(return_type)
        result = await validator.validate(content)
        assert result.is_valid, (
            f"{_type_label(fmt)} content should pass {_type_label(fmt)} "
            f"validation but failed: {result.error_message}"
        )


class TestTextAcceptsAll:
    """TEXT return type must accept content of every format."""

    @pytest.mark.parametrize("fmt", list(FORMAT_SAMPLES))
    @pytest.mark.asyncio
    async def test_text_accepts(self, fmt):
        content = FORMAT_SAMPLES[fmt]
        validator = create_validator(TEXT)
        result = await validator.validate(content)
        assert result.is_valid, (
            f"TEXT should accept {_type_label(fmt)} content but failed: "
            f"{result.error_message}"
        )


def _wrong_combos():
    """Generate all (source_format, target_type) pairs that MUST fail."""
    all_fmts = list(FORMAT_SAMPLES)
    for src in all_fmts:
        for tgt in all_fmts:
            if src == tgt:
                continue
            if tgt == "text":
                continue
            if (src, tgt) in KNOWN_VALID_CROSS:
                continue
            yield pytest.param(src, tgt, id=f"{src}-as-{tgt}")


class TestCrossTypeRejection:
    """Content in format X validated as type Y must be rejected (unless it's
    a known legitimate cross-type pass)."""

    @pytest.mark.parametrize("src_fmt,tgt_fmt", list(_wrong_combos()))
    @pytest.mark.asyncio
    async def test_wrong_format_rejected(self, src_fmt, tgt_fmt):
        content = FORMAT_SAMPLES[src_fmt]
        return_type = RETURN_TYPES[tgt_fmt]
        validator = create_validator(return_type)
        result = await validator.validate(content)
        assert not result.is_valid, (
            f"{_type_label(src_fmt)} content should be REJECTED by "
            f"{_type_label(tgt_fmt)} validator but was accepted"
        )


class TestKnownCrossTypeSuccesses:
    """Document legitimate cross-type passes so they don't regress."""

    @pytest.mark.asyncio
    async def test_json_content_accepted_as_yaml(self):
        validator = create_validator(YAML)
        result = await validator.validate(SAMPLE_JSON)
        assert result.is_valid, "JSON is valid YAML by spec"

    @pytest.mark.asyncio
    async def test_json_canonical_accepted_as_yaml(self):
        validator = create_validator(YAML)
        result = await validator.validate(SAMPLE_JSON_CANONICAL)
        assert result.is_valid, "Valid JSON must also be valid YAML 1.2"

    @pytest.mark.asyncio
    async def test_html_content_accepted_as_xml(self):
        validator = create_validator(XML)
        result = await validator.validate(SAMPLE_HTML)
        assert result.is_valid, "Well-formed HTML is valid XML"

    @pytest.mark.asyncio
    async def test_html_content_accepted_as_markdown(self):
        validator = create_validator(Markdown)
        result = await validator.validate(SAMPLE_HTML)
        assert result.is_valid, "Markdown supports inline HTML blocks"


class TestJsonYamlSpecCases:
    """Explicit JSON↔YAML spec examples discussed in review."""

    @pytest.mark.asyncio
    async def test_yaml_unquoted_keys_valid_yaml_invalid_json(self):
        yaml_validator = create_validator(YAML)
        yaml_result = await yaml_validator.validate(SAMPLE_YAML_UNQUOTED_KEYS)
        assert yaml_result.is_valid, "Unquoted keys + indentation list are valid YAML"

        json_validator = create_validator(JSON)
        json_result = await json_validator.validate(SAMPLE_YAML_UNQUOTED_KEYS)
        assert not json_result.is_valid, (
            "The same content must fail JSON (unquoted keys / indentation syntax)"
        )

    @pytest.mark.asyncio
    async def test_yaml_yes_scalar_valid_yaml_invalid_json(self):
        yaml_validator = create_validator(YAML)
        yaml_result = await yaml_validator.validate(SAMPLE_YAML_BOOLEAN_YES)
        assert yaml_result.is_valid, "'yes' scalar must be accepted by YAML parser"

        json_validator = create_validator(JSON)
        json_result = await json_validator.validate(SAMPLE_YAML_BOOLEAN_YES)
        assert not json_result.is_valid, "'yes' scalar syntax is invalid JSON"

    @pytest.mark.asyncio
    async def test_json_canonical_valid_for_both_json_and_yaml(self):
        json_validator = create_validator(JSON)
        json_result = await json_validator.validate(SAMPLE_JSON_CANONICAL)
        assert json_result.is_valid, "Canonical JSON sample must pass JSON"

        yaml_validator = create_validator(YAML)
        yaml_result = await yaml_validator.validate(SAMPLE_JSON_CANONICAL)
        assert yaml_result.is_valid, "Canonical JSON sample must pass YAML 1.2"


class TestCrossTypeThroughFacade:
    """Verify that cross-type rejection works end-to-end through Lamia.run_async."""

    def _run_local(self, tmp_path, content, filename, return_type):
        f = tmp_path / filename
        f.write_text(content)
        with patch('lamia.facade.lamia.LamiaEngine') as MockEngine, \
             patch('lamia.facade.lamia.get_current_source_file', return_value=str(tmp_path / "script.lm")):
            mock_engine = MagicMock()
            mock_engine.config_provider = MagicMock()
            MockEngine.return_value = mock_engine
            lamia = Lamia()
            return asyncio.run(lamia.run_async(f"./{filename}", return_type=return_type))

    def test_json_content_rejected_as_xml(self, tmp_path):
        with pytest.raises(ValueError, match="failed validation"):
            self._run_local(tmp_path, SAMPLE_JSON, "data.json", XML)

    def test_xml_content_rejected_as_json(self, tmp_path):
        with pytest.raises(ValueError, match="failed validation"):
            self._run_local(tmp_path, SAMPLE_XML, "data.xml", JSON)

    def test_csv_content_rejected_as_json(self, tmp_path):
        with pytest.raises(ValueError, match="failed validation"):
            self._run_local(tmp_path, SAMPLE_CSV, "data.csv", JSON)

    def test_yaml_content_rejected_as_xml(self, tmp_path):
        with pytest.raises(ValueError, match="failed validation"):
            self._run_local(tmp_path, SAMPLE_YAML, "data.yaml", XML)

    def test_json_content_accepted_as_yaml_through_facade(self, tmp_path):
        result = self._run_local(tmp_path, SAMPLE_JSON, "config.json", YAML)
        assert result is not None
