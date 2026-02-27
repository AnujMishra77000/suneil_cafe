#!/usr/bin/env python3
"""Evaluate Locust CSV stats against SLA thresholds.

Exit codes:
  0: SLA pass
  2: SLA fail
  3: Invalid/missing input
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _to_float(value: Any, default: float = 0.0) -> float:
    raw = str(value or "").strip().replace(",", "")
    if not raw:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    return int(round(_to_float(value, float(default))))


def _first_numeric(row: Dict[str, Any], keys: List[str], default: float = 0.0) -> float:
    for key in keys:
        if key in row:
            return _to_float(row.get(key), default)
    return default


def _extract_metrics(row: Dict[str, Any]) -> Dict[str, float]:
    request_count = _to_int(row.get("Request Count"), 0)
    failure_count = _to_int(row.get("Failure Count"), 0)
    avg_ms = _first_numeric(row, ["Average Response Time", "Avg Response Time"], 0.0)
    p95_ms = _first_numeric(row, ["95%", "95%ile", "95th percentile"], 0.0)
    p99_ms = _first_numeric(row, ["99%", "99%ile", "99th percentile"], 0.0)
    rps = _first_numeric(row, ["Requests/s", "Current RPS"], 0.0)
    error_rate = (failure_count / request_count) if request_count > 0 else 1.0

    return {
        "request_count": request_count,
        "failure_count": failure_count,
        "error_rate": error_rate,
        "avg_ms": avg_ms,
        "p95_ms": p95_ms,
        "p99_ms": p99_ms,
        "rps": rps,
    }


def _read_stats_rows(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            if not row:
                continue
            if not any((str(v or "").strip() for v in row.values())):
                continue
            rows.append(row)
    return rows


def _resolve_aggregate_row(rows: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    for row in rows:
        name = str(row.get("Name") or "").strip().lower()
        if name in {"aggregated", "aggregate"}:
            return row
    return None


def _resolve_named_row(rows: List[Dict[str, Any]], endpoint_name: str) -> Dict[str, Any] | None:
    candidates = []
    for row in rows:
        name = str(row.get("Name") or "").strip()
        if name != endpoint_name:
            continue
        metrics = _extract_metrics(row)
        candidates.append((metrics["request_count"], row))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _as_pct(value: float) -> float:
    return round(value * 100.0, 4)


def _check(condition: bool, key: str, description: str, actual: Any, threshold: Any) -> Dict[str, Any]:
    return {
        "key": key,
        "passed": bool(condition),
        "description": description,
        "actual": actual,
        "threshold": threshold,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check Locust stats against SLA thresholds")
    parser.add_argument("--stats-csv", required=True, help="Path to locust_stats.csv")
    parser.add_argument("--summary-out", default="", help="Optional JSON output path")
    parser.add_argument("--max-error-rate", type=float, default=0.01, help="Max allowed aggregate error ratio")
    parser.add_argument("--max-p95-ms", type=float, default=800.0, help="Max allowed aggregate p95 response time")
    parser.add_argument("--max-p99-ms", type=float, default=1500.0, help="Max allowed aggregate p99 response time")
    parser.add_argument("--max-avg-ms", type=float, default=500.0, help="Max allowed aggregate avg response time")
    parser.add_argument("--min-rps", type=float, default=1.0, help="Min required aggregate requests/sec")
    parser.add_argument("--min-requests", type=int, default=1000, help="Min required aggregate request count")
    parser.add_argument(
        "--critical-endpoints",
        default="/api/products/category-cards/,/api/products/categories/[id]/products/,/api/cart/view/,/api/cart/add/,/api/cart/place/",
        help="Comma-separated endpoint names as used in Locust 'name=' labels",
    )
    parser.add_argument(
        "--endpoint-max-p95-ms",
        type=float,
        default=1200.0,
        help="Max allowed p95 for each critical endpoint",
    )
    parser.add_argument(
        "--allow-missing-critical",
        action="store_true",
        help="Do not fail if a critical endpoint has zero traffic/missing row",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    stats_path = Path(args.stats_csv)
    if not stats_path.exists():
        print(f"[SLA] stats file not found: {stats_path}")
        return 3

    rows = _read_stats_rows(stats_path)
    if not rows:
        print("[SLA] locust stats CSV is empty")
        return 3

    aggregate_row = _resolve_aggregate_row(rows)
    if not aggregate_row:
        print("[SLA] 'Aggregated' row not found in locust stats")
        return 3

    aggregate = _extract_metrics(aggregate_row)

    checks: List[Dict[str, Any]] = [
        _check(
            aggregate["request_count"] >= args.min_requests,
            "min_requests",
            "Aggregate request count must be high enough for reliable result",
            aggregate["request_count"],
            f">= {args.min_requests}",
        ),
        _check(
            aggregate["error_rate"] <= args.max_error_rate,
            "max_error_rate",
            "Aggregate failure ratio within limit",
            aggregate["error_rate"],
            f"<= {args.max_error_rate}",
        ),
        _check(
            aggregate["avg_ms"] <= args.max_avg_ms,
            "max_avg_ms",
            "Aggregate average response time within limit",
            aggregate["avg_ms"],
            f"<= {args.max_avg_ms}",
        ),
        _check(
            aggregate["p95_ms"] <= args.max_p95_ms,
            "max_p95_ms",
            "Aggregate p95 response time within limit",
            aggregate["p95_ms"],
            f"<= {args.max_p95_ms}",
        ),
        _check(
            aggregate["p99_ms"] <= args.max_p99_ms,
            "max_p99_ms",
            "Aggregate p99 response time within limit",
            aggregate["p99_ms"],
            f"<= {args.max_p99_ms}",
        ),
        _check(
            aggregate["rps"] >= args.min_rps,
            "min_rps",
            "Aggregate throughput meets minimum",
            aggregate["rps"],
            f">= {args.min_rps}",
        ),
    ]

    critical_endpoints = [item.strip() for item in str(args.critical_endpoints or "").split(",") if item.strip()]
    endpoint_checks: List[Dict[str, Any]] = []
    endpoint_summaries: List[Dict[str, Any]] = []

    for endpoint in critical_endpoints:
        row = _resolve_named_row(rows, endpoint)
        if row is None:
            endpoint_checks.append(
                _check(
                    args.allow_missing_critical,
                    f"critical:{endpoint}",
                    "Critical endpoint should be present in stats",
                    "missing",
                    "present",
                )
            )
            endpoint_summaries.append(
                {
                    "endpoint": endpoint,
                    "present": False,
                    "request_count": 0,
                    "failure_count": 0,
                    "error_rate": 0.0,
                    "p95_ms": 0.0,
                    "p99_ms": 0.0,
                }
            )
            continue

        metrics = _extract_metrics(row)
        endpoint_summaries.append(
            {
                "endpoint": endpoint,
                "present": True,
                **metrics,
            }
        )
        endpoint_checks.append(
            _check(
                metrics["p95_ms"] <= args.endpoint_max_p95_ms,
                f"critical_p95:{endpoint}",
                "Critical endpoint p95 within limit",
                metrics["p95_ms"],
                f"<= {args.endpoint_max_p95_ms}",
            )
        )

    all_checks = checks + endpoint_checks
    overall_pass = all(item["passed"] for item in all_checks)

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "stats_csv": str(stats_path),
        "overall_pass": overall_pass,
        "aggregate": {
            **aggregate,
            "error_rate_pct": _as_pct(aggregate["error_rate"]),
        },
        "checks": all_checks,
        "critical_endpoints": endpoint_summaries,
        "thresholds": {
            "max_error_rate": args.max_error_rate,
            "max_avg_ms": args.max_avg_ms,
            "max_p95_ms": args.max_p95_ms,
            "max_p99_ms": args.max_p99_ms,
            "min_rps": args.min_rps,
            "min_requests": args.min_requests,
            "endpoint_max_p95_ms": args.endpoint_max_p95_ms,
            "allow_missing_critical": bool(args.allow_missing_critical),
        },
    }

    print("[SLA] Aggregate metrics")
    print(
        "[SLA] requests={request_count} failures={failure_count} "
        "error_rate={error_rate:.4f} ({error_rate_pct:.2f}%) avg={avg_ms:.2f}ms "
        "p95={p95_ms:.2f}ms p99={p99_ms:.2f}ms rps={rps:.2f}".format(
            **summary["aggregate"]
        )
    )

    print("[SLA] Checks")
    for item in all_checks:
        status = "PASS" if item["passed"] else "FAIL"
        print(
            f"[SLA] {status:<4} {item['key']} | actual={item['actual']} "
            f"threshold={item['threshold']}"
        )

    if args.summary_out:
        out_path = Path(args.summary_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"[SLA] Summary JSON written: {out_path}")

    print(f"[SLA] OVERALL: {'PASS' if overall_pass else 'FAIL'}")
    return 0 if overall_pass else 2


if __name__ == "__main__":
    sys.exit(main())
