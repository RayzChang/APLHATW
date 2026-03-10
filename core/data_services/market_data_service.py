from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from loguru import logger

from core.data.tw_data_fetcher import TWDataFetcher


class MarketDataService:
    """Unified market data access wrapper around TWDataFetcher."""

    def __init__(self, fetcher: TWDataFetcher):
        self.fetcher = fetcher

    def get_quote(self, symbol: str) -> dict[str, Any]:
        return self.fetcher.fetch_realtime_quote(symbol)

    def get_klines(self, symbol: str, start: str | None = None, end: str | None = None):
        return self.fetcher.fetch_klines(symbol, start, end)

    def get_symbol_name(self, symbol: str) -> str:
        return self.fetcher.get_symbol_name(symbol)

    def get_stock_list(self, market_type: str = "all"):
        return self.fetcher.get_stock_list(market_type)

    def get_all_stock_ids_with_market(self) -> dict[str, str]:
        return self.fetcher.get_all_stock_ids_with_market()

    def get_market_snapshot(self) -> dict[str, Any]:
        """Best-effort TAIEX snapshot via TWSE MIS; safe fallback when unavailable."""
        tz_tw = timezone(timedelta(hours=8))
        now = datetime.now(tz_tw)
        is_open = now.weekday() < 5 and (9, 0) <= (now.hour, now.minute) <= (13, 30)

        result: dict[str, Any] = {
            "market_trend": "UNKNOWN",
            "market_risk_level": "MEDIUM",
            "market_index": None,
            "market_change_pct": None,
            "is_market_open": is_open,
            "source": "unavailable",
        }

        try:
            url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw&json=1&delay=0"
            headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://mis.twse.com.tw/"}
            resp = requests.get(url, headers=headers, timeout=5)
            if not resp.ok:
                return result
            data = resp.json()
            rows = data.get("msgArray", [])
            if not rows:
                return result
            row = rows[0]
            z_val = row.get("z", "-")
            y_val = row.get("y", "0")
            prev_close = float(y_val or 0)
            index_value = float(z_val) if z_val not in ("-", "", None) else prev_close
            change_pct = round(((index_value - prev_close) / prev_close) * 100, 2) if prev_close else 0.0

            trend = "SIDEWAYS"
            if change_pct > 0.8:
                trend = "BULLISH"
            elif change_pct < -0.8:
                trend = "BEARISH"

            risk = "LOW"
            if abs(change_pct) > 1.8:
                risk = "HIGH"
            elif abs(change_pct) > 0.8:
                risk = "MEDIUM"

            result.update(
                {
                    "market_index": index_value,
                    "market_change_pct": change_pct,
                    "market_trend": trend,
                    "market_risk_level": risk,
                    "source": "twse",
                }
            )
        except Exception as exc:
            logger.debug(f"MarketDataService.get_market_snapshot failed: {exc}")

        return result

