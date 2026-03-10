from __future__ import annotations

from typing import Any


def passes_quote_filters(
    price: float,
    volume: float,
    change_pct: float,
    min_price: float = 10.0,
    max_price: float = 3000.0,
    min_volume: float = 500_000.0,
    limit_up_threshold: float = 9.5,
) -> bool:
    if price < min_price or price > max_price:
        return False
    if volume < min_volume:
        return False
    if abs(change_pct) >= limit_up_threshold:
        return False
    return True


def passes_indicator_filters(row: Any) -> bool:
    rsi = row.get("rsi")
    ma20 = row.get("ma20")
    close = row.get("close")
    if rsi is None or ma20 is None or close is None:
        return False
    return 25 < float(rsi) < 75 and float(close) > float(ma20)


def passes_candidate_threshold(
    score: int,
    close: float,
    volume: float,
    min_score: int = 3,
    min_price: float = 10.0,
    min_volume: float = 500_000.0,
) -> bool:
    return score >= min_score and close >= min_price and volume >= min_volume

