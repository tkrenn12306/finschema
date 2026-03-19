from __future__ import annotations

import string

import pytest

from finschema.errors import CheckDigitError, InvalidCountryError, InvalidFormatError
from finschema.types import BIC, CUSIP, FIGI, IBAN, ISIN, LEI, RIC, SEDOL, VALOR, WKN, Ticker
from finschema.types.banking import compute_iban_check_digits
from finschema.types.identifiers import (
    compute_cusip_check_digit,
    compute_isin_check_digit,
    compute_lei_check_digits,
    compute_sedol_check_digit,
)

COUNTRIES = ["US", "DE", "GB", "FR", "CH", "JP"]
ALNUM = string.ascii_uppercase + string.digits
SEDOL_ALPHABET = "0123456789BCDFGHJKLMNPQRSTVWXYZ"


def _make_isins() -> list[str]:
    values: list[str] = []
    for i in range(24):
        country = COUNTRIES[i % len(COUNTRIES)]
        body = f"{i:09d}"
        base = country + body
        check = compute_isin_check_digit(base)
        values.append(base + str(check))
    return values


def _make_cusips() -> list[str]:
    values: list[str] = []
    for i in range(24):
        body = f"{i:08d}"
        check = compute_cusip_check_digit(body)
        values.append(body + str(check))
    return values


def _make_sedols() -> list[str]:
    values: list[str] = []
    for i in range(24):
        body = "".join(SEDOL_ALPHABET[(i + j * 3) % len(SEDOL_ALPHABET)] for j in range(6))
        check = compute_sedol_check_digit(body)
        values.append(body + str(check))
    return values


def _make_leis() -> list[str]:
    values: list[str] = []
    for i in range(24):
        body = f"5299{i:014d}"
        check = compute_lei_check_digits(body)
        values.append(body + check)
    return values


def _make_ibans() -> list[str]:
    values: list[str] = []
    for i in range(24):
        bban = f"{37040044:08d}{i:010d}"
        check = compute_iban_check_digits("DE", bban)
        values.append(f"DE{check}{bban}")
    return values


def _make_bics() -> list[str]:
    countries = ["DE", "GB", "CH", "FR", "US", "NL"]
    values: list[str] = []
    for i in range(24):
        country = countries[i % len(countries)]
        values.append(f"BANK{country}{i % 90 + 10:02d}")
    return values


@pytest.mark.parametrize("value", _make_isins())
def test_isin_valid_cases(value: str) -> None:
    assert ISIN(value) == value


@pytest.mark.parametrize("value", _make_isins())
def test_isin_invalid_check_digit_cases(value: str) -> None:
    bad = value[:-1] + str((int(value[-1]) + 1) % 10)
    with pytest.raises(CheckDigitError):
        ISIN(bad)


def test_isin_invalid_country() -> None:
    with pytest.raises(InvalidCountryError):
        ISIN("ZZ0378331005")


def test_isin_invalid_format() -> None:
    with pytest.raises(InvalidFormatError):
        ISIN("US037833100")


@pytest.mark.parametrize("value", _make_cusips())
def test_cusip_valid_cases(value: str) -> None:
    assert CUSIP(value) == value


def test_cusip_invalid_format() -> None:
    with pytest.raises(InvalidFormatError):
        CUSIP("12 45678")


@pytest.mark.parametrize("value", _make_cusips())
def test_cusip_invalid_cases(value: str) -> None:
    bad = value[:-1] + str((int(value[-1]) + 1) % 10)
    with pytest.raises(CheckDigitError):
        CUSIP(bad)


@pytest.mark.parametrize("value", _make_sedols())
def test_sedol_valid_cases(value: str) -> None:
    assert SEDOL(value) == value


def test_sedol_invalid_format() -> None:
    with pytest.raises(InvalidFormatError):
        SEDOL("ABCD*12")


@pytest.mark.parametrize("value", _make_sedols())
def test_sedol_invalid_cases(value: str) -> None:
    bad = value[:-1] + str((int(value[-1]) + 1) % 10)
    with pytest.raises(CheckDigitError):
        SEDOL(bad)


@pytest.mark.parametrize("value", _make_leis())
def test_lei_valid_cases(value: str) -> None:
    assert LEI(value) == value


def test_lei_invalid_format() -> None:
    with pytest.raises(InvalidFormatError):
        LEI("ABC")


@pytest.mark.parametrize("value", _make_leis())
def test_lei_invalid_cases(value: str) -> None:
    bad = value[:-1] + str((int(value[-1]) + 1) % 10)
    with pytest.raises(CheckDigitError):
        LEI(bad)


def test_lei_body_length_validation() -> None:
    with pytest.raises(InvalidFormatError):
        compute_lei_check_digits("SHORT")


def test_cusip_symbol_char_mapping() -> None:
    digit = compute_cusip_check_digit("*1234567")
    assert 0 <= digit <= 9


def test_cusip_letter_char_mapping() -> None:
    digit = compute_cusip_check_digit("AB123456")
    assert 0 <= digit <= 9


@pytest.mark.parametrize("value", _make_ibans())
def test_iban_valid_cases(value: str) -> None:
    assert IBAN(value) == value


@pytest.mark.parametrize("value", _make_ibans())
def test_iban_invalid_cases(value: str) -> None:
    bad = value[:2] + "00" + value[4:]
    with pytest.raises(CheckDigitError):
        IBAN(bad)


def test_iban_us_not_supported() -> None:
    with pytest.raises(InvalidCountryError):
        IBAN("US64370400440532013000")


def test_iban_invalid_format() -> None:
    with pytest.raises(InvalidFormatError):
        IBAN("DE00")


def test_iban_unknown_country_code() -> None:
    with pytest.raises(InvalidCountryError):
        IBAN("ZZ89370400440532013000")


def test_iban_invalid_length() -> None:
    with pytest.raises(InvalidFormatError):
        IBAN("DE8937040044053201300")


def test_iban_invalid_bban_pattern() -> None:
    with pytest.raises(InvalidFormatError):
        IBAN("NL91ABNA12345A7890")


def test_iban_checksum_safety_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    from finschema.types import banking as banking_mod

    original = banking_mod._mod97
    calls = {"count": 0}

    def _patched(value: str) -> int:
        calls["count"] += 1
        if calls["count"] == 1:
            return original(value)
        return 0

    monkeypatch.setattr(banking_mod, "_mod97", _patched)
    with pytest.raises(CheckDigitError):
        IBAN("DE89370400440532013000")


@pytest.mark.parametrize("value", _make_bics())
def test_bic_valid_cases(value: str) -> None:
    assert BIC(value) == value


def test_bic_invalid_format() -> None:
    with pytest.raises(InvalidFormatError):
        BIC("ABC12")


@pytest.mark.parametrize("value", _make_bics())
def test_bic_invalid_cases(value: str) -> None:
    bad = value[:4] + "ZZ" + value[6:]
    with pytest.raises(InvalidCountryError):
        BIC(bad)


@pytest.mark.parametrize("value", ["BBG000B9XRY4", "BBG00AA12BC3", "BBG123456789"])
def test_figi_valid(value: str) -> None:
    assert FIGI(value) == value


@pytest.mark.parametrize("value", ["BGG000B9XRY4", "BBG123", "BBG00$123456"])
def test_figi_invalid(value: str) -> None:
    with pytest.raises(InvalidFormatError):
        FIGI(value)


@pytest.mark.parametrize("value", ["908440", "1234567", "123456789"])
def test_valor_valid(value: str) -> None:
    assert VALOR(value) == value


@pytest.mark.parametrize("value", ["12A345", "12345", "1234567890"])
def test_valor_invalid(value: str) -> None:
    with pytest.raises(InvalidFormatError):
        VALOR(value)


@pytest.mark.parametrize("value", ["716460", "A1B2C3", "123ABC"])
def test_wkn_valid(value: str) -> None:
    assert WKN(value) == value


@pytest.mark.parametrize("value", ["12345", "1234567", "12 3456"])
def test_wkn_invalid(value: str) -> None:
    with pytest.raises(InvalidFormatError):
        WKN(value)


@pytest.mark.parametrize("value", ["AAPL.OQ", "VOWG.DE", "MSFT", "BRK.B"])
def test_ric_valid(value: str) -> None:
    assert RIC(value) == value.upper()


@pytest.mark.parametrize("value", ["", "APPLE$", "TOO-LONG-RIC-NAME-EXCEEDING-LIMIT.XX"])
def test_ric_invalid(value: str) -> None:
    with pytest.raises(InvalidFormatError):
        RIC(value)


@pytest.mark.parametrize("value", ["AAPL", "BRK.B", "VOW3.DE"])
def test_ticker_valid(value: str) -> None:
    assert Ticker(value) == value.upper()


@pytest.mark.parametrize("value", ["", "AAPL$", "THIS_SYMBOL_IS_WAY_TOO_LONG_FOR_DEFAULT"])
def test_ticker_invalid(value: str) -> None:
    with pytest.raises(InvalidFormatError):
        Ticker(value)
