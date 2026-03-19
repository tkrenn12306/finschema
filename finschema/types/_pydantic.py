"""Pydantic v2 adapter helpers."""

from __future__ import annotations

from typing import Any


class PydanticStrMixin:
    """Allow custom string subclasses to validate in Pydantic models."""

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: Any, handler: Any) -> dict[str, Any]:
        schema = handler(core_schema)
        if not isinstance(schema, dict):
            return {"type": "string", "title": cls.__name__}

        schema.setdefault("title", getattr(cls, "JSON_SCHEMA_TITLE", cls.__name__))
        pattern = getattr(cls, "JSON_SCHEMA_PATTERN", None)
        examples = getattr(cls, "JSON_SCHEMA_EXAMPLES", None)
        value_format = getattr(cls, "JSON_SCHEMA_FORMAT", None)
        description = getattr(cls, "JSON_SCHEMA_DESCRIPTION", None)

        if isinstance(pattern, str):
            schema["pattern"] = pattern
        if isinstance(examples, (list, tuple)) and examples:
            schema["examples"] = [str(item) for item in examples]
        if isinstance(value_format, str):
            schema["format"] = value_format
        if isinstance(description, str):
            schema["description"] = description

        return schema
