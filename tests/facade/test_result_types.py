from lamia.facade.result_types import LamiaResult
from lamia.validation.base import TrackingContext
from lamia.interpreter.command_types import CommandType


def test_lamia_result_fields():
    context = TrackingContext(
        data_provider_name="python",
        command_type=CommandType.LLM,
        metadata={}
    )
    result = LamiaResult(
        result_text="ok",
        typed_result=123,
        tracking_context=context
    )

    assert result.result_text == "ok"
    assert result.typed_result == 123
    assert result.tracking_context == context
