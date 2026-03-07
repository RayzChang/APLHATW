"""
策略回測 — 近 6 個月歷史 K 線模擬買賣

依策略條件產生買賣信號，計算總報酬、勝率、交易次數
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from loguru import logger

from core.data.tw_data_fetcher import TWDataFetcher
from core.analysis.indicators import add_all_indicators, calc_buy_sell_score
from core.screener.stock_screener import _check_strategy
from config.settings import SCREENER_STRATEGIES


@dataclass
class BacktestResult:
    symbol: str
    name: str
    close: float
    total_return: float
    win_rate: float
    trade_count: int


def _run_backtest_on_df(
    df: pd.DataFrame,
    strategy_id: str,
) -> tuple[float, float, int]:
    """
    在單一標的 DataFrame 上回測
    回傳: (總報酬, 勝率, 交易次數)
    """
    if df.empty or len(df) < 30:
        return 0.0, 0.0, 0
    strategy_map = {s["id"]: s for s in SCREENER_STRATEGIES}
    if strategy_id not in strategy_map:
        return 0.0, 0.0, 0
    s = strategy_map[strategy_id]
    signal_type = s["type"]
    if signal_type == "filter":
        return 0.0, 0.0, 0
    
    pos = 0
    entry_price = 0.0
    pnls: list[float] = []
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        if not _check_strategy(row, strategy_id):
            continue
        
        if signal_type == "buy":
            if pos == 0:
                pos = 1
                entry_price = row["close"]
            elif pos == -1:
                pnl = (entry_price - row["close"]) / entry_price
                pnls.append(pnl)
                pos = 1
                entry_price = row["close"]
        elif signal_type == "sell":
            if pos == 0:
                pos = -1
                entry_price = row["close"]
            elif pos == 1:
                pnl = (row["close"] - entry_price) / entry_price
                pnls.append(pnl)
                pos = -1
                entry_price = row["close"]
    
    if pos == 1:
        pnl = (df.iloc[-1]["close"] - entry_price) / entry_price
        pnls.append(pnl)
    elif pos == -1:
        pnl = (entry_price - df.iloc[-1]["close"]) / entry_price
        pnls.append(pnl)
    
    if not pnls:
        return 0.0, 0.0, 0
    total_return = (1 + sum(pnls)) - 1
    wins = sum(1 for p in pnls if p > 0)
    win_rate = wins / len(pnls) * 100
    return total_return, win_rate, len(pnls)


def run_backtest(
    symbols: list[str],
    strategy_id: str,
    months: int = 6,
    fetcher: Optional[TWDataFetcher] = None,
) -> list[BacktestResult]:
    """執行回測，返回按總報酬排序的結果"""
    fetcher = fetcher or TWDataFetcher()
    end = datetime.now()
    start = (end - timedelta(days=months * 30)).strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    
    results: list[BacktestResult] = []
    for symbol in symbols:
        try:
            df = fetcher.fetch_klines(symbol, start, end_str)
            if df.empty or len(df) < 30:
                continue
            df = add_all_indicators(df)
            total_return, win_rate, trade_count = _run_backtest_on_df(df, strategy_id)
            if trade_count == 0:
                continue
            name = fetcher.get_symbol_name(symbol)
            results.append(BacktestResult(
                symbol=symbol,
                name=name,
                close=float(df.iloc[-1]["close"]),
                total_return=round(total_return * 100, 2),
                win_rate=round(win_rate, 1),
                trade_count=trade_count,
            ))
        except Exception as e:
            logger.warning(f"回測 {symbol} 失敗: {e}")
    
    results.sort(key=lambda x: x.total_return, reverse=True)
    return results
