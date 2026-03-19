"""Banking identifier types."""

from __future__ import annotations

import re

from finschema.errors import CheckDigitError, InvalidCountryError, InvalidFormatError
from finschema.reference import ISO_COUNTRY_CODES

from ._pydantic import PydanticStrMixin

_IBAN_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}$")
_BIC_RE = re.compile(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")

_IBAN_LENGTHS: dict[str, int] = {
    "AT": 20,
    "BE": 16,
    "CH": 21,
    "DE": 22,
    "DK": 18,
    "ES": 24,
    "FI": 18,
    "FR": 27,
    "GB": 22,
    "IE": 22,
    "IT": 27,
    "LU": 20,
    "NL": 18,
    "NO": 15,
    "PL": 28,
    "PT": 25,
    "SE": 24,
}

_IBAN_BBAN_RE: dict[str, re.Pattern[str]] = {
    "AT": re.compile(r"^[0-9]{16}$"),
    "CH": re.compile(r"^[0-9]{5}[A-Z0-9]{12}$"),
    "DE": re.compile(r"^[0-9]{18}$"),
    "ES": re.compile(r"^[0-9]{20}$"),
    "FR": re.compile(r"^[0-9]{10}[A-Z0-9]{11}[0-9]{2}$"),
    "GB": re.compile(r"^[A-Z]{4}[0-9]{14}$"),
    "IT": re.compile(r"^[A-Z][0-9]{10}[A-Z0-9]{12}$"),
    "NL": re.compile(r"^[A-Z]{4}[0-9]{10}$"),
}


def _alpha_to_numeric(value: str) -> str:
    out: list[str] = []
    for ch in value:
        if ch.isdigit():
            out.append(ch)
        else:
            out.append(str(ord(ch) - 55))
    return "".join(out)


def _mod97(value: str) -> int:
    rem = 0
    for ch in value:
        rem = (rem * 10 + int(ch)) % 97
    return rem


def compute_iban_check_digits(country: str, bban: str) -> str:
    numeric = _alpha_to_numeric(bban + country + "00")
    check = 98 - _mod97(numeric)
    return f"{check:02d}"


class IBAN(PydanticStrMixin, str):
    def __new__(cls, value: str) -> IBAN:
        normalized = value.replace(" ", "").upper().strip()
        if not _IBAN_RE.fullmatch(normalized):
            raise InvalidFormatError(
                f"{normalized!r} is not a valid IBAN",
                details={"expected": "Country + check digits + BBAN"},
            )

        country = normalized[:2]
        if country not in ISO_COUNTRY_CODES:
            raise InvalidCountryError(
                f"Unknown country code {country!r} in IBAN",
                details={"country_code": country},
            )
        if country not in _IBAN_LENGTHS:
            raise InvalidCountryError(
                f"Country code {country!r} does not support ISO IBAN",
                details={"country_code": country, "rule": "iban_supported_country"},
            )

        expected_len = _IBAN_LENGTHS[country]
        if len(normalized) != expected_len:
            raise InvalidFormatError(
                "Invalid IBAN length",
                details={
                    "country_code": country,
                    "expected_length": expected_len,
                    "actual": len(normalized),
                },
            )

        bban = normalized[4:]
        bban_pattern = _IBAN_BBAN_RE.get(country)
        if bban_pattern is not None and not bban_pattern.fullmatch(bban):
            raise InvalidFormatError(
                "Invalid IBAN BBAN format",
                details={
                    "country_code": country,
                    "expected_bban_pattern": bban_pattern.pattern,
                    "actual_bban": bban,
                },
            )

        expected = compute_iban_check_digits(country, bban)
        actual = normalized[2:4]
        if expected != actual:
            raise CheckDigitError(
                "Invalid IBAN check digits",
                details={
                    "identifier": normalized,
                    "expected": expected,
                    "actual": actual,
                    "algorithm": "MOD-97",
                },
            )

        rearranged = _alpha_to_numeric(normalized[4:] + normalized[:4])
        if _mod97(rearranged) != 1:
            raise CheckDigitError(
                "Invalid IBAN checksum",
                details={"identifier": normalized, "algorithm": "MOD-97"},
            )

        return str.__new__(cls, normalized)


class BIC(PydanticStrMixin, str):
    def __new__(cls, value: str) -> BIC:
        normalized = value.upper().strip()
        if not _BIC_RE.fullmatch(normalized):
            raise InvalidFormatError(
                f"{normalized!r} is not a valid BIC/SWIFT code",
                details={"expected": "4 bank + 2 country + 2 location + optional 3 branch"},
            )

        country = normalized[4:6]
        if country not in ISO_COUNTRY_CODES:
            raise InvalidCountryError(
                f"Unknown country code {country!r} in BIC",
                details={"country_code": country},
            )

        return str.__new__(cls, normalized)


SWIFT = BIC
