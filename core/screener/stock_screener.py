"""
台股選股器 — 技術指標篩選

支援：上市、上櫃、台指期
策略：KD、RSI、MACD、布林、MA20、量能
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from loguru import logger

from config.settings import SCREENER_STRATEGIES
from core.data.tw_data_fetcher import TWDataFetcher
from core.analysis.indicators import add_all_indicators, calc_buy_sell_score
from core.analysis.patterns import (
    detect_double_bottom, detect_double_top,
    detect_inverse_head_shoulders, detect_head_shoulders,
    detect_triangle, detect_breakout, detect_fibonacci,
)


@dataclass
class ScreenerResult:
    symbol: str
    name: str
    close: float
    change_pct: float
    signal: str  # BUY | SELL | FILTER
    strategy_id: str
    strategy_name: str


_PATTERN_STRATEGIES = {
    "double_bottom", "double_top",
    "head_shoulders_bottom", "head_shoulders_top",
    "triangle_bull", "breakout_up", "breakdown", "fib_support",
}


def _check_strategy(row: pd.Series, strategy_id: str, df: pd.DataFrame = None) -> bool:
    """
    檢查單一策略條件。
    技術指標策略只需要 row（最後一根 K 線的 Series）。
    K 線型態策略需要完整 df（若 df 為 None 則跳過）。
    """
    # ── 技術指標策略 ──────────────────────────────
    if strategy_id == "list_all":
        return True
    if strategy_id == "buy_score":
        return calc_buy_sell_score(row) >= 1
    if strategy_id == "sell_score":
        return calc_buy_sell_score(row) <= -1
    if strategy_id == "volume_surge":
        return row.get("vol_ratio", 0) >= 1.5
    if strategy_id == "oversold":
        rsi = row.get("rsi")
        bb  = row.get("bb_pct")
        return (pd.notna(rsi) and rsi < 30) or (pd.notna(bb) and bb < 0)
    if strategy_id == "kd_golden":
        k, d = row.get("kd_k"), row.get("kd_d")
        return pd.notna(k) and pd.notna(d) and k > d
    if strategy_id == "kd_death":
        k, d = row.get("kd_k"), row.get("kd_d")
        return pd.notna(k) and pd.notna(d) and k < d
    if strategy_id == "rsi_oversold":
        return pd.notna(row.get("rsi")) and row["rsi"] < 30
    if strategy_id == "rsi_overbought":
        return pd.notna(row.get("rsi")) and row["rsi"] > 70
    if strategy_id == "macd_bull":
        return pd.notna(row.get("macd_hist")) and row["macd_hist"] > 0
    if strategy_id == "macd_bear":
        return pd.notna(row.get("macd_hist")) and row["macd_hist"] < 0
    if strategy_id == "ma20_above":
        return pd.notna(row.get("ma20")) and row["close"] > row["ma20"]
    if strategy_id == "ma20_below":
        return pd.notna(row.get("ma20")) and row["close"] < row["ma20"]
    if strategy_id == "bb_upper":
        return pd.notna(row.get("bb_pct")) and row["bb_pct"] > 1.0
    if strategy_id == "bb_lower":
        return pd.notna(row.get("bb_pct")) and row["bb_pct"] < 0.0

    # ── K 線型態策略（需要完整 df）────────────────
    if strategy_id in _PATTERN_STRATEGIES:
        if df is None or len(df) < 30:
            return False
        try:
            if strategy_id == "double_bottom":
                r = detect_double_bottom(df)
                return r is not None and r.completion >= 50
            if strategy_id == "double_top":
                r = detect_double_top(df)
                return r is not None and r.completion >= 50
            if strategy_id == "head_shoulders_bottom":
                r = detect_inverse_head_shoulders(df)
                return r is not None and r.completion >= 70
            if strategy_id == "head_shoulders_top":
                r = detect_head_shoulders(df)
                return r is not None and r.completion >= 70
            if strategy_id == "triangle_bull":
                r = detect_triangle(df)
                return r is not None and r.signal == "bullish" and r.completion >= 50
            if strategy_id == "breakout_up":
                r = detect_breakout(df, lookback=20)
                return r is not None and r.pattern_id == "breakout_up"
            if strategy_id == "breakdown":
                r = detect_breakout(df, lookback=20)
                return r is not None and r.pattern_id == "breakdown"
            if strategy_id == "fib_support":
                fib = detect_fibonacci(df)
                return bool(fib.get("near_support"))
        except Exception:
            return False

    return False


def run_screener(
    symbols: list[str],
    strategies: list[str],
    fetcher: Optional[TWDataFetcher] = None,
) -> list[ScreenerResult]:
    """
    執行選股
    
    Args:
        symbols: 股票/期貨代碼列表
        strategies: 策略 ID 列表，如 ["buy_score", "oversold"]
    """
    fetcher = fetcher or TWDataFetcher()
    end = datetime.now()
    start = (end - timedelta(days=60)).strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    
    results: list[ScreenerResult] = []
    strategy_map = {s["id"]: s for s in SCREENER_STRATEGIES}
    
    for symbol in symbols:
        try:
            df = fetcher.fetch_klines(symbol, start, end_str)
            if df.empty or len(df) < 30:
                continue
            df = add_all_indicators(df)
            row = df.iloc[-1]
            prev = df.iloc[-2] if len(df) >= 2 else row
            change_pct = ((row["close"] - prev["close"]) / prev["close"] * 100) if prev["close"] else 0
            name = fetcher.get_symbol_name(symbol)
            
            score = calc_buy_sell_score(row)
            for sid in strategies:
                if sid not in strategy_map:
                    continue
                s = strategy_map[sid]
                if _check_strategy(row, sid, df=df):
                    if sid == "list_all":
                        signal = "BUY" if score >= 1 else "SELL" if score <= -1 else "觀望"
                    else:
                        signal = "BUY" if s["type"] == "buy" else "SELL" if s["type"] == "sell" else "FILTER"
                    results.append(ScreenerResult(
                        symbol=symbol,
                        name=name,
                        close=float(row["close"]),
                        change_pct=round(change_pct, 2),
                        signal=signal,
                        strategy_id=sid,
                        strategy_name=s["name"],
                    ))
        except Exception as e:
            logger.warning(f"選股 {symbol} 失敗: {e}")
    
    return results
