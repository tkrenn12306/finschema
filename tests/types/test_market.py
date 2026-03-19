from __future__ import annotations

import pytest

from finschema.errors import InvalidCountryError, InvalidCurrencyError
from finschema.types import CountryCode, CurrencyCode


def test_currency_code_properties() -> None:
    eur = CurrencyCode("eur")
    assert str(eur) == "EUR"
    assert eur.decimals == 2
    assert eur.numeric_code == "978"
    assert eur.name == "Euro"


def test_currency_code_historical() -> None:
    dem = CurrencyCode("DEM", include_historical=True)
    assert dem.deprecated is True
    assert dem.successor == "EUR"


def test_currency_code_invalid() -> None:
    with pytest.raises(InvalidCurrencyError):
        CurrencyCode("XXX")


def test_country_code_lookup_and_properties() -> None:
    de = CountryCode("DEU")
    assert str(de) == "DE"
    assert de.alpha2 == "DE"
    assert de.alpha3 == "DEU"
    assert de.numeric == "276"
    assert de.name == "Germany"
    assert de.region == "Europe"
    assert de.sub_region == "Western Europe"


def test_country_code_invalid() -> None:
    with pytest.raises(InvalidCountryError):
        CountryCode("ZZ")
