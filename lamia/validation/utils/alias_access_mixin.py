from __future__ import annotations

from functools import lru_cache
from typing import Any, Type

from pydantic import BaseModel


class AliasAccessMixin:
    """Enable attribute access via Pydantic field aliases.

    Typed approach: keeps normal attribute access by field name intact,
    and adds alias-based access via __getattr__ with clear typing.
    """

    def __getattr__(self, name: str) -> Any:  # noqa: D401 - simple alias resolver
        # Access model_fields from class per Pydantic v2 guidance
        fields = self.__class__.model_fields  # type: ignore[attr-defined]
        for field_name, field_info in fields.items():
            alias = getattr(field_info, "alias", None)
            if alias == name:
                return getattr(self, field_name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


@lru_cache(maxsize=256)
def wrap_model_class_with_alias_mixin(model_cls: Type[BaseModel]) -> Type[BaseModel]:
    """Return a subclass of model_cls that includes AliasAccessMixin.

    Cached to avoid generating multiple identical subclasses.
    """
    # If it's already enhanced, return as-is
    try:
        if issubclass(model_cls, AliasAccessMixin):
            return model_cls
    except TypeError:
        # model_cls may not be a class in edge cases; just return as-is
        return model_cls

    enhanced_name = f"{model_cls.__name__}WithAliasAccess"
    enhanced_cls = type(enhanced_name, (AliasAccessMixin, model_cls), {})
    return enhanced_cls


