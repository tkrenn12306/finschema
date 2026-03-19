from __future__ import annotations

import pytest

from finschema.errors import FinschemaError, InvalidCountryError, InvalidCurrencyError
from finschema.reference import get_country_info, get_currency_decimals, get_currency_info


def test_error_string_includes_details() -> None:
    err = FinschemaError("boom", field="isin", expected=5, actual=9)
    text = str(err)
    assert "boom" in text
    assert "field" in text
    assert "expected" in text
    assert "code" in text


def test_get_currency_decimals_rejects_unknown() -> None:
    with pytest.raises(InvalidCurrencyError):
        get_currency_decimals("XXX")


def test_get_currency_info_properties() -> None:
    eur = get_currency_info("EUR")
    assert eur.numeric_code == "978"
    assert eur.decimals == 2
    assert eur.name == "Euro"


def test_get_historical_currency_info() -> None:
    dem = get_currency_info("DEM", include_historical=True)
    assert dem.deprecated is True
    assert dem.successor == "EUR"


def test_country_lookup_variants() -> None:
    de = get_country_info("DE")
    assert de.alpha3 == "DEU"
    assert get_country_info("DEU").alpha2 == "DE"
    assert get_country_info("276").alpha2 == "DE"


def test_country_lookup_invalid() -> None:
    with pytest.raises(InvalidCountryError):
        get_country_info("ZZZ")
