import sqlite3
import json
import os
import sys
from datetime import datetime
from loguru import logger

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

    def execute_signal(self, signal: dict) -> dict:
        """接收 Orchestrator 訊號並執行。"""
        action = signal.get("action", "HOLD")
        confidence = signal.get("confidence", 0.0)
        stock_id = signal.get("stock_id")
        price = signal.get("current_price", 0.0)
        
        if not stock_id or price <= 0:
            return {"executed": False, "reason": "無效的訊號資料", "shares": 0, "cost": 0, "remaining_cash": self.cash}

        # 執行買入
        if action == "BUY" and confidence >= 0.7:
            if stock_id in self.positions:
                return {"executed": False, "reason": "已持有部位", "shares": 0, "cost": 0, "remaining_cash": self.cash}
                
            # 1. 計算可用買入金額：available = cash * min(position_size_pct/100, max_position_pct)
            pos_size_pct = signal.get("position_size_pct", 10) / 100
            target_pct = min(pos_size_pct, self.max_position_pct)
            available = self.cash * target_pct
            
            # 2. 計算可買張數：shares = int(available / price / 1000) * 1000
            shares = int(available / price / 1000) * 1000
            
            # 3. 判斷邏輯
            if shares < 1000:
                reason = f"資金不足：需要 {price*1000:,.0f} 元買一張，可用資金 {available:,.0f} 元"
                return {
                    "executed": False, 
                    "reason": reason, 
                    "shares": 0, 
                    "cost": 0, 
                    "remaining_cash": self.cash
                }
                
            # 4. 買入時的費用計算：確認 cost <= cash 才執行，否則遞減張數直到符合
            while shares >= 1000:
                cost_base = shares * price
                fee = cost_base * self.commission_rate
                total_cost = cost_base + fee
                if total_cost <= self.cash:
                    break
                shares -= 1000

            if shares < 1000:
                return {
                    "executed": False, 
                    "reason": "可用現金不足以支付含手續費之成本", 
                    "shares": 0, 
                    "cost": 0, 
                    "remaining_cash": self.cash
                }

            self.cash -= total_cost
            self.positions[stock_id] = {
                "shares": shares,
                "avg_cost": (total_cost / shares),
                "entry_price": price,
                "current_price": price,       # 即時更新，供損益計算用
                "highest_price": price,
                "stop_loss_price": signal.get("stop_loss_price", price * 0.95),
                "take_profit_price": signal.get("take_profit_price", price * 1.1),
                "name": signal.get("name", stock_id),
                "timestamp": datetime.now().isoformat()
            }
            
            trade_record = {
                "timestamp": datetime.now().isoformat(),
                "stock_id": stock_id,
                "type": "BUY",
                "price": price,
                "shares": shares,
                "fee": fee,
                "total_cost": total_cost,
                "remaining_cash": self.cash
            }
            self.trade_history.append(trade_record)
            self.save_state()
            logger.success(f"Executed BUY for {stock_id}: {shares} shares at {price}")
            
            return {
                "executed": True, 
                "reason": f"已買入 {shares} 股",
                "shares": shares,
                "cost": round(total_cost, 2),
                "remaining_cash": round(self.cash, 2)
            }

        # 執行賣出
        elif action == "SELL" and stock_id in self.positions:
            pos = self.positions.pop(stock_id)
            shares = pos["shares"]
            amount = shares * price
            fee = amount * self.commission_rate
            tax = amount * self.tax_rate
            total_receive = amount - fee - tax
            
            pnl = total_receive - (shares * pos["avg_cost"])
            
            self.cash += total_receive
            trade_record = {
                "timestamp": datetime.now().isoformat(),
                "stock_id": stock_id,
                "type": "SELL",
                "price": price,
                "shares": shares,
                "fee": fee,
                "tax": tax,
                "pnl": pnl,
                "pnl_pct": (pnl / (shares * pos["avg_cost"])) * 100,
                "remaining_cash": self.cash
            }
            self.trade_history.append(trade_record)
            self.save_state()
            logger.success(f"Executed SELL for {stock_id}: {shares} shares at {price}, PnL: {pnl:.2f}")
            
            return {
                "executed": True, 
                "reason": f"已賣出 {shares} 股，獲利 {pnl:.2f}",
                "shares": shares,
                "cost": 0, # 這裡是賣出，cost意義自訂，通常回傳成交金額或receive
                "remaining_cash": round(self.cash, 2)
            }

        return {"executed": False, "reason": "無動作", "shares": 0, "cost": 0, "remaining_cash": self.cash}

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
        actions = []
        to_sell = []

        for sid, pos in self.positions.items():
            if sid not in current_prices:
                continue

            price = current_prices[sid]

            # 更新即時價格與最高價
            pos["current_price"] = price
            if price > pos["highest_price"]:
                pos["highest_price"] = price

            profit_pct = (price - pos["entry_price"]) / pos["entry_price"]

            # a. 止損觸發
            if price <= pos["stop_loss_price"]:
                logger.warning(f"Risk: Stop loss triggered for {sid} at {price:.2f}")
                to_sell.append((sid, "止損觸發"))
                actions.append({"stock_id": sid, "action": "SELL", "reason": "止損觸發", "price": price})
                continue

            # b. 止盈觸發
            if price >= pos["take_profit_price"]:
                logger.info(f"Risk: Take profit triggered for {sid} at {price:.2f}")
                to_sell.append((sid, "止盈觸發"))
                actions.append({"stock_id": sid, "action": "SELL", "reason": "止盈觸發", "price": price})
                continue

            # c. 保本觸發：獲利超過 1.5% → 止損上移至成本價（含來回手續費）
            if profit_pct >= 0.015:
                be_price = pos["entry_price"] * (1 + self.commission_rate * 2)
                if pos["stop_loss_price"] < be_price:
                    pos["stop_loss_price"] = be_price
                    logger.info(f"Risk: Moving SL to BE for {sid} at {be_price:.2f}")
                    actions.append({"stock_id": sid, "action": "UPDATE_SL", "reason": "保本觸發", "new_sl": be_price})

            # d. 追蹤止損：獲利超過 3% → 啟動追蹤止損，保持最高價下方 1.5%
            if profit_pct >= 0.03:
                ts_price = pos["highest_price"] * (1 - 0.015)
                if pos["stop_loss_price"] < ts_price:
                    pos["stop_loss_price"] = ts_price
                    logger.info(f"Risk: Trailing SL for {sid} → {ts_price:.2f}")
                    actions.append({"stock_id": sid, "action": "UPDATE_SL", "reason": "追蹤止損更新", "new_sl": ts_price})

        # 執行強制賣出（止損 / 止盈）
        for sid, reason in to_sell:
            self.execute_signal({
                "stock_id": sid,
                "action": "SELL",
                "current_price": current_prices[sid],
                "confidence": 1.0
            })

        if actions:
            self.save_state()

        return actions

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
