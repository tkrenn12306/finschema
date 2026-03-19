from __future__ import annotations

from finschema.quality.report import QualityReport, Severity, ValidationIssue


def test_report_stats_include_new_keys() -> None:
    report = QualityReport(issues=[], total_records=2)
    stats = report.stats
    assert stats["valid_count"] == 2
    assert stats["invalid_count"] == 0
    assert stats["valid"] == 2
    assert stats["invalid"] == 0


def test_report_fail_on_severity_threshold() -> None:
    warning_issue = ValidationIssue(rule="warn", severity=Severity.WARNING, message="warn")

    pass_report = QualityReport(
        issues=[warning_issue],
        total_records=1,
        min_score=0.0,
        fail_on_severity=Severity.ERROR,
    )
    fail_report = QualityReport(
        issues=[warning_issue],
        total_records=1,
        min_score=0.0,
        fail_on_severity=Severity.WARNING,
    )

    assert pass_report.passed is True
    assert fail_report.passed is False
