"""Tests for ValueManager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from lamia.engine.managers.value_manager import ValueManager
from lamia.facade.lamia import Lamia
from lamia.interpreter.command_types import CommandType
from lamia.interpreter.commands import ValueCommand
from lamia.type_converter import create_validator
from lamia.types import CSV, JSON
from lamia.validation.base import ValidationResult


class Row(BaseModel):
    name: str
    qty: int


@pytest.fixture
def manager():
    return ValueManager(MagicMock())


class TestValueManager:
    @pytest.mark.asyncio
    async def test_serializes_and_validates(self, manager):
        command = ValueCommand([Row(name="a", qty=1)], CSV[Row])

        result = await manager.execute(command, create_validator(CSV[Row]))

        assert result.is_valid
        assert result.raw_text.splitlines() == ["name,qty", "a,1"]
        assert result.typed_result == [Row(name="a", qty=1)]
        assert result.execution_context.command_type == CommandType.VALUE

    @pytest.mark.asyncio
    async def test_invalid_value_reported(self, manager):
        command = ValueCommand({"name": "a"}, JSON[Row, True])

        result = await manager.execute(command, create_validator(JSON[Row, True]))

        assert not result.is_valid

    @pytest.mark.asyncio
    async def test_without_validator_returns_text(self, manager):
        result = await manager.execute(ValueCommand({"a": 1}), None)

        assert result.is_valid
        assert result.typed_result == '{\n  "a": 1\n}'


class TestFacadeRouting:
    @pytest.mark.asyncio
    async def test_non_string_command_becomes_value_command(self):
        with patch("lamia.facade.lamia.LamiaEngine") as MockEngine:
            engine = MagicMock()
            engine.execute = AsyncMock(return_value=ValidationResult(is_valid=True, raw_text="name,qty\na,1\n"))
            engine.config_provider = MagicMock()
            MockEngine.return_value = engine
            rows = [Row(name="a", qty=1)]

            await Lamia().run_async(rows, CSV[Row])

            command = engine.execute.call_args.args[0]
            assert isinstance(command, ValueCommand)
            assert command.value is rows
            assert command.return_type == CSV[Row]

    @pytest.mark.asyncio
    async def test_unsupported_value_rejected(self):
        with patch("lamia.facade.lamia.LamiaEngine") as MockEngine:
            MockEngine.return_value = MagicMock()

            with pytest.raises(TypeError, match="Unsupported command type: int"):
                await Lamia().run_async(5, JSON)
