from __future__ import annotations

import string

import pytest
from hypothesis import given
from hypothesis import strategies as st

from finschema.errors import CheckDigitError
from finschema.types import CUSIP, IBAN, ISIN, LEI, SEDOL
from finschema.types.banking import compute_iban_check_digits
from finschema.types.identifiers import (
    compute_cusip_check_digit,
    compute_isin_check_digit,
    compute_lei_check_digits,
    compute_sedol_check_digit,
)

COUNTRIES = ["US", "GB", "DE", "FR", "JP", "CH"]
ALNUM = string.ascii_uppercase + string.digits
SEDOL_SET = "0123456789BCDFGHJKLMNPQRSTVWXYZ"


@given(
    country=st.sampled_from(COUNTRIES),
    body=st.text(alphabet=ALNUM, min_size=9, max_size=9),
)
def test_isin_check_digit_property(country: str, body: str) -> None:
    base = country + body
    check = compute_isin_check_digit(base)
    valid = base + str(check)
    assert ISIN(valid) == valid

    invalid = base + str((check + 1) % 10)
    with pytest.raises(CheckDigitError):
        ISIN(invalid)


@given(body=st.text(alphabet=string.ascii_uppercase + string.digits, min_size=8, max_size=8))
def test_cusip_check_digit_property(body: str) -> None:
    check = compute_cusip_check_digit(body)
    valid = body + str(check)
    assert CUSIP(valid) == valid

    invalid = body + str((check + 1) % 10)
    with pytest.raises(CheckDigitError):
        CUSIP(invalid)


@given(body=st.text(alphabet=SEDOL_SET, min_size=6, max_size=6))
def test_sedol_check_digit_property(body: str) -> None:
    check = compute_sedol_check_digit(body)
    valid = body + str(check)
    assert SEDOL(valid) == valid

    invalid = body + str((check + 1) % 10)
    with pytest.raises(CheckDigitError):
        SEDOL(invalid)


@given(body=st.text(alphabet=ALNUM, min_size=18, max_size=18))
def test_lei_check_digit_property(body: str) -> None:
    check = compute_lei_check_digits(body)
    valid = body + check
    assert LEI(valid) == valid

    last_digit = (int(check[-1]) + 1) % 10
    invalid = body + check[:-1] + str(last_digit)
    with pytest.raises(CheckDigitError):
        LEI(invalid)


@given(bban=st.text(alphabet=string.digits, min_size=18, max_size=18))
def test_iban_check_digit_property(bban: str) -> None:
    check = compute_iban_check_digits("DE", bban)
    valid = f"DE{check}{bban}"
    assert IBAN(valid) == valid

    invalid = f"DE00{bban}"
    with pytest.raises(CheckDigitError):
        IBAN(invalid)
