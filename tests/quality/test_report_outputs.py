from __future__ import annotations

import json
from pathlib import Path

from finschema.quality.report import QualityReport, Severity, ValidationIssue


def _sample_report() -> QualityReport:
    return QualityReport(
        issues=[
            ValidationIssue(
                rule="r_error",
                severity=Severity.ERROR,
                message="bad <value>",
                field="price",
                record_index=1,
                context={"actual": "<script>alert(1)</script>"},
            ),
            ValidationIssue(
                rule="r_warn",
                severity=Severity.WARNING,
                message="warn",
                field="isin",
                record_index=2,
            ),
        ],
        total_records=3,
    )


def test_report_to_json_returns_payload() -> None:
    report = _sample_report()
    payload = report.to_json()
    assert payload["score"] >= 0.0
    assert "stats" in payload
    assert len(payload["errors"]) == 1


def test_report_to_json_writes_file(tmp_path: Path) -> None:
    report = _sample_report()
    output = tmp_path / "report.json"
    report.to_json(output)
    raw = output.read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert payload["stats"]["total_records"] == 3


def test_report_to_html_returns_html_and_escapes_content() -> None:
    report = _sample_report()
    html = report.to_html()
    assert "<html" in html
    assert "finschema Quality Report" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert 'id="severity-filter"' in html
    assert "Export Invalid Rows CSV" in html
    assert "Trend Placeholder" in html


def test_report_to_html_writes_file(tmp_path: Path) -> None:
    report = _sample_report()
    output = tmp_path / "report.html"
    html = report.to_html(output)
    disk = output.read_text(encoding="utf-8")
    assert html == disk
    assert "Summary By Rule" in disk


def test_report_to_html_embeds_invalid_rows_for_csv_export() -> None:
    report = _sample_report()
    records = [
        {"isin": "US0378331005", "price": "1"},
        {"isin": "US0378331009", "price": "2"},
        {"isin": "US5949181045", "price": "3"},
    ]
    html = report.to_html(records=records)
    assert '"invalid_rows": [{"isin": "US0378331009", "price": "2"}]' in html


def test_report_repr_html_delegates_to_html() -> None:
    report = _sample_report()
    html = report._repr_html_()
    assert "<html" in html
