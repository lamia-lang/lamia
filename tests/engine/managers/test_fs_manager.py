"""Tests for filesystem manager."""

import os
import tempfile
from typing import List, Optional
from unittest.mock import Mock, mock_open, patch

import pytest

from lamia.engine.config_provider import ConfigProvider
from lamia.engine.managers.fs_manager import FSManager
from lamia.engine.managers.manager import Manager
from lamia.interpreter.commands import FileActionType, FileCommand
from lamia.validation.base import BaseValidator, ValidationResult


class MockValidator(BaseValidator):
    """Mock validator for testing."""

    def __init__(
        self,
        validation_result: ValidationResult,
        validator_name: str = "mock_validator",
    ):
        self._validation_result = validation_result
        self._name = validator_name
        self.validated_content: List[str] = []
        super().__init__()

    @property
    def name(self) -> str:
        return self._name

    @property
    def initial_hint(self) -> str:
        return "Mock validation hint"

    async def validate(self, response: str, **kwargs) -> ValidationResult:
        self.validated_content.append(response)
        return self._validation_result


def _make_command(
    action: FileActionType,
    path: str,
    content: Optional[str] = None,
    encoding: str = "utf-8",
) -> FileCommand:
    return FileCommand(
        action=action,
        path=path,
        content=content,
        encoding=encoding,
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestFSManagerInitialization:
    """Test FSManager initialization."""

    def test_initialization(self) -> None:
        config_provider = Mock(spec=ConfigProvider)
        fs_manager = FSManager(config_provider)
        assert fs_manager.config_provider == config_provider
        assert isinstance(fs_manager, Manager)

    def test_inheritance(self) -> None:
        config_provider = Mock(spec=ConfigProvider)
        fs_manager = FSManager(config_provider)
        assert isinstance(fs_manager, Manager)
        assert callable(fs_manager.execute)

@pytest.mark.asyncio
class TestFSManagerActionDispatch:
    """Test that execute routes each FileActionType correctly."""

    def setup_method(self) -> None:
        self.fs_manager = FSManager(Mock(spec=ConfigProvider))

    async def test_unsupported_action_raises(self) -> None:
        cmd = _make_command(FileActionType.READ, "/tmp/x")
        cmd.action = "NOT_A_REAL_ACTION"  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Unsupported file action"):
            await self.fs_manager.execute(cmd)


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFSManagerRead:
    """Test READ operation."""

    def setup_method(self) -> None:
        self.fs_manager = FSManager(Mock(spec=ConfigProvider))

    async def test_read_real_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Test file content\nLine 2\nLine 3")
            path = f.name
        try:
            cmd = _make_command(FileActionType.READ, path)
            result = await self.fs_manager.execute(cmd)
            assert isinstance(result, ValidationResult)
            assert result.is_valid
            assert result.typed_result == "Test file content\nLine 2\nLine 3"
        finally:
            os.unlink(path)

    async def test_read_with_validator(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("content")
            path = f.name
        try:
            cmd = _make_command(FileActionType.READ, path)
            expected = ValidationResult(is_valid=True)
            validator = MockValidator(expected)
            result = await self.fs_manager.execute(cmd, validator)
            assert result is expected
            assert validator.validated_content == ["content"]
        finally:
            os.unlink(path)

    async def test_read_with_validator_failure(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("bad")
            path = f.name
        try:
            cmd = _make_command(FileActionType.READ, path)
            expected = ValidationResult(is_valid=False, error_message="fail")
            validator = MockValidator(expected)
            result = await self.fs_manager.execute(cmd, validator)
            assert isinstance(result, ValidationResult)
            assert not result.is_valid
            assert result.error_message == "fail"
        finally:
            os.unlink(path)

    @patch("builtins.open", new_callable=mock_open, read_data="Mocked content")
    async def test_read_mocked(self, mocked_file) -> None:  # type: ignore[no-untyped-def]
        cmd = _make_command(FileActionType.READ, "/mocked/path.txt")
        result = await self.fs_manager.execute(cmd)
        assert isinstance(result, ValidationResult)
        assert result.is_valid
        assert result.typed_result == "Mocked content"
        mocked_file.assert_called_once_with("/mocked/path.txt", "r", encoding="utf-8")

    @patch("builtins.open", new_callable=mock_open, read_data="")
    async def test_read_empty_file(self, _mocked_file) -> None:  # type: ignore[no-untyped-def]
        cmd = _make_command(FileActionType.READ, "/empty.txt")
        result = await self.fs_manager.execute(cmd)
        assert isinstance(result, ValidationResult)
        assert result.is_valid
        assert result.typed_result == ""

    async def test_read_file_not_found(self) -> None:
        cmd = _make_command(FileActionType.READ, "/nonexistent/file.txt")
        with pytest.raises(FileNotFoundError):
            await self.fs_manager.execute(cmd)

    async def test_read_permission_error(self) -> None:
        with patch("builtins.open", side_effect=PermissionError("denied")):
            cmd = _make_command(FileActionType.READ, "/restricted.txt")
            with pytest.raises(PermissionError):
                await self.fs_manager.execute(cmd)


# ---------------------------------------------------------------------------
# WRITE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFSManagerWrite:
    """Test WRITE operation."""

    def setup_method(self) -> None:
        self.fs_manager = FSManager(Mock(spec=ConfigProvider))

    async def test_write_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            cmd = _make_command(FileActionType.WRITE, path, content="hello world")
            result = await self.fs_manager.execute(cmd)
            assert isinstance(result, ValidationResult)
            assert result.is_valid
            assert result.typed_result == "hello world"
            with open(path, "r") as f:
                assert f.read() == "hello world"

    async def test_write_overwrites_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            with open(path, "w") as f:
                f.write("old")
            cmd = _make_command(FileActionType.WRITE, path, content="new")
            await self.fs_manager.execute(cmd)
            with open(path, "r") as f:
                assert f.read() == "new"

    async def test_write_creates_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sub", "deep", "out.txt")
            cmd = _make_command(FileActionType.WRITE, path, content="deep")
            await self.fs_manager.execute(cmd)
            assert os.path.isfile(path)
            with open(path, "r") as f:
                assert f.read() == "deep"

    async def test_write_content_none_raises(self) -> None:
        cmd = _make_command(FileActionType.WRITE, "/tmp/dummy.txt")
        with pytest.raises(ValueError, match="content is required for WRITE"):
            await self.fs_manager.execute(cmd)

    async def test_write_with_validator_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            cmd = _make_command(FileActionType.WRITE, path, content="validated")
            expected = ValidationResult(is_valid=True)
            validator = MockValidator(expected)
            result = await self.fs_manager.execute(cmd, validator)
            assert result is expected
            assert validator.validated_content == ["validated"]
            # File should be written since validation passed
            with open(path, "r") as f:
                assert f.read() == "validated"

    async def test_write_validates_before_writing(self) -> None:
        """Invalid content should NOT be written to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            cmd = _make_command(FileActionType.WRITE, path, content="invalid data")
            expected = ValidationResult(is_valid=False, error_message="bad content")
            validator = MockValidator(expected)
            result = await self.fs_manager.execute(cmd, validator)
            assert isinstance(result, ValidationResult)
            assert not result.is_valid
            # File should NOT have been created
            assert not os.path.exists(path)


# ---------------------------------------------------------------------------
# APPEND
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFSManagerAppend:
    """Test APPEND operation."""

    def setup_method(self) -> None:
        self.fs_manager = FSManager(Mock(spec=ConfigProvider))

    async def test_append_to_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            with open(path, "w") as f:
                f.write("start")
            cmd = _make_command(FileActionType.APPEND, path, content="-end")
            result = await self.fs_manager.execute(cmd)
            assert isinstance(result, ValidationResult)
            assert result.is_valid
            assert result.typed_result == "-end"
            with open(path, "r") as f:
                assert f.read() == "start-end"

    async def test_append_creates_file_if_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "new.txt")
            cmd = _make_command(FileActionType.APPEND, path, content="first")
            await self.fs_manager.execute(cmd)
            with open(path, "r") as f:
                assert f.read() == "first"

    async def test_append_creates_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "a", "b", "c.txt")
            cmd = _make_command(FileActionType.APPEND, path, content="nested")
            await self.fs_manager.execute(cmd)
            assert os.path.isfile(path)

    async def test_append_content_none_raises(self) -> None:
        cmd = _make_command(FileActionType.APPEND, "/tmp/dummy.txt")
        with pytest.raises(ValueError, match="content is required for APPEND"):
            await self.fs_manager.execute(cmd)

    async def test_append_with_validator_reads_full_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            with open(path, "w") as f:
                f.write("base")
            cmd = _make_command(FileActionType.APPEND, path, content="+extra")
            expected = ValidationResult(is_valid=True)
            validator = MockValidator(expected)
            result = await self.fs_manager.execute(cmd, validator)
            assert result is expected
            assert validator.validated_content == ["base+extra"]

    async def test_append_delegates_to_prepare_content_for_write(self) -> None:
        """FSManager delegates full content assembly to the validator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "data.txt")
            with open(path, "w") as f:
                f.write("existing\n")
            expected = ValidationResult(is_valid=True)
            validator = MockValidator(expected)
            validator.prepare_content_for_write = lambda existing, new: existing + new.upper()  # type: ignore[assignment]
            cmd = _make_command(FileActionType.APPEND, path, content="hello")
            await self.fs_manager.execute(cmd, validator)
            with open(path, "r") as f:
                content = f.read()
            assert content == "existing\nHELLO"

    async def test_append_overwrite_semantics_via_validator(self) -> None:
        """A validator returning only new_content causes overwrite."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "data.json")
            with open(path, "w") as f:
                f.write('{"old": true}')
            expected = ValidationResult(is_valid=True)
            validator = MockValidator(expected)
            validator.prepare_content_for_write = lambda existing, new: new  # type: ignore[assignment]
            cmd = _make_command(FileActionType.APPEND, path, content='{"new": true}')
            await self.fs_manager.execute(cmd, validator)
            with open(path, "r") as f:
                content = f.read()
            assert content == '{"new": true}'


# ---------------------------------------------------------------------------
# EXISTS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFSManagerExists:
    """Test EXISTS operation."""

    def setup_method(self) -> None:
        self.fs_manager = FSManager(Mock(spec=ConfigProvider))

    async def test_exists_returns_true_for_existing_file(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"content")
            path = f.name
        try:
            cmd = _make_command(FileActionType.EXISTS, path)
            result = await self.fs_manager.execute(cmd)
            assert isinstance(result, ValidationResult)
            assert result.is_valid
            assert result.typed_result is True
        finally:
            os.unlink(path)

    async def test_exists_returns_false_for_missing_file(self) -> None:
        cmd = _make_command(FileActionType.EXISTS, "/nonexistent/path/file.txt")
        result = await self.fs_manager.execute(cmd)
        assert isinstance(result, ValidationResult)
        assert result.is_valid
        assert result.typed_result is False

    async def test_exists_returns_true_for_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = _make_command(FileActionType.EXISTS, tmpdir)
            result = await self.fs_manager.execute(cmd)
            assert result.is_valid
            assert result.typed_result is True

    async def test_exists_ignores_validator(self) -> None:
        cmd = _make_command(FileActionType.EXISTS, "/nonexistent")
        result = await self.fs_manager.execute(cmd)
        assert result.is_valid
        assert result.typed_result is False


# ---------------------------------------------------------------------------
# Text append is raw concatenation (no forced newlines)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAppendRawConcat:
    """Text append is raw concatenation — users control separators."""

    def setup_method(self) -> None:
        self.fs_manager = FSManager(Mock(spec=ConfigProvider))

    async def test_raw_concat_no_separator(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "log.txt")
            with open(path, "w") as f:
                f.write("hello")
            cmd = _make_command(FileActionType.APPEND, path, content=" world")
            await self.fs_manager.execute(cmd)
            with open(path, "r") as f:
                assert f.read() == "hello world"

    async def test_user_controls_newlines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "log.txt")
            cmd = _make_command(FileActionType.APPEND, path, content="line1\n")
            await self.fs_manager.execute(cmd)
            cmd = _make_command(FileActionType.APPEND, path, content="line2\n")
            await self.fs_manager.execute(cmd)
            with open(path, "r") as f:
                assert f.read() == "line1\nline2\n"


# ---------------------------------------------------------------------------
# Common: encoding for READ and WRITE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFSManagerEncoding:
    """Common encoding tests for operations that handle text."""

    def setup_method(self) -> None:
        self.fs_manager = FSManager(Mock(spec=ConfigProvider))

    async def test_read_utf8_special_chars(self) -> None:
        text = "Héllo wörld — ñ ü ä ö"
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False, suffix=".txt"
        ) as f:
            f.write(text)
            path = f.name
        try:
            cmd = _make_command(FileActionType.READ, path)
            result = await self.fs_manager.execute(cmd)
            assert isinstance(result, ValidationResult)
            assert result.is_valid
            assert result.typed_result == text
        finally:
            os.unlink(path)

    async def test_write_utf8_special_chars(self) -> None:
        text = "Héllo wörld — ñ ü ä ö"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "utf8.txt")
            cmd = _make_command(FileActionType.WRITE, path, content=text)
            await self.fs_manager.execute(cmd)
            with open(path, "r", encoding="utf-8") as f:
                assert f.read() == text

    async def test_write_then_read_roundtrip(self) -> None:
        text = "Round-trip test: 日本語 中文 한국어"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "roundtrip.txt")
            write_cmd = _make_command(FileActionType.WRITE, path, content=text)
            await self.fs_manager.execute(write_cmd)
            read_cmd = _make_command(FileActionType.READ, path)
            result = await self.fs_manager.execute(read_cmd)
            assert isinstance(result, ValidationResult)
            assert result.is_valid
            assert result.typed_result == text

    async def test_append_preserves_encoding(self) -> None:
        original = "café"
        appended = " résumé"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "enc.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(original)
            cmd = _make_command(FileActionType.APPEND, path, content=appended)
            await self.fs_manager.execute(cmd)
            with open(path, "r", encoding="utf-8") as f:
                assert f.read() == "café résumé"

    async def test_read_binary_file_raises(self) -> None:
        binary = b"\x00\x01\x02\x03\xff\xfe\xfd"
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(binary)
            path = f.name
        try:
            cmd = _make_command(FileActionType.READ, path)
            with pytest.raises(UnicodeDecodeError):
                await self.fs_manager.execute(cmd)
        finally:
            os.unlink(path)

    async def test_custom_encoding(self) -> None:
        text = "Latin-1: ñ é ü"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "latin1.txt")
            write_cmd = _make_command(
                FileActionType.WRITE, path, content=text, encoding="latin-1"
            )
            await self.fs_manager.execute(write_cmd)
            read_cmd = _make_command(FileActionType.READ, path, encoding="latin-1")
            result = await self.fs_manager.execute(read_cmd)
            assert isinstance(result, ValidationResult)
            assert result.is_valid
            assert result.typed_result == text


# ---------------------------------------------------------------------------
# Common error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFSManagerErrorHandling:
    """Test common error handling patterns."""

    def setup_method(self) -> None:
        self.fs_manager = FSManager(Mock(spec=ConfigProvider))

    async def test_validator_exception_propagates(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("content")
            path = f.name
        try:
            cmd = _make_command(FileActionType.READ, path)
            validator = Mock(spec=BaseValidator)
            validator.validate.side_effect = RuntimeError("validator exploded")
            with pytest.raises(RuntimeError, match="validator exploded"):
                await self.fs_manager.execute(cmd, validator)
        finally:
            os.unlink(path)

    async def test_read_none_validator_returns_operation_result(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("text")
            path = f.name
        try:
            cmd = _make_command(FileActionType.READ, path)
            result = await self.fs_manager.execute(cmd, None)
            assert isinstance(result, ValidationResult)
            assert result.is_valid
            assert result.typed_result == "text"
        finally:
            os.unlink(path)

    async def test_write_none_validator_returns_operation_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            cmd = _make_command(FileActionType.WRITE, path, content="hi")
            result = await self.fs_manager.execute(cmd, None)
            assert isinstance(result, ValidationResult)
            assert result.is_valid
            assert result.typed_result == "hi"


# ---------------------------------------------------------------------------
# Encoding validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEncodingValidation:
    """Encoding check rejects unencodable content and prevents file write."""

    def setup_method(self) -> None:
        self.fs_manager = FSManager(Mock(spec=ConfigProvider))

    # --- Rejection cases (unhappy paths) ---

    async def test_ascii_rejects_yen_sign(self) -> None:
        """¥ (U+00A5) is not encodable in ASCII."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            cmd = _make_command(
                FileActionType.WRITE, path, content="price: 100¥", encoding="ascii"
            )
            result = await self.fs_manager.execute(cmd)
            assert not result.is_valid
            assert "ascii" in result.error_message
            assert "U+00A5" in result.hint
            assert not os.path.exists(path)

    async def test_ascii_rejects_accented_chars(self) -> None:
        """é (U+00E9) is not encodable in ASCII."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            cmd = _make_command(
                FileActionType.WRITE, path, content="café", encoding="ascii"
            )
            result = await self.fs_manager.execute(cmd)
            assert not result.is_valid
            assert "ascii" in result.error_message
            assert not os.path.exists(path)

    async def test_latin1_rejects_emoji(self) -> None:
        """🎉 (U+1F389) is not encodable in latin-1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            cmd = _make_command(
                FileActionType.WRITE, path, content="done 🎉", encoding="latin-1"
            )
            result = await self.fs_manager.execute(cmd)
            assert not result.is_valid
            assert "latin-1" in result.error_message
            assert not os.path.exists(path)

    async def test_latin1_rejects_cjk(self) -> None:
        """日 (U+65E5) is not encodable in latin-1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            cmd = _make_command(
                FileActionType.WRITE, path, content="日本語", encoding="latin-1"
            )
            result = await self.fs_manager.execute(cmd)
            assert not result.is_valid
            assert "latin-1" in result.error_message

    async def test_ascii_rejects_euro_sign(self) -> None:
        """€ (U+20AC) is not encodable in ASCII."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            cmd = _make_command(
                FileActionType.WRITE, path, content="50€", encoding="ascii"
            )
            result = await self.fs_manager.execute(cmd)
            assert not result.is_valid
            assert "U+20AC" in result.hint
            assert not os.path.exists(path)

    async def test_append_rejects_unencodable_and_preserves_file(self) -> None:
        """Append with unencodable content must NOT corrupt existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            with open(path, "w", encoding="latin-1") as f:
                f.write("existing")
            cmd = _make_command(
                FileActionType.APPEND, path, content=" 🚀", encoding="latin-1"
            )
            result = await self.fs_manager.execute(cmd)
            assert not result.is_valid
            with open(path, "r", encoding="latin-1") as f:
                assert f.read() == "existing"

    async def test_hint_shows_exact_codepoint(self) -> None:
        """Hint must identify the problematic character with U+XXXX."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            cmd = _make_command(
                FileActionType.WRITE, path, content="a→b", encoding="ascii"
            )
            result = await self.fs_manager.execute(cmd)
            assert not result.is_valid
            assert "U+2192" in result.hint

    async def test_error_message_includes_position(self) -> None:
        """Error message must report the character position."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            cmd = _make_command(
                FileActionType.WRITE, path, content="abc¥", encoding="ascii"
            )
            result = await self.fs_manager.execute(cmd)
            assert not result.is_valid
            assert "position 3" in result.error_message

    # --- Happy paths (sanity checks that valid content writes successfully) ---

    async def test_utf8_accepts_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            cmd = _make_command(
                FileActionType.WRITE, path, content="¥€🎉日本語", encoding="utf-8"
            )
            result = await self.fs_manager.execute(cmd)
            assert result.is_valid
            assert os.path.exists(path)

    async def test_latin1_accepts_within_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.txt")
            cmd = _make_command(
                FileActionType.WRITE, path, content="café ¥ résumé", encoding="latin-1"
            )
            result = await self.fs_manager.execute(cmd)
            assert result.is_valid
            assert os.path.exists(path)


# ---------------------------------------------------------------------------
# Resource cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFSManagerClose:
    """FSManager.close() must be a no-op and must not raise AttributeError."""

    def setup_method(self) -> None:
        self.fs_manager = FSManager(Mock(spec=ConfigProvider))

    async def test_close_does_not_raise(self) -> None:
        await self.fs_manager.close()

    async def test_close_returns_none(self) -> None:
        result = await self.fs_manager.close()
        assert result is None

    async def test_close_is_idempotent(self) -> None:
        await self.fs_manager.close()
        await self.fs_manager.close()