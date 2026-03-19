"""Market-level types."""

from __future__ import annotations

from finschema.reference import get_country_info, get_currency_info

from ._pydantic import PydanticStrMixin


class CurrencyCode(PydanticStrMixin, str):
    JSON_SCHEMA_TITLE = "CurrencyCode"
    JSON_SCHEMA_PATTERN = r"^[A-Z]{3}$"
    JSON_SCHEMA_EXAMPLES = ("EUR", "USD", "JPY")
    JSON_SCHEMA_DESCRIPTION = "ISO 4217 currency code."

    def __new__(cls, value: str, *, include_historical: bool = False) -> CurrencyCode:
        normalized = value.upper().strip()
        info = get_currency_info(normalized, include_historical=include_historical)
        return str.__new__(cls, info.code)

    @property
    def name(self) -> str:
        return get_currency_info(str(self), include_historical=True).name

    @property
    def decimals(self) -> int:
        return get_currency_info(str(self), include_historical=True).decimals

    @property
    def numeric_code(self) -> str:
        return get_currency_info(str(self), include_historical=True).numeric_code

    @property
    def deprecated(self) -> bool:
        return get_currency_info(str(self), include_historical=True).deprecated

    @property
    def successor(self) -> str | None:
        return get_currency_info(str(self), include_historical=True).successor


class CountryCode(PydanticStrMixin, str):
    JSON_SCHEMA_TITLE = "CountryCode"
    JSON_SCHEMA_EXAMPLES = ("DE", "DEU", "276")
    JSON_SCHEMA_DESCRIPTION = "ISO 3166 country code (alpha-2/alpha-3/numeric)."

    def __new__(cls, value: str) -> CountryCode:
        info = get_country_info(value)
        return str.__new__(cls, info.alpha2)

    @property
    def alpha2(self) -> str:
        return str(self)

    @property
    def alpha3(self) -> str:
        return get_country_info(str(self)).alpha3

    @property
    def numeric(self) -> str:
        return get_country_info(str(self)).numeric

    @property
    def name(self) -> str:
        return get_country_info(str(self)).name

    @property
    def region(self) -> str:
        return get_country_info(str(self)).region

    @property
    def sub_region(self) -> str:
        return get_country_info(str(self)).sub_region
