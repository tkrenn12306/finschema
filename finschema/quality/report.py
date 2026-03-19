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


_SEVERITY_RANK: dict[Severity, int] = {
    Severity.INFO: 1,
    Severity.WARNING: 2,
    Severity.ERROR: 3,
}


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    rule: str
    severity: Severity
    message: str
    field: str | None = None
    record_index: int | None = None
    context: dict[str, Any] = dataclass_field(default_factory=dict)


class QualityReport:
    def __init__(
        self,
        issues: list[ValidationIssue],
        total_records: int,
        min_score: float = 0.95,
        total_checks: int | None = None,
        fail_on_severity: Severity | str = Severity.ERROR,
    ):
        self._issues = list(issues)
        self._total_records = max(0, total_records)
        self._min_score = min_score
        self._total_checks = max(total_checks or self._total_records or 1, 1)
        self._fail_on_severity = (
            fail_on_severity
            if isinstance(fail_on_severity, Severity)
            else Severity(str(fail_on_severity).upper())
        )

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
    def weighted_errors(self) -> float:
        return (
            float(len(self.errors)) + float(len(self.warnings)) * 0.5 + float(len(self.info)) * 0.1
        )

    @property
    def score(self) -> float:
        return max(0.0, 1.0 - (self.weighted_errors / float(self._total_checks)))

    def _is_failure_issue(self, issue: ValidationIssue) -> bool:
        return _SEVERITY_RANK[issue.severity] >= _SEVERITY_RANK[self._fail_on_severity]

    @property
    def passed(self) -> bool:
        if self.score < self._min_score:
            return False
        return not any(self._is_failure_issue(issue) for issue in self._issues)

    @property
    def stats(self) -> dict[str, float | int]:
        invalid = self._compute_invalid_record_count()
        valid = max(0, self._total_records - invalid)
        error_rate = float(invalid) / float(self._total_records) if self._total_records else 0.0
        return {
            "total_records": self._total_records,
            "valid_count": valid,
            "invalid_count": invalid,
            "error_rate": error_rate,
            # Backward compatibility aliases
            "valid": valid,
            "invalid": invalid,
        }

    def _compute_invalid_record_count(self) -> int:
        if self._total_records == 0:
            return 0

        failing_issues = [issue for issue in self._issues if self._is_failure_issue(issue)]
        indexed_failures = {
            issue.record_index for issue in failing_issues if issue.record_index is not None
        }
        has_global_failure = any(issue.record_index is None for issue in failing_issues)

        if self._total_records == 1 and (indexed_failures or has_global_failure):
            return 1

        if indexed_failures:
            return len(indexed_failures)

        if has_global_failure:
            return self._total_records

        return 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "stats": self.stats,
            "total_checks": self._total_checks,
            "weighted_errors": self.weighted_errors,
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

    def to_html(
        self,
        path: str | Path | None = None,
        *,
        records: list[dict[str, Any]] | None = None,
    ) -> str:
        payload = self.to_dict()
        stats = payload["stats"]
        score = payload["score"]
        passed = payload["passed"]
        all_rows: list[dict[str, Any]] = [
            *payload["errors"],
            *payload["warnings"],
            *payload["info"],
        ]

        by_rule_rows = "".join(
            f"<tr><td>{escape(str(rule))}</td><td>{len(issues)}</td></tr>"
            for rule, issues in payload["by_rule"].items()
        )
        if not by_rule_rows:
            by_rule_rows = "<tr><td colspan='2'>None</td></tr>"

        by_field_rows = "".join(
            f"<tr><td>{escape(str(field))}</td><td>{len(issues)}</td></tr>"
            for field, issues in payload["by_field"].items()
        )
        if not by_field_rows:
            by_field_rows = "<tr><td colspan='2'>None</td></tr>"

        issue_rows = self._render_issue_rows(all_rows)
        invalid_rows = self._invalid_rows(records)

        score_percent = score * 100.0
        gauge_color = "#1f7a45"
        if score_percent < 80:
            gauge_color = "#a1302a"
        elif score_percent < 95:
            gauge_color = "#b8860b"

        script_payload = {
            "issues": all_rows,
            "invalid_rows": invalid_rows,
            "score": score,
            "stats": stats,
        }
        script_json = self._json_for_script(script_payload)

        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>finschema Quality Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f4ef;
      --card: #ffffff;
      --text: #1f2529;
      --muted: #667078;
      --border: #d6d9d1;
      --accent: #0f5c82;
      --ok: #1f7a45;
      --warn: #b8860b;
      --bad: #a1302a;
    }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    .container {{
      max-width: 1200px;
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
      color: {("var(--ok)" if passed else "var(--bad)")};
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
      margin-top: 12px;
    }}
    .metric {{
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
      background: #fafbfc;
    }}
    .metric .label {{
      color: var(--muted);
      font-size: 0.84rem;
    }}
    .metric .value {{
      margin-top: 6px;
      font-size: 1.2rem;
      font-weight: 650;
    }}
    .gauge {{
      width: 100%;
      height: 16px;
      border-radius: 999px;
      background: #e9ece8;
      overflow: hidden;
      border: 1px solid var(--border);
      margin-top: 10px;
    }}
    .gauge-fill {{
      height: 100%;
      width: {score_percent:.2f}%;
      background: {gauge_color};
      transition: width 0.25s ease;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin: 10px 0 12px;
    }}
    .toolbar input, .toolbar select, .toolbar button {{
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 7px 9px;
      font: inherit;
      background: #fff;
      color: var(--text);
    }}
    .toolbar button {{
      background: #f4f8fb;
      cursor: pointer;
    }}
    .toolbar button:hover {{
      border-color: var(--accent);
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
      background: #eef2ef;
      font-weight: 600;
      cursor: pointer;
      user-select: none;
    }}
    th.sortable::after {{
      content: " \\2195";
      color: var(--muted);
      font-size: 0.8rem;
    }}
    code {{
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .placeholder {{
      border: 1px dashed var(--border);
      border-radius: 8px;
      padding: 12px;
      color: var(--muted);
      background: #fafbfc;
    }}
  </style>
</head>
<body>
  <div class="container">
    <section class="card">
      <h1>finschema Quality Report</h1>
      <p class="muted">Standalone report generated from QualityReport.</p>
      <p><strong>Status:</strong> <span class="status">{"PASS" if passed else "FAIL"}</span></p>
      <div class="gauge" aria-label="Quality score gauge">
        <div class="gauge-fill"></div>
      </div>
      <div class="summary-grid">
        <div class="metric"><div class="label">Quality Score</div><div class="value">{score_percent:.2f}%</div></div>
        <div class="metric"><div class="label">Total Records</div><div class="value">{stats["total_records"]}</div></div>
        <div class="metric"><div class="label">Invalid Records</div><div class="value">{stats["invalid_count"]}</div></div>
        <div class="metric"><div class="label">Error Rate</div><div class="value">{stats["error_rate"]:.4f}</div></div>
        <div class="metric"><div class="label">Errors</div><div class="value">{len(payload["errors"])}</div></div>
        <div class="metric"><div class="label">Warnings</div><div class="value">{len(payload["warnings"])}</div></div>
      </div>
    </section>

    <section class="card">
      <h2>Issues</h2>
      <div class="toolbar">
        <label for="severity-filter">Severity</label>
        <select id="severity-filter">
          <option value="">All</option>
          <option value="ERROR">ERROR</option>
          <option value="WARNING">WARNING</option>
          <option value="INFO">INFO</option>
        </select>
        <label for="text-filter">Filter</label>
        <input id="text-filter" type="text" placeholder="rule, field, message..." />
        <button id="reset-filter" type="button">Reset</button>
        <button id="export-invalid" type="button">Export Invalid Rows CSV</button>
      </div>
      <table>
        <thead>
          <tr>
            <th class="sortable" data-sort="rule">Rule</th>
            <th class="sortable" data-sort="severity">Severity</th>
            <th class="sortable" data-sort="field">Field</th>
            <th class="sortable" data-sort="record_index">Record</th>
            <th class="sortable" data-sort="message">Message</th>
            <th class="sortable" data-sort="context">Context</th>
          </tr>
        </thead>
        <tbody id="issues-body">{issue_rows}</tbody>
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

    <section class="card">
      <h2>Trend Placeholder</h2>
      <div id="trend-placeholder" class="placeholder">
        Historical trend integration point for CI quality history.
      </div>
    </section>
  </div>
  <script id="finschema-data" type="application/json">{script_json}</script>
  <script>
    (function() {{
      const root = document.getElementById("finschema-data");
      if (!root) return;
      const data = JSON.parse(root.textContent || "{{}}");
      const issues = Array.isArray(data.issues) ? data.issues.slice() : [];
      const invalidRows = Array.isArray(data.invalid_rows) ? data.invalid_rows : [];
      const tbody = document.getElementById("issues-body");
      const severityFilter = document.getElementById("severity-filter");
      const textFilter = document.getElementById("text-filter");
      const resetButton = document.getElementById("reset-filter");
      const exportButton = document.getElementById("export-invalid");
      let sortKey = "severity";
      let sortAsc = false;

      const severityRank = {{ "ERROR": 3, "WARNING": 2, "INFO": 1 }};

      function asText(value) {{
        if (value === null || value === undefined) return "";
        if (typeof value === "object") return JSON.stringify(value);
        return String(value);
      }}

      function escapeHtml(text) {{
        return String(text)
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#39;");
      }}

      function rowHtml(row) {{
        const ctx = JSON.stringify(row.context || {{}});
        return "<tr>"
          + "<td>" + escapeHtml(asText(row.rule)) + "</td>"
          + "<td>" + escapeHtml(asText(row.severity)) + "</td>"
          + "<td>" + escapeHtml(asText(row.field)) + "</td>"
          + "<td>" + escapeHtml(asText(row.record_index)) + "</td>"
          + "<td>" + escapeHtml(asText(row.message)) + "</td>"
          + "<td><code>" + escapeHtml(ctx) + "</code></td>"
          + "</tr>";
      }}

      function compareRows(a, b) {{
        const av = a[sortKey];
        const bv = b[sortKey];
        if (sortKey === "severity") {{
          const diff = (severityRank[asText(av)] || 0) - (severityRank[asText(bv)] || 0);
          return sortAsc ? diff : -diff;
        }}
        const astr = asText(av).toLowerCase();
        const bstr = asText(bv).toLowerCase();
        if (astr < bstr) return sortAsc ? -1 : 1;
        if (astr > bstr) return sortAsc ? 1 : -1;
        return 0;
      }}

      function filteredRows() {{
        const selectedSeverity = (severityFilter && severityFilter.value) || "";
        const query = ((textFilter && textFilter.value) || "").trim().toLowerCase();
        let rows = issues.slice();
        if (selectedSeverity) {{
          rows = rows.filter((row) => asText(row.severity) === selectedSeverity);
        }}
        if (query) {{
          rows = rows.filter((row) => {{
            const hay = [
              row.rule,
              row.severity,
              row.field,
              row.message,
              row.record_index,
              JSON.stringify(row.context || {{}})
            ].map(asText).join(" ").toLowerCase();
            return hay.includes(query);
          }});
        }}
        rows.sort(compareRows);
        return rows;
      }}

      function render() {{
        if (!tbody) return;
        const rows = filteredRows();
        if (rows.length === 0) {{
          tbody.innerHTML = "<tr><td colspan='6'>None</td></tr>";
          return;
        }}
        tbody.innerHTML = rows.map(rowHtml).join("");
      }}

      function exportInvalidRows() {{
        if (!invalidRows.length) {{
          alert("No invalid rows available in this report.");
          return;
        }}
        const keys = Array.from(new Set(invalidRows.flatMap((row) => Object.keys(row || {{}}))));
        const lines = [keys.join(",")];
        for (const row of invalidRows) {{
          const cells = keys.map((key) => {{
            const raw = row[key];
            const txt = raw === null || raw === undefined ? "" : String(raw);
            const escaped = txt.replaceAll('"', '""');
            return '"' + escaped + '"';
          }});
          lines.push(cells.join(","));
        }}
        const blob = new Blob([lines.join("\\n")], {{ type: "text/csv;charset=utf-8" }});
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "invalid_rows.csv";
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 0);
      }}

      document.querySelectorAll("th.sortable").forEach((header) => {{
        header.addEventListener("click", () => {{
          const key = header.getAttribute("data-sort");
          if (!key) return;
          if (sortKey === key) {{
            sortAsc = !sortAsc;
          }} else {{
            sortKey = key;
            sortAsc = true;
          }}
          render();
        }});
      }});

      if (severityFilter) severityFilter.addEventListener("change", render);
      if (textFilter) textFilter.addEventListener("input", render);
      if (resetButton) {{
        resetButton.addEventListener("click", () => {{
          if (severityFilter) severityFilter.value = "";
          if (textFilter) textFilter.value = "";
          sortKey = "severity";
          sortAsc = false;
          render();
        }});
      }}
      if (exportButton) exportButton.addEventListener("click", exportInvalidRows);
      render();
    }})();
  </script>
</body>
</html>
"""

        if path is not None:
            target = Path(path)
            target.write_text(html, encoding="utf-8")

        return html

    def _repr_html_(self) -> str:
        """Rich notebook representation."""
        return self.to_html()

    def _invalid_rows(self, records: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if records is None:
            return []

        invalid_indices = sorted(
            {
                issue.record_index
                for issue in self._issues
                if issue.record_index is not None and self._is_failure_issue(issue)
            }
        )
        result: list[dict[str, Any]] = []
        for index in invalid_indices:
            if 0 <= index < len(records):
                result.append(dict(records[index]))
        return result

    @staticmethod
    def _json_for_script(payload: dict[str, Any]) -> str:
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return rendered.replace("</", "<\\/")

    @staticmethod
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
