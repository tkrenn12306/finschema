"""Identifier types and check-digit logic."""

from __future__ import annotations

import re
import string
from typing import Final

from finschema.errors import CheckDigitError, InvalidCountryError, InvalidFormatError
from finschema.reference import ISO_COUNTRY_CODES

from ._pydantic import PydanticStrMixin

_ALNUM_MAP: Final[dict[str, int]] = {
    char: idx for idx, char in enumerate(string.digits + string.ascii_uppercase)
}
_CUSIP_EXTRA_MAP: Final[dict[str, int]] = {"*": 36, "@": 37, "#": 38}

_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_CUSIP_RE = re.compile(r"^[A-Z0-9*@#]{8}[0-9]$")
_SEDOL_RE = re.compile(r"^[0-9BCDFGHJKLMNPQRSTVWXYZ]{6}[0-9]$")
_LEI_RE = re.compile(r"^[A-Z0-9]{18}[0-9]{2}$")
_FIGI_RE = re.compile(r"^BBG[A-Z0-9]{9}$")
_VALOR_RE = re.compile(r"^[0-9]{6,9}$")
_WKN_RE = re.compile(r"^[A-Z0-9]{6}$")
_RIC_RE = re.compile(r"^[A-Z0-9._-]{1,24}(\.[A-Z0-9]{1,4})?$")


def _expand_alpha_numeric(value: str) -> str:
    return "".join(str(_ALNUM_MAP[ch]) if ch.isalpha() else ch for ch in value)


def _mod97(number: str) -> int:
    remainder = 0
    for ch in number:
        remainder = (remainder * 10 + int(ch)) % 97
    return remainder


def compute_isin_check_digit(body: str) -> int:
    expanded = _expand_alpha_numeric(body)
    total = 0
    for idx, digit in enumerate(reversed(expanded), start=1):
        n = int(digit)
        if idx % 2 == 1:
            n *= 2
        total += n // 10 + n % 10
    return (10 - total % 10) % 10


def compute_cusip_check_digit(body: str) -> int:
    def _char_value(ch: str) -> int:
        if ch in _CUSIP_EXTRA_MAP:
            return _CUSIP_EXTRA_MAP[ch]
        if ch.isdigit():
            return int(ch)
        return _ALNUM_MAP[ch]

    total = 0
    for idx, ch in enumerate(body):
        value = _char_value(ch)
        if idx % 2 == 1:
            value *= 2
        total += value // 10 + value % 10
    return (10 - total % 10) % 10


def compute_sedol_check_digit(body: str) -> int:
    weights = (1, 3, 1, 7, 3, 9)
    total = 0
    for weight, ch in zip(weights, body, strict=True):
        value = int(ch) if ch.isdigit() else _ALNUM_MAP[ch]
        total += value * weight
    return (10 - total % 10) % 10


def compute_lei_check_digits(body: str) -> str:
    if len(body) != 18:
        raise InvalidFormatError(
            "LEI body must contain exactly 18 characters", details={"body": body}
        )
    converted = _expand_alpha_numeric(body + "00")
    check = 98 - _mod97(converted)
    return f"{check:02d}"


class ISIN(PydanticStrMixin, str):
    def __new__(cls, value: str) -> ISIN:
        normalized = value.upper().strip()
        if not _ISIN_RE.fullmatch(normalized):
            raise InvalidFormatError(
                f"{normalized!r} is not a valid ISIN",
                details={
                    "expected": "2-letter country + 9 alphanum + check digit",
                    "identifier": normalized,
                },
            )

        country = normalized[:2]
        if country not in ISO_COUNTRY_CODES:
            raise InvalidCountryError(
                f"Unknown country code {country!r} in ISIN",
                details={"country_code": country},
            )

        expected = compute_isin_check_digit(normalized[:-1])
        actual = int(normalized[-1])
        if expected != actual:
            raise CheckDigitError(
                "Invalid ISIN check digit",
                details={
                    "identifier": normalized,
                    "expected": expected,
                    "actual": actual,
                    "algorithm": "Luhn (ISO 6166)",
                },
            )
        return str.__new__(cls, normalized)


class CUSIP(PydanticStrMixin, str):
    def __new__(cls, value: str) -> CUSIP:
        normalized = value.upper().strip()
        if not _CUSIP_RE.fullmatch(normalized):
            raise InvalidFormatError(
                f"{normalized!r} is not a valid CUSIP",
                details={"expected": "8 alnum/symbol + check digit", "identifier": normalized},
            )
        expected = compute_cusip_check_digit(normalized[:-1])
        actual = int(normalized[-1])
        if expected != actual:
            raise CheckDigitError(
                "Invalid CUSIP check digit",
                details={
                    "identifier": normalized,
                    "expected": expected,
                    "actual": actual,
                    "algorithm": "CUSIP Mod-10",
                },
            )
        return str.__new__(cls, normalized)


class SEDOL(PydanticStrMixin, str):
    def __new__(cls, value: str) -> SEDOL:
        normalized = value.upper().strip()
        if not _SEDOL_RE.fullmatch(normalized):
            raise InvalidFormatError(
                f"{normalized!r} is not a valid SEDOL",
                details={"expected": "6 alphanum + check digit", "identifier": normalized},
            )
        expected = compute_sedol_check_digit(normalized[:-1])
        actual = int(normalized[-1])
        if expected != actual:
            raise CheckDigitError(
                "Invalid SEDOL check digit",
                details={
                    "identifier": normalized,
                    "expected": expected,
                    "actual": actual,
                    "algorithm": "SEDOL weighted mod-10",
                },
            )
        return str.__new__(cls, normalized)


class LEI(PydanticStrMixin, str):
    def __new__(cls, value: str) -> LEI:
        normalized = value.upper().strip()
        if not _LEI_RE.fullmatch(normalized):
            raise InvalidFormatError(
                f"{normalized!r} is not a valid LEI",
                details={"expected": "20 alphanumeric chars, last 2 numeric check digits"},
            )
        expected = compute_lei_check_digits(normalized[:-2])
        actual = normalized[-2:]
        if expected != actual:
            raise CheckDigitError(
                "Invalid LEI check digits",
                details={
                    "identifier": normalized,
                    "expected": expected,
                    "actual": actual,
                    "algorithm": "MOD-97-10 (ISO 17442)",
                },
            )
        return str.__new__(cls, normalized)


class FIGI(PydanticStrMixin, str):
    def __new__(cls, value: str) -> FIGI:
        normalized = value.upper().strip()
        if not _FIGI_RE.fullmatch(normalized):
            raise InvalidFormatError(
                f"{normalized!r} is not a valid FIGI",
                details={"expected": "12 characters starting with BBG"},
            )
        return str.__new__(cls, normalized)


class VALOR(PydanticStrMixin, str):
    def __new__(cls, value: str) -> VALOR:
        normalized = value.strip()
        if not _VALOR_RE.fullmatch(normalized):
            raise InvalidFormatError(
                f"{normalized!r} is not a valid VALOR",
                details={"expected": "6 to 9 digits"},
            )
        return str.__new__(cls, normalized)


class WKN(PydanticStrMixin, str):
    def __new__(cls, value: str) -> WKN:
        normalized = value.upper().strip()
        if not _WKN_RE.fullmatch(normalized):
            raise InvalidFormatError(
                f"{normalized!r} is not a valid WKN",
                details={"expected": "6 alphanumeric characters"},
            )
        return str.__new__(cls, normalized)


class RIC(PydanticStrMixin, str):
    def __new__(cls, value: str) -> RIC:
        normalized = value.upper().strip()
        if not _RIC_RE.fullmatch(normalized):
            raise InvalidFormatError(
                f"{normalized!r} is not a valid RIC",
                details={"expected": "RIC ticker with optional exchange suffix (e.g. AAPL.OQ)"},
            )
        return str.__new__(cls, normalized)


class Ticker(PydanticStrMixin, str):
    DEFAULT_PATTERN = re.compile(r"^[A-Z0-9.]+$")
    DEFAULT_MAX_LENGTH = 16

    def __new__(
        cls,
        value: str,
        *,
        max_length: int = DEFAULT_MAX_LENGTH,
        pattern: re.Pattern[str] | None = None,
    ) -> Ticker:
        normalized = value.upper().strip()
        active_pattern = pattern or cls.DEFAULT_PATTERN
        if len(normalized) == 0 or len(normalized) > max_length:
            raise InvalidFormatError(
                f"{normalized!r} is not a valid ticker length",
                details={"expected_max_length": max_length, "actual_length": len(normalized)},
            )
        if not active_pattern.fullmatch(normalized):
            raise InvalidFormatError(
                f"{normalized!r} contains invalid ticker characters",
                details={"expected_pattern": active_pattern.pattern},
            )
        return str.__new__(cls, normalized)
