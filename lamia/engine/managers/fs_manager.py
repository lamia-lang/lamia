import glob
import os
from typing import Optional

from lamia.engine.managers import Manager
from lamia.engine.config_provider import ConfigProvider
from lamia.interpreter.commands import FileCommand, FileActionType
from lamia.validation.base import ValidationResult, BaseValidator


class FSManager(Manager[FileCommand]):
    def __init__(self, config_provider: ConfigProvider):
        self.config_provider = config_provider

    async def execute(
        self, command: FileCommand, validator: Optional[BaseValidator] = None
    ) -> ValidationResult:
        action = command.action
        if action == FileActionType.READ:
            return await self._read(command, validator)
        if action == FileActionType.WRITE:
            return await self._write(command, validator)
        if action == FileActionType.APPEND:
            return await self._append(command, validator)
        if action == FileActionType.EXISTS:
            return self._exists(command)
        if action == FileActionType.GLOB:
            return self._glob(command)
        raise ValueError(f"Unsupported file action: {action}")

    async def _read(
        self, command: FileCommand, validator: Optional[BaseValidator]
    ) -> ValidationResult:
        with open(command.path, "r", encoding=command.encoding) as f:
            content = f.read()
        if validator is not None:
            return await validator.validate(content)
        return ValidationResult(is_valid=True, typed_result=content, error_message=None)

    async def _write(
        self, command: FileCommand, validator: Optional[BaseValidator]
    ) -> ValidationResult:
        if command.content is None:
            raise ValueError("FileCommand.content is required for WRITE action")
        if validator is not None:
            validation_result = await validator.validate(command.content)
            if not validation_result.is_valid:
                return validation_result
        else:
            validation_result = ValidationResult(
                is_valid=True, typed_result=command.content, error_message=None
            )

        encoding_result = self._check_encoding(command.content, command.encoding)
        if encoding_result is not None:
            return encoding_result

        self._ensure_parent_dirs(command.path)
        with open(command.path, "w", encoding=command.encoding) as f:
            f.write(command.content)
        return validation_result

    async def _append(
        self, command: FileCommand, validator: Optional[BaseValidator]
    ) -> ValidationResult:
        if command.content is None:
            raise ValueError("FileCommand.content is required for APPEND action")

        existing_content = ""
        try:
            with open(command.path, "r", encoding=command.encoding) as f:
                existing_content = f.read()
        except FileNotFoundError:
            existing_content = ""

        if validator is not None:
            final_content = validator.prepare_content_for_write(existing_content, command.content)
            validation_result = await validator.validate(final_content)
            if not validation_result.is_valid:
                return validation_result
        else:
            final_content = existing_content + command.content
            validation_result = ValidationResult(
                is_valid=True, typed_result=command.content, error_message=None
            )

        encoding_result = self._check_encoding(final_content, command.encoding)
        if encoding_result is not None:
            return encoding_result

        self._ensure_parent_dirs(command.path)
        with open(command.path, "w", encoding=command.encoding) as f:
            f.write(final_content)
        return validation_result

    def _exists(self, command: FileCommand) -> ValidationResult:
        """Check if a file exists. Returns ValidationResult with typed_result=bool."""
        exists = os.path.exists(command.path)
        return ValidationResult(is_valid=True, typed_result=exists, error_message=None)

    def _glob(self, command: FileCommand) -> ValidationResult:
        """Find files matching a glob pattern. Returns ValidationResult with typed_result=list[str]."""
        matches = sorted(glob.glob(command.path, recursive=True))
        return ValidationResult(is_valid=True, typed_result=matches, error_message=None)

    def _check_encoding(self, content: str, encoding: str) -> Optional[ValidationResult]:
        """Return a failed ValidationResult if content is not encodable, else None."""
        try:
            content.encode(encoding)
        except UnicodeEncodeError as e:
            char = content[e.start]
            return ValidationResult(
                is_valid=False,
                error_message=(
                    f"Content contains characters not encodable in {encoding}: "
                    f"{e.reason} at position {e.start}"
                ),
                hint=(
                    f"Avoid characters outside the {encoding} character set. "
                    f"The problematic character is: {char!r} (U+{ord(char):04X})"
                ),
            )
        return None

    def _ensure_parent_dirs(self, path: str) -> None:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)