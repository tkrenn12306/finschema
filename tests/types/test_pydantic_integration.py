from __future__ import annotations

from pydantic import BaseModel
from pydantic_core import SchemaValidator

from finschema.types import ISIN, BusinessDate, Money
from finschema.types._pydantic import PydanticStrMixin


class TradeModel(BaseModel):
    isin: ISIN
    trade_date: BusinessDate
    notional: Money


def test_pydantic_parsing() -> None:
    model = TradeModel(
        isin="US0378331005",
        trade_date="2026-03-19",
        notional={"amount": "100.00", "currency": "EUR"},
    )
    assert str(model.isin) == "US0378331005"
    assert model.trade_date.isoformat() == "2026-03-19"
    assert str(model.notional.currency) == "EUR"


class _DummyCode(PydanticStrMixin, str):
    pass


class _RichCode(PydanticStrMixin, str):
    JSON_SCHEMA_TITLE = "RichCode"
    JSON_SCHEMA_PATTERN = r"^[A-Z]{3}$"
    JSON_SCHEMA_EXAMPLES = ("ABC", "XYZ")
    JSON_SCHEMA_FORMAT = "code"
    JSON_SCHEMA_DESCRIPTION = "Rich schema metadata."


def test_pydantic_str_mixin_core_schema_validator() -> None:
    schema = _DummyCode.__get_pydantic_core_schema__(_DummyCode, None)
    validator = SchemaValidator(schema)
    value = validator.validate_python("abc")
    assert isinstance(value, _DummyCode)
    assert value == "abc"


def test_pydantic_str_mixin_json_schema_non_dict_handler() -> None:
    schema = _DummyCode.__get_pydantic_json_schema__({}, lambda _core: "not-a-dict")
    assert schema == {"type": "string", "title": "_DummyCode"}


def test_pydantic_str_mixin_json_schema_with_metadata() -> None:
    schema = _RichCode.__get_pydantic_json_schema__({}, lambda _core: {})
    assert schema["title"] == "RichCode"
    assert schema["pattern"] == r"^[A-Z]{3}$"
    assert schema["examples"] == ["ABC", "XYZ"]
    assert schema["format"] == "code"
    assert schema["description"] == "Rich schema metadata."


def test_pydantic_str_mixin_json_schema_keeps_existing_title() -> None:
    schema = _DummyCode.__get_pydantic_json_schema__({}, lambda _core: {"title": "ExistingTitle"})
    assert schema["title"] == "ExistingTitle"
