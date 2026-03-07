"""
一週模擬交易測試 — 100 萬台幣

使用近 5 個交易日歷史資料，依選股策略模擬買賣，
輸出：初始資金、最終資金、總報酬、勝率、交易筆數
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datetime import datetime, timedelta
from loguru import logger

from config.settings import SIMULATION_INITIAL_BALANCE, DEFAULT_WATCHLIST
from core.data.tw_data_fetcher import TWDataFetcher
from core.analysis.indicators import add_all_indicators, calc_buy_sell_score
from database.db_manager import DatabaseManager


def run_weekly_sim(
    initial: float = 1_000_000,
    symbols: list[str] | None = None,
    days: int = 5,
) -> dict:
    """
    模擬一週（5 個交易日）
    - 每日依「適合買進」策略選股
    - 用 10% 資金買入符合條件的標的
    - 隔日收盤賣出，計算損益
    """
    symbols = symbols or DEFAULT_WATCHLIST[:50]
    fetcher = TWDataFetcher()
    balance = initial
    cash = initial
    positions: dict[str, dict] = {}
    trades: list[dict] = []
    
    end = datetime.now()
    for d in range(days):
        day = (end - timedelta(days=days - d)).strftime("%Y-%m-%d")
        day_next = (end - timedelta(days=days - d - 1)).strftime("%Y-%m-%d")
        
        # 先平倉昨日持倉
        for sym, pos in list(positions.items()):
            df = fetcher.fetch_klines(sym, day, day)
            if df.empty:
                continue
            exit_price = float(df.iloc[-1]["close"])
            pnl = (exit_price - pos["entry"]) * pos["qty"]
            cash += pos["qty"] * exit_price
            trades.append({
                "symbol": sym,
                "side": "SELL",
                "price": exit_price,
                "pnl": pnl,
                "date": day,
            })
            del positions[sym]
        
        # 選股並買入（使用 day 當天收盤前的資料）
        day_dt = datetime.strptime(day, "%Y-%m-%d")
        start_hist = (day_dt - timedelta(days=60)).strftime("%Y-%m-%d")
        buys_today = 0
        max_buys_per_day = 5
        for sym in symbols:
            if buys_today >= max_buys_per_day:
                break
            df = fetcher.fetch_klines(sym, start_hist, day)
            if df.empty or len(df) < 30:
                continue
            df = add_all_indicators(df)
            row = df.iloc[-1]
            score = calc_buy_sell_score(row)
            if score < 2:
                continue
            price = float(row["close"])
            amount = balance * 0.1
            if amount < 10000 or cash < amount:
                continue
            qty = int(amount / price / 1000) * 1000
            if qty <= 0:
                continue
            cost = qty * price
            cash -= cost
            positions[sym] = {"entry": price, "qty": qty}
            buys_today += 1
            trades.append({
                "symbol": sym,
                "side": "BUY",
                "price": price,
                "qty": qty,
                "date": day,
            })
        
        # 計算持倉市值
        pos_value = 0
        for s, p in positions.items():
            df = fetcher.fetch_klines(s, day, day)
            if not df.empty:
                pos_value += p["qty"] * float(df.iloc[-1]["close"])
            else:
                pos_value += p["qty"] * p["entry"]
        balance = cash + pos_value
    
    # 最後平倉
    for sym, pos in list(positions.items()):
        df = fetcher.fetch_klines(sym, end.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        exit_price = float(df.iloc[-1]["close"]) if not df.empty else pos["entry"]
        pnl = (exit_price - pos["entry"]) * pos["qty"]
        cash += pos["qty"] * exit_price
        trades.append({"symbol": sym, "side": "SELL", "price": exit_price, "pnl": pnl})
    
    total_pnl = cash - initial
    roi = total_pnl / initial * 100
    closed = [t for t in trades if t.get("pnl") is not None]
    wins = sum(1 for t in closed if t["pnl"] > 0)
    win_rate = wins / len(closed) * 100 if closed else 0
    
    return {
        "initial_balance": initial,
        "final_balance": round(cash, 2),
        "total_pnl": round(total_pnl, 2),
        "roi_pct": round(roi, 2),
        "win_rate": round(win_rate, 1),
        "trade_count": len(trades),
    }


if __name__ == "__main__":
    logger.info("開始一週模擬交易（100 萬台幣）...")
    result = run_weekly_sim(initial=SIMULATION_INITIAL_BALANCE)
    logger.info("=" * 50)
    logger.info(f"初始資金: {result['initial_balance']:,.0f} 元")
    logger.info(f"最終資金: {result['final_balance']:,.0f} 元")
    logger.info(f"總損益: {result['total_pnl']:+,.2f} 元")
    logger.info(f"報酬率: {result['roi_pct']:+.2f}%")
    logger.info(f"勝率: {result['win_rate']:.1f}%")
    logger.info(f"交易筆數: {result['trade_count']}")
    logger.info("=" * 50)
