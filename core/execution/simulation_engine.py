"""
模擬交易引擎 — AI 自主交易

使用者放一筆資金，AI/程式自主決定交易哪些標的（上市、上櫃、期貨）。
使用者不選股，由 AI 掃描全市場。驗證系統穩固後再考慮實盤。
"""

from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from config.settings import SIMULATION_INITIAL_BALANCE, DEFAULT_WATCHLIST
from core.data.tw_data_fetcher import TWDataFetcher
from core.screener.stock_screener import run_screener
from core.backtest.strategy_backtest import run_backtest
from database.db_manager import DatabaseManager


class SimulationEngine:
    """模擬交易引擎"""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()
        self.fetcher = TWDataFetcher()
        self._ensure_simulation_state()

    def _ensure_simulation_state(self) -> None:
        state = self.db.get_simulation_state()
        if not state:
            self.db.init_simulation(SIMULATION_INITIAL_BALANCE)
            logger.info(f"模擬帳戶初始化: {SIMULATION_INITIAL_BALANCE:,.0f} 元")

    def get_balance(self) -> float:
        state = self.db.get_simulation_state()
        return float(state["current_balance"]) if state else SIMULATION_INITIAL_BALANCE

    def run_simulation(
        self,
        symbols: Optional[list[str]] = None,
        strategies: Optional[list[str]] = None,
        days: int = 5,
        initial_balance: Optional[float] = None,
    ) -> dict:
        """
        模擬交易 — 驗證系統穩固性，實盤前必做
        
        可設定金額（50萬、100萬）與天數（一週、一個月）
        回傳：初始資金、最終資金、總報酬、勝率、交易筆數
        """
        amount = initial_balance or SIMULATION_INITIAL_BALANCE
        symbols = symbols or DEFAULT_WATCHLIST[:30]
        strategies = strategies or ["buy_score", "oversold", "kd_golden"]
        
        self.db.init_simulation(amount)
        balance = amount
        total_trades = 0
        wins = 0
        
        end = datetime.now()
        for d in range(days):
            day_start = (end - timedelta(days=days - d)).strftime("%Y-%m-%d")
            day_end = day_start
            
            screener_results = run_screener(symbols, strategies, self.fetcher)
            for r in screener_results:
                if r.signal != "BUY":
                    continue
                # 模擬買入：用 10% 資金買一檔
                amount = balance * 0.1
                if amount < 10000:
                    continue
                qty = int(amount / r.close / 1000) * 1000
                if qty <= 0:
                    continue
                cost = qty * r.close
                balance -= cost
                total_trades += 1
                self.db.insert_trade({
                    "symbol": r.symbol,
                    "symbol_name": r.name,
                    "market_type": "listed",
                    "side": "LONG",
                    "entry_price": r.close,
                    "quantity": qty,
                    "amount": cost,
                    "status": "OPEN",
                    "strategy_name": r.strategy_name,
                    "opened_at": day_start,
                })
            
            open_trades = self.db.get_open_trades()
            for t in open_trades:
                df = self.fetcher.fetch_klines(t["symbol"], day_start, day_end)
                if df.empty:
                    continue
                exit_price = float(df.iloc[-1]["close"])
                pnl = (exit_price - t["entry_price"]) * t["quantity"]
                pnl_pct = (exit_price - t["entry_price"]) / t["entry_price"] * 100
                balance += t["quantity"] * exit_price
                if pnl > 0:
                    wins += 1
                self.db.close_trade(t["id"], exit_price, pnl, pnl_pct, "SIM_DAY_END")
        
        total_pnl = balance - amount
        roi = total_pnl / amount * 100
        win_rate = (wins / total_trades * 100) if total_trades else 0
        self.db.update_simulation_balance(balance, total_pnl)
        
        return {
            "initial_balance": amount,
            "final_balance": round(balance, 2),
            "total_pnl": round(total_pnl, 2),
            "roi_pct": round(roi, 2),
            "win_rate": round(win_rate, 1),
            "trade_count": total_trades,
        }
