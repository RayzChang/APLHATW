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

    def reset(self):
        """清空所有狀態，重設回初始資金，並重建資料位元。"""
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
                "highest_price": price,
                "stop_loss_price": signal.get("stop_loss_price", price * 0.95),
                "take_profit_price": signal.get("take_profit_price", price * 1.1),
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

    def check_risk_management(self, current_prices: dict) -> list[dict]:
        """
        遍歷部位檢查風險控管。
        current_prices: {stock_id: price}
        """
        actions = []
        to_sell = []
        
        for sid, pos in self.positions.items():
            if sid not in current_prices:
                continue
                
            price = current_prices[sid]
            
            # 更新最高價
            if price > pos["highest_price"]:
                pos["highest_price"] = price
            
            profit_pct = (price - pos["entry_price"]) / pos["entry_price"]
            
            # a. 止損觸發
            if price <= pos["stop_loss_price"]:
                logger.warning(f"Risk: Stop loss triggered for {sid} at {price}")
                to_sell.append(sid)
                actions.append({"stock_id": sid, "action": "SELL", "reason": "止損觸發"})
                continue
                
            # b. 保本觸發: 獲利超過 1.5% -> 將止損上移到對應保本價 (考慮來回手續費)
            if profit_pct >= 0.015:
                be_price = pos["entry_price"] * (1 + self.commission_rate * 2)
                if pos["stop_loss_price"] < be_price:
                    pos["stop_loss_price"] = be_price
                    logger.info(f"Risk: Moving SL to BE for {sid} at {be_price:.2f}")
                    actions.append({"stock_id": sid, "action": "UPDATE_SL", "reason": "保本觸發"})

            # c. 追蹤止損: 獲利超過 3% -> 啟動追蹤止損 (1.5%)
            if profit_pct >= 0.03:
                ts_price = pos["highest_price"] * (1 - 0.015)
                if pos["stop_loss_price"] < ts_price:
                    pos["stop_loss_price"] = ts_price
                    logger.info(f"Risk: Moving SL (Trailing) for {sid} to {ts_price:.2f}")
                    actions.append({"stock_id": sid, "action": "UPDATE_SL", "reason": "追蹤止損更新"})

        # 執行強制賣出
        for sid in to_sell:
            self.execute_signal({"stock_id": sid, "action": "SELL", "current_price": current_prices[sid]})
            
        if actions:
            self.save_state()
            
        return actions

    def get_portfolio_summary(self) -> dict:
        """回傳資產概覽。"""
        pos_value = 0
        for sid, pos in self.positions.items():
            # 注意：這裡應該要有最新價格，如果沒有最新價格，先用 entry_price 或 highest_price 代替
            # 在實際應用中，調用者應提供目前價格
            pos_value += pos["shares"] * pos["entry_price"] 
            
        total_assets = self.cash + pos_value
        total_pnl = total_assets - self.initial_capital
        total_pnl_pct = (total_pnl / self.initial_capital) * 100
        
        wins = [t for t in self.trade_history if t.get("type") == "SELL" and t.get("pnl", 0) > 0]
        total_closed = [t for t in self.trade_history if t.get("type") == "SELL"]
        win_rate = (len(wins) / len(total_closed)) * 100 if total_closed else 0.0
        
        return {
            "total_assets": round(total_assets, 2),
            "cash": round(self.cash, 2),
            "positions_value": round(pos_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "win_rate": round(win_rate, 2),
            "total_trades": len(self.trade_history),
            "positions": list(self.positions.keys())
        }
