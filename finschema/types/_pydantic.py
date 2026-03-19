"""Pydantic v2 adapter helpers."""

from __future__ import annotations

from typing import Any


class PydanticStrMixin:
    """Allow custom string subclasses to validate in Pydantic models."""

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())
