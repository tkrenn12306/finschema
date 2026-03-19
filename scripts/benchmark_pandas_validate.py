#!/usr/bin/env python3
"""Reproducible benchmark for pandas DataFrame validation throughput."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any


def _build_frame(rows: int):
    import pandas as pd

    valid_isin = "US0378331005"
    data = {
        "trade_id": [f"T-{idx}" for idx in range(rows)],
        "isin": [valid_isin for _ in range(rows)],
        "side": ["BUY" for _ in range(rows)],
        "quantity": [100 for _ in range(rows)],
        "price": [178.52 for _ in range(rows)],
        "currency": ["USD" for _ in range(rows)],
        "trade_date": ["2026-03-19" for _ in range(rows)],
        "settlement_date": ["2026-03-20" for _ in range(rows)],
    }
    return pd.DataFrame(data)


def run_benchmark(rows: int, target_seconds: float | None) -> dict[str, Any]:
    try:
        import pandas  # noqa: F401
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "pandas is required. Install with: pip install finschema[pandas]"
        ) from exc

    import finschema.integrations.pandas  # noqa: F401

    frame = _build_frame(rows)

    start = time.perf_counter()
    report = frame.finschema.validate("Trade")
    elapsed = time.perf_counter() - start

    payload = {
        "rows": rows,
        "elapsed_seconds": elapsed,
        "rows_per_second": rows / elapsed if elapsed > 0 else float("inf"),
        "score": report.score,
        "passed": report.passed,
        "errors": len(report.errors),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
    }

    if target_seconds is not None and elapsed > target_seconds:
        payload["target_seconds"] = target_seconds
        payload["target_passed"] = False
    else:
        payload["target_passed"] = True

    return payload


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark finschema pandas DataFrame validation")
    parser.add_argument("--rows", type=int, default=1_000_000, help="Number of rows to validate")
    parser.add_argument(
        "--target-seconds",
        type=float,
        default=10.0,
        help="Optional target threshold in seconds (default: 10.0)",
    )
    parser.add_argument("--output-json", type=Path, default=None, help="Optional JSON output path")
    parser.add_argument(
        "--strict-target",
        action="store_true",
        help="Return exit code 1 when the configured target is missed",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    if args.rows <= 0:
        print("--rows must be > 0")
        return 2

    try:
        payload = run_benchmark(args.rows, args.target_seconds)
    except Exception as exc:
        print(f"Benchmark failed: {exc}")
        return 3

    print("finschema pandas benchmark")
    print(json.dumps(payload, indent=2, sort_keys=True))

    if args.output_json is not None:
        args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Wrote benchmark results to: {args.output_json}")

    if args.strict_target and not payload.get("target_passed", True):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
