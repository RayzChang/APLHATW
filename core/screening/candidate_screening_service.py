from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from core.analysis.indicators import add_all_indicators, calc_buy_sell_score
from core.data.tw_data_fetcher import TWDataFetcher
from core.screening.indicator_filters import passes_candidate_threshold, passes_indicator_filters, passes_quote_filters


@dataclass
class CandidateSignal:
    symbol: str
    name: str
    score: int
    current_price: float
    change_pct: float
    volume: float
    indicators: dict[str, Any] = field(default_factory=dict)
    raw_row: Any = None


class CandidateScreeningService:
    """Phase 3 screening layer for candidate discovery and ranking."""

    def __init__(self, fetcher: TWDataFetcher):
        self.fetcher = fetcher

    def screen_symbols(self, stock_ids: list[str], batch_size: int = 20, top_n: int = 20) -> list[CandidateSignal]:
        candidates: list[CandidateSignal] = []

        for i in range(0, len(stock_ids), batch_size):
            batch = stock_ids[i:i + batch_size]
            quotes = self.fetcher.fetch_realtime_batch(batch)
            for sid, quote in quotes.items():
                try:
                    price = float(quote.get("price", 0) or 0)
                    volume = float(quote.get("volume", 0) or 0)
                    change_pct = float(quote.get("change_pct", 0) or 0)
                    if not passes_quote_filters(price, volume, change_pct):
                        continue

                    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
                    df = self.fetcher.fetch_klines(sid, start_date=start_date)
                    if len(df) < 30:
                        continue
                    df = add_all_indicators(df)
                    row = df.iloc[-1]
                    if not passes_indicator_filters(row):
                        continue

                    score = calc_buy_sell_score(row)
                    candidates.append(
                        CandidateSignal(
                            symbol=sid,
                            name=self.fetcher.get_symbol_name(sid),
                            score=score,
                            current_price=price,
                            change_pct=change_pct,
                            volume=volume,
                            indicators=self._extract_indicators(row),
                            raw_row=row,
                        )
                    )
                except Exception as exc:
                    logger.debug(f"Candidate screening failed for {sid}: {exc}")

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[:top_n]

    def rank_market_data(
        self,
        market_frames: dict[str, Any],
        symbol_map: dict[str, str],
        top_n: int = 30,
        min_score: int = 3,
    ) -> list[CandidateSignal]:
        candidates: list[CandidateSignal] = []

        for external_symbol, raw_df in market_frames.items():
            sid = symbol_map.get(external_symbol)
            if not sid:
                continue
            try:
                df = add_all_indicators(raw_df.copy())
                df = df.dropna(subset=["rsi", "macd_hist", "ma20"]).reset_index(drop=True)
                if df.empty:
                    continue
                row = df.iloc[-1]
                score = calc_buy_sell_score(row)
                close = float(row.get("close", 0) or 0)
                volume = float(row.get("volume", 0) or 0)
                if not passes_candidate_threshold(score, close, volume, min_score=min_score):
                    continue

                prev = df.iloc[-2] if len(df) >= 2 else row
                prev_close = float(prev.get("close", close) or close)
                change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0.0

                candidates.append(
                    CandidateSignal(
                        symbol=sid,
                        name=self.fetcher.get_symbol_name(sid),
                        score=score,
                        current_price=close,
                        change_pct=round(change_pct, 2),
                        volume=volume,
                        indicators=self._extract_indicators(row),
                        raw_row=row,
                    )
                )
            except Exception as exc:
                logger.debug(f"rank_market_data failed for {sid}: {exc}")

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[:top_n]

    @staticmethod
    def _extract_indicators(row: Any) -> dict[str, Any]:
        return {
            "rsi": float(row.get("rsi", 0) or 0),
            "kd_k": float(row.get("kd_k", 0) or 0),
            "kd_d": float(row.get("kd_d", 0) or 0),
            "macd": float(row.get("macd", 0) or 0),
            "macd_hist": float(row.get("macd_hist", 0) or 0),
            "ma5": float(row.get("ma5", 0) or 0),
            "ma20": float(row.get("ma20", 0) or 0),
            "ma60": float(row.get("ma60", 0) or 0),
            "bb_upper": float(row.get("bb_upper", 0) or 0),
            "bb_lower": float(row.get("bb_lower", 0) or 0),
            "atr": float(row.get("atr", 0) or 0),
            "volume": float(row.get("volume", 0) or 0),
            "close": float(row.get("close", 0) or 0),
            "high": float(row.get("high", 0) or 0),
            "low": float(row.get("low", 0) or 0),
        }
