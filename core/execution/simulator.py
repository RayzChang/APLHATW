import sqlite3
import json
import os
import sys
from datetime import datetime
from loguru import logger

from core.decision.signal_models import TradeSignal
from core.execution.execution_engine import ExecutionEngine
from core.execution.execution_models import ExecutionResult
from core.execution.portfolio_service import PortfolioService
from core.risk.risk_engine import RiskEngine

class TradeSimulator:
    """
    台股交易模擬器，負責執行訊號、管理部位、風險控制以及持久化狀態。
    """
    def __init__(
        self, 
        initial_capital: float = 1_000_000,
        commission_rate: float = 0.001425,
        tax_rate: float = 0.003,
        max_position_pct: float = 0.2,
        db_path: str = "database/simulation.db"
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.tax_rate = tax_rate
        self.max_position_pct = max_position_pct
        self.db_path = db_path
        
        # 內部狀態
        self.cash = initial_capital
        self.positions = {}  # {stock_id: {shares, avg_cost, entry_price, highest_price, stop_loss_price, take_profit_price}}
        self.trade_history = []
        self.equity_curve = []
        self.portfolio_service = PortfolioService()
        self.execution_engine = ExecutionEngine(
            commission_rate=self.commission_rate,
            tax_rate=self.tax_rate,
            max_position_pct=self.max_position_pct,
        )
        self.risk_engine = RiskEngine(commission_rate=self.commission_rate)
        
        # 確保資料庫與資料表存在
        self._ensure_db_initialized()
        self.load_state()

    def _ensure_db_initialized(self):
        """確保資料庫檔案與所需的資料表都已建立。"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS positions (stock_id TEXT PRIMARY KEY, data TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS equity (timestamp TEXT PRIMARY KEY, total_assets REAL)")
        conn.commit()
        conn.close()

    def _get_conn(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        return sqlite3.connect(self.db_path)

    def reset(self, new_capital: float | None = None):
        """清空所有狀態，重設回初始資金，並重建資料位元。
        若傳入 new_capital，同時更新 initial_capital。
        """
        if new_capital is not None and new_capital > 0:
            self.initial_capital = new_capital
            logger.info(f"TradeSimulator: initial_capital 更新為 {new_capital:,.0f}")
        logger.info("Resetting TradeSimulator state and database...")
        self.cash = self.initial_capital
        self.positions = {}
        self.trade_history = []
        self.equity_curve = [{"timestamp": datetime.now().isoformat(), "total_assets": self.cash}]
        
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS positions (stock_id TEXT PRIMARY KEY, data TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS equity (timestamp TEXT PRIMARY KEY, total_assets REAL)")
        conn.commit()
        conn.close()
        self.save_state()

    def load_state(self):
        """從 SQLite 載入狀態。"""
        if not os.path.exists(self.db_path):
            logger.info(f"Database {self.db_path} not found. Skipping load.")
            return

        try:
            logger.debug(f"Loading state from {self.db_path}...")
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # 載入基礎狀態
            cursor.execute("SELECT value FROM state WHERE key='cash'")
            row = cursor.fetchone()
            if row:
                self.cash = float(row[0])
                logger.debug(f"Loaded cash: {self.cash}")
            
            # 載入部位
            self.positions = {}
            cursor.execute("SELECT stock_id, data FROM positions")
            rows = cursor.fetchall()
            for sid, data in rows:
                self.positions[sid] = json.loads(data)
            logger.debug(f"Loaded {len(self.positions)} positions.")
                
            # 載入交易紀錄
            self.trade_history = []
            cursor.execute("SELECT data FROM trades ORDER BY id ASC")
            for (data,) in cursor.fetchall():
                self.trade_history.append(json.loads(data))
                
            # 載入資產曲線
            self.equity_curve = []
            cursor.execute("SELECT timestamp, total_assets FROM equity ORDER BY timestamp ASC")
            for ts, assets in cursor.fetchall():
                self.equity_curve.append({"timestamp": ts, "total_assets": assets})
                
            conn.close()
            logger.info(f"Loaded simulation state. Cash: {self.cash}, Positions: {len(self.positions)}")
        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    def save_state(self):
        """將狀態持久化到 SQLite。"""
        try:
            logger.debug(f"Saving state to {self.db_path}...")
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # 儲存基礎狀態
            cursor.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('cash', ?)", (str(self.cash),))
            
            # 儲存部位
            cursor.execute("DELETE FROM positions")
            for sid, data in self.positions.items():
                cursor.execute("INSERT INTO positions (stock_id, data) VALUES (?, ?)", (sid, json.dumps(data)))
            
            # 儲存交易紀錄
            cursor.execute("DELETE FROM trades")
            for trade in self.trade_history:
                cursor.execute("INSERT INTO trades (data) VALUES (?)", (json.dumps(trade),))
                
            # 儲存資產曲線
            summary = self.get_portfolio_summary()
            total_assets = summary["total_assets"]
            ts = datetime.now().isoformat()
            cursor.execute("INSERT OR IGNORE INTO equity (timestamp, total_assets) VALUES (?, ?)", (ts, total_assets))
            
            conn.commit()
            conn.close()
            logger.debug("State saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _normalize_signal(self, signal: dict | TradeSignal) -> dict:
        if isinstance(signal, TradeSignal):
            payload = signal.model_dump()
            payload["stock_id"] = signal.symbol
            payload["name"] = payload.get("name", signal.symbol)
            return payload
        return dict(signal)

    def execute_trade_signal(self, signal: dict | TradeSignal) -> ExecutionResult:
        """V2-compatible execution entrypoint."""
        result = self.execution_engine.execute(self, signal)
        if result.executed:
            logger.success(f"Executed {result.action} for {result.stock_id}: {result.reason}")
        return result

    def execute_signal(self, signal: dict | TradeSignal) -> dict:
        """Legacy adapter maintained for existing routes/jobs."""
        return self.execute_trade_signal(signal).model_dump()

    def update_current_prices(self, current_prices: dict):
        """
        更新所有持倉的即時價格（供損益計算用）。
        current_prices: {stock_id: price}
        """
        changed = False
        for sid, pos in self.positions.items():
            if sid in current_prices:
                pos["current_price"] = current_prices[sid]
                changed = True
        if changed:
            self.save_state()

    def check_risk_management(self, current_prices: dict) -> list[dict]:
        """
        遍歷部位檢查風險控管，同時更新即時價格。
        current_prices: {stock_id: price}
        回傳觸發的動作列表。
        """
        actions = self.risk_engine.evaluate_positions(self.positions, current_prices)

        for action in actions:
            if action.get("action") == "SELL":
                exit_signal = self.risk_engine.build_exit_signal(
                    stock_id=action["stock_id"],
                    price=action["price"],
                    reason=action.get("reason", "風控觸發"),
                )
                self.execute_signal(exit_signal)

        if actions:
            self.save_state()

        return actions

    def get_portfolio_model(self):
        return self.portfolio_service.build_portfolio(self)

    def get_portfolio_summary(self) -> dict:
        """
        回傳資產概覽。
        持倉市值優先使用 current_price（由 update_current_prices 更新），
        若未更新過則 fallback 到 entry_price。
        """
        pos_value = 0
        positions_detail = []

        for sid, pos in self.positions.items():
            price = pos.get("current_price", pos["entry_price"])
            market_value = pos["shares"] * price
            cost_basis   = pos["shares"] * pos["avg_cost"]
            unrealized_pnl = market_value - cost_basis
            unrealized_pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis else 0.0

            pos_value += market_value
            positions_detail.append({
                "stock_id": sid,
                "name": pos.get("name", sid),
                "shares": pos["shares"],
                "entry_price": round(pos["entry_price"], 2),
                "current_price": round(price, 2),
                "avg_cost": round(pos["avg_cost"], 2),
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
                "stop_loss_price": round(pos.get("stop_loss_price", 0), 2),
                "take_profit_price": round(pos.get("take_profit_price", 0), 2),
                "highest_price": round(pos.get("highest_price", price), 2),
                "timestamp": pos.get("timestamp", ""),
            })

        total_assets = self.cash + pos_value
        total_pnl = total_assets - self.initial_capital
        total_pnl_pct = (total_pnl / self.initial_capital * 100) if self.initial_capital else 0.0

        closed_trades = [t for t in self.trade_history if t.get("type") == "SELL"]
        wins = [t for t in closed_trades if t.get("pnl", 0) > 0]
        win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0.0

        realized_pnl = sum(t.get("pnl", 0) for t in closed_trades)

        return {
            "total_assets": round(total_assets, 2),
            "cash": round(self.cash, 2),
            "positions_value": round(pos_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "realized_pnl": round(realized_pnl, 2),
            "win_rate": round(win_rate, 2),
            "total_trades": len(self.trade_history),
            "closed_trades": len(closed_trades),
            "positions": positions_detail,
            "positions_count": len(self.positions),
        }
