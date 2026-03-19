from __future__ import annotations

import pytest

from finschema.errors import CheckDigitError, InvalidCountryError, InvalidFormatError
from finschema.types import BIC, CUSIP, IBAN, ISIN, LEI, SEDOL
from finschema.types import banking as banking_module
from finschema.types.identifiers import compute_cusip_check_digit, compute_lei_check_digits


def test_isin_valid() -> None:
    assert ISIN("US0378331005") == "US0378331005"


def test_isin_invalid_check_digit() -> None:
    with pytest.raises(CheckDigitError) as exc:
        ISIN("US0378331009")
    assert exc.value.details["expected"] == 5
    assert exc.value.details["actual"] == 9
    assert exc.value.details["algorithm"] == "Luhn (ISO 6166)"


def test_isin_invalid_country() -> None:
    with pytest.raises(InvalidCountryError):
        ISIN("XX0378331005")


def test_cusip_valid() -> None:
    assert CUSIP("037833100") == "037833100"


def test_cusip_invalid_check_digit() -> None:
    with pytest.raises(CheckDigitError):
        CUSIP("037833109")


def test_sedol_valid() -> None:
    assert SEDOL("B0YQ5W0") == "B0YQ5W0"


def test_lei_valid() -> None:
    assert LEI("529900T8BM49AURSDO55") == "529900T8BM49AURSDO55"


def test_lei_invalid_check_digit() -> None:
    with pytest.raises(CheckDigitError):
        LEI("529900T8BM49AURSDO99")


def test_iban_valid() -> None:
    assert IBAN("DE89370400440532013000") == "DE89370400440532013000"


def test_iban_invalid_check_digit() -> None:
    with pytest.raises(CheckDigitError):
        IBAN("DE00370400440532013000")


def test_iban_invalid_format() -> None:
    with pytest.raises(InvalidFormatError):
        IBAN("BAD")


def test_iban_invalid_country() -> None:
    with pytest.raises(InvalidCountryError):
        IBAN("XX89370400440532013000")


def test_iban_invalid_length() -> None:
    with pytest.raises(InvalidFormatError):
        IBAN("DE8937040044053201300")


def test_iban_checksum_guard_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    original_mod97 = banking_module._mod97
    state = {"calls": 0}

    def fake_mod97(value: str) -> int:
        state["calls"] += 1
        if state["calls"] == 2:
            return 2
        return original_mod97(value)

    monkeypatch.setattr(banking_module, "_mod97", fake_mod97)
    with pytest.raises(CheckDigitError):
        IBAN("DE89370400440532013000")


def test_bic_valid() -> None:
    assert BIC("DEUTDEFF500") == "DEUTDEFF500"


def test_bic_invalid_country() -> None:
    with pytest.raises(InvalidCountryError):
        BIC("DEUTXXFF")


def test_invalid_format() -> None:
    with pytest.raises(InvalidFormatError):
        ISIN("INVALID123")


def test_bic_invalid_format() -> None:
    with pytest.raises(InvalidFormatError):
        BIC("ABC")


def test_cusip_with_special_chars_supported() -> None:
    body = "AB12*34@"
    check = compute_cusip_check_digit(body)
    assert CUSIP(body + str(check)) == body + str(check)


def test_cusip_invalid_format() -> None:
    with pytest.raises(InvalidFormatError):
        CUSIP("123")


def test_sedol_invalid_format() -> None:
    with pytest.raises(InvalidFormatError):
        SEDOL("AEIOU01")


def test_lei_invalid_format() -> None:
    with pytest.raises(InvalidFormatError):
        LEI("123")


def test_compute_lei_check_digits_rejects_invalid_body_length() -> None:
    with pytest.raises(InvalidFormatError):
        compute_lei_check_digits("ABC")
