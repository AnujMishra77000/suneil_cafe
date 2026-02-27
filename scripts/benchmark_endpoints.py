#!/usr/bin/env python3
"""Simple HTTP benchmark for Thathwamasi endpoints.

Usage:
  python scripts/benchmark_endpoints.py --base http://127.0.0.1:8000 --phone 9999999999 --category-id 1
"""

import argparse
import json
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request


def timed_request(method: str, url: str, payload=None, timeout=20):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        status = exc.code
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return status, elapsed_ms, body


def run_series(name, method, url, payload, n):
    results = []
    statuses = []
    for _ in range(n):
        status, ms, _ = timed_request(method, url, payload)
        results.append(ms)
        statuses.append(status)
    return {
        "name": name,
        "count": n,
        "status_set": sorted(set(statuses)),
        "min_ms": round(min(results), 2),
        "p50_ms": round(statistics.median(results), 2),
        "p95_ms": round(sorted(results)[max(0, int(n * 0.95) - 1)], 2),
        "max_ms": round(max(results), 2),
        "avg_ms": round(sum(results) / len(results), 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000", help="Base URL")
    ap.add_argument("--phone", required=True, help="Customer phone for cart endpoints")
    ap.add_argument("--category-id", type=int, required=True, help="Existing category id")
    ap.add_argument("--product-id", type=int, required=False, help="Existing product id (for add-to-cart)")
    ap.add_argument("--loops", type=int, default=12, help="Requests per endpoint")
    args = ap.parse_args()

    base = args.base.rstrip("/")
    loops = max(5, args.loops)

    endpoints = [
        ("category_cards_snacks", "GET", f"{base}/api/products/category-cards/?section=snacks", None),
        ("products_by_category", "GET", f"{base}/api/products/categories/{args.category_id}/products/", None),
        ("search_cake", "GET", f"{base}/api/products/search/?q=cake", None),
        ("cart_view", "GET", f"{base}/api/cart/view/?phone={urllib.parse.quote(args.phone)}", None),
    ]

    if args.product_id:
        endpoints.append((
            "cart_add",
            "POST",
            f"{base}/api/cart/add/",
            {
                "phone": args.phone,
                "customer_name": "Bench User",
                "whatsapp_no": args.phone,
                "product_id": args.product_id,
                "quantity": 1,
            },
        ))

    print("\\n=== Cold Requests (first-hit) ===")
    for name, method, url, payload in endpoints:
        status, ms, body = timed_request(method, url, payload)
        print(f"{name:22} status={status} cold_ms={ms:.2f}")
        if status >= 400:
            preview = body[:160].decode("utf-8", "ignore").replace("\\n", " ")
            print(f"  error_preview: {preview}")

    print("\\n=== Warm Requests (cached/steady) ===")
    summaries = []
    for name, method, url, payload in endpoints:
        summaries.append(run_series(name, method, url, payload, loops))

    for s in summaries:
        print(
            f"{s['name']:22} statuses={s['status_set']} "
            f"p50={s['p50_ms']}ms p95={s['p95_ms']}ms avg={s['avg_ms']}ms "
            f"min={s['min_ms']}ms max={s['max_ms']}ms"
        )


if __name__ == "__main__":
    main()
