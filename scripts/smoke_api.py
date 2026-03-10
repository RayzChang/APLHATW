"""
Quick API smoke test for AlphaTW.

Usage:
  python scripts/smoke_api.py
  python scripts/smoke_api.py http://127.0.0.1:8000
"""

from __future__ import annotations

import sys
from typing import List, Tuple

import requests


def run(base_url: str) -> int:
    endpoints: List[Tuple[str, str]] = [
        ("GET", "/api/health"),
        ("GET", "/api/market/status"),
        ("GET", "/api/market/index"),
        ("GET", "/api/trading/scan/status"),
        ("GET", "/api/trading/portfolio"),
        ("GET", "/api/stock/quote/2330"),
        ("GET", "/api/analysis/symbol/2330"),
    ]

    failed = 0
    print(f"[smoke] base_url={base_url}")
    for method, path in endpoints:
        url = f"{base_url}{path}"
        try:
            resp = requests.request(method, url, timeout=20)
            ok = 200 <= resp.status_code < 300
            mark = "PASS" if ok else "FAIL"
            print(f"[{mark}] {method} {path} -> {resp.status_code}")
            if not ok:
                failed += 1
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {method} {path} -> {exc}")

    if failed:
        print(f"[smoke] completed with {failed} failure(s).")
        return 1

    print("[smoke] all checks passed.")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    raise SystemExit(run(target.rstrip("/")))
