"""Quality report data structures."""

from __future__ import annotations

import importlib
import json
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import Enum
from html import escape
from pathlib import Path
from typing import Any


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    rule: str
    severity: Severity
    message: str
    field: str | None = None
    record_index: int | None = None
    context: dict[str, Any] = dataclass_field(default_factory=dict)


class QualityReport:
    def __init__(self, issues: list[ValidationIssue], total_records: int, min_score: float = 0.95):
        self._issues = list(issues)
        self._total_records = max(0, total_records)
        self._min_score = min_score

    @property
    def issues(self) -> list[ValidationIssue]:
        return list(self._issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self._issues if issue.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self._issues if issue.severity == Severity.WARNING]

    @property
    def info(self) -> list[ValidationIssue]:
        return [issue for issue in self._issues if issue.severity == Severity.INFO]

    @property
    def by_rule(self) -> dict[str, list[ValidationIssue]]:
        grouped: dict[str, list[ValidationIssue]] = defaultdict(list)
        for issue in self._issues:
            grouped[issue.rule].append(issue)
        return dict(grouped)

    @property
    def by_field(self) -> dict[str, list[ValidationIssue]]:
        grouped: dict[str, list[ValidationIssue]] = defaultdict(list)
        for issue in self._issues:
            grouped[issue.field or "__root__"].append(issue)
        return dict(grouped)

    @property
    def score(self) -> float:
        denominator = max(self._total_records, 1)
        penalties = len(self.errors) * 1.0 + len(self.warnings) * 0.25 + len(self.info) * 0.05
        return max(0.0, 1.0 - penalties / float(denominator))

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0 and self.score >= self._min_score

    @property
    def stats(self) -> dict[str, float | int]:
        invalid = self._compute_invalid_record_count()
        valid = max(0, self._total_records - invalid)
        error_rate = float(invalid) / float(self._total_records) if self._total_records else 0.0
        return {
            "total_records": self._total_records,
            "valid": valid,
            "invalid": invalid,
            "error_rate": error_rate,
        }

    def _compute_invalid_record_count(self) -> int:
        if self._total_records == 0:
            return 0

        indexed_errors = {
            issue.record_index for issue in self.errors if issue.record_index is not None
        }
        has_global_error = any(issue.record_index is None for issue in self.errors)

        if self._total_records == 1 and (indexed_errors or has_global_error):
            return 1

        if indexed_errors:
            return len(indexed_errors)

        if has_global_error:
            return self._total_records

        return 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "stats": self.stats,
            "errors": [self._issue_to_dict(issue) for issue in self.errors],
            "warnings": [self._issue_to_dict(issue) for issue in self.warnings],
            "info": [self._issue_to_dict(issue) for issue in self.info],
            "by_rule": {
                rule: [self._issue_to_dict(issue) for issue in issues]
                for rule, issues in self.by_rule.items()
            },
            "by_field": {
                field: [self._issue_to_dict(issue) for issue in issues]
                for field, issues in self.by_field.items()
            },
        }

    def to_json(self, path: str | Path | None = None) -> dict[str, Any]:
        payload = self.to_dict()
        if path is not None:
            target = Path(path)
            target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload

    def to_dataframe(self) -> Any:
        try:
            pandas_module = importlib.import_module("pandas")
        except Exception as exc:  # pragma: no cover - import environment dependent
            raise RuntimeError(
                "pandas is not installed. Install extras with: pip install finschema[pandas]"
            ) from exc

        rows: list[dict[str, Any]] = []
        for issue in self._issues:
            row = self._issue_to_dict(issue)
            rows.append(row)
        return pandas_module.DataFrame(rows)

    def to_html(self, path: str | Path | None = None) -> str:
        payload = self.to_dict()
        stats = payload["stats"]
        score = payload["score"]
        passed = payload["passed"]

        def _render_issue_rows(rows: list[dict[str, Any]]) -> str:
            if not rows:
                return "<tr><td colspan='6'>None</td></tr>"

            rendered: list[str] = []
            for row in rows:
                context = json.dumps(row.get("context", {}), ensure_ascii=False, sort_keys=True)
                rendered.append(
                    "<tr>"
                    f"<td>{escape(str(row.get('rule')))}</td>"
                    f"<td>{escape(str(row.get('severity')))}</td>"
                    f"<td>{escape(str(row.get('field')))}</td>"
                    f"<td>{escape(str(row.get('record_index')))}</td>"
                    f"<td>{escape(str(row.get('message')))}</td>"
                    f"<td><code>{escape(context)}</code></td>"
                    "</tr>"
                )
            return "".join(rendered)

        all_rows: list[dict[str, Any]] = []
        all_rows.extend(payload["errors"])
        all_rows.extend(payload["warnings"])
        all_rows.extend(payload["info"])

        by_rule_rows = (
            "".join(
                f"<tr><td>{escape(str(rule))}</td><td>{len(issues)}</td></tr>"
                for rule, issues in payload["by_rule"].items()
            )
            or "<tr><td colspan='2'>None</td></tr>"
        )

        by_field_rows = (
            "".join(
                f"<tr><td>{escape(str(field))}</td><td>{len(issues)}</td></tr>"
                for field, issues in payload["by_field"].items()
            )
            or "<tr><td colspan='2'>None</td></tr>"
        )

        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>finschema Quality Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f8fb;
      --card: #ffffff;
      --text: #18202a;
      --muted: #5f6b7a;
      --border: #d8e0ea;
      --ok: #156d3f;
      --bad: #9b1c1c;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    .container {{
      max-width: 1100px;
      margin: 24px auto;
      padding: 0 16px 32px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
      margin-bottom: 16px;
    }}
    h1, h2 {{
      margin: 0 0 10px;
      font-weight: 600;
    }}
    .muted {{
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .status {{
      font-weight: 700;
      color: {("#156d3f" if passed else "#9b1c1c")};
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.92rem;
    }}
    th, td {{
      text-align: left;
      border-bottom: 1px solid var(--border);
      padding: 8px 10px;
      vertical-align: top;
    }}
    th {{
      background: #f0f4f8;
      font-weight: 600;
    }}
    code {{
      white-space: pre-wrap;
      word-break: break-word;
    }}
  </style>
</head>
<body>
  <div class="container">
    <section class="card">
      <h1>finschema Quality Report</h1>
      <p class="muted">Standalone report generated from QualityReport.</p>
      <p><strong>Score:</strong> {score:.4f} | <strong>Status:</strong> <span class="status">{"PASS" if passed else "FAIL"}</span></p>
      <p><strong>Total:</strong> {stats["total_records"]} | <strong>Valid:</strong> {stats["valid"]} | <strong>Invalid:</strong> {stats["invalid"]} | <strong>Error rate:</strong> {stats["error_rate"]:.4f}</p>
    </section>

    <section class="card">
      <h2>Issues</h2>
      <table>
        <thead>
          <tr>
            <th>Rule</th>
            <th>Severity</th>
            <th>Field</th>
            <th>Record</th>
            <th>Message</th>
            <th>Context</th>
          </tr>
        </thead>
        <tbody>
          {_render_issue_rows(all_rows)}
        </tbody>
      </table>
    </section>

    <section class="card">
      <h2>Summary By Rule</h2>
      <table>
        <thead><tr><th>Rule</th><th>Count</th></tr></thead>
        <tbody>{by_rule_rows}</tbody>
      </table>
    </section>

    <section class="card">
      <h2>Summary By Field</h2>
      <table>
        <thead><tr><th>Field</th><th>Count</th></tr></thead>
        <tbody>{by_field_rows}</tbody>
      </table>
    </section>
  </div>
</body>
</html>
"""

        if path is not None:
            target = Path(path)
            target.write_text(html, encoding="utf-8")

        return html

    @staticmethod
    def _issue_to_dict(issue: ValidationIssue) -> dict[str, Any]:
        return {
            "rule": issue.rule,
            "severity": issue.severity.value,
            "message": issue.message,
            "field": issue.field,
            "record_index": issue.record_index,
            "context": dict(issue.context),
        }
