"""SQLite 資料庫管理器 — 台股交易推手"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional

from loguru import logger

from config.settings import DB_PATH
from database.models import INDEXES, TABLES


class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self.get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            for name, sql in TABLES.items():
                conn.execute(sql)
            for idx in INDEXES:
                conn.execute(idx)
            conn.commit()
        logger.info(f"Database initialized: {self.db_path}")

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> list:
        with self.get_connection() as conn:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.fetchall()

    def insert_trade(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        ph = ", ".join(["?"] * len(data))
        sql = f"INSERT INTO trades ({cols}) VALUES ({ph})"
        with self.get_connection() as conn:
            cur = conn.execute(sql, tuple(data.values()))
            conn.commit()
            return cur.lastrowid

    def close_trade(self, trade_id: int, exit_price: float, pnl: float, pnl_pct: float, exit_reason: str) -> None:
        now = datetime.utcnow().isoformat()
        self.execute(
            "UPDATE trades SET exit_price=?, pnl=?, pnl_pct=?, status='CLOSED', closed_at=?, exit_reason=? WHERE id=?",
            (exit_price, pnl, pnl_pct, now, exit_reason, trade_id),
        )

    def get_open_trades(self) -> list[dict]:
        rows = self.execute("SELECT * FROM trades WHERE status='OPEN'")
        return [dict(r) for r in rows]

    def get_trades_since(self, since: str) -> list[dict]:
        rows = self.execute("SELECT * FROM trades WHERE opened_at >= ? ORDER BY opened_at DESC", (since,))
        return [dict(r) for r in rows]

    def init_simulation(self, initial_balance: float) -> None:
        now = datetime.utcnow().isoformat()
        self.execute(
            "INSERT OR REPLACE INTO simulation_state (id, initial_balance, current_balance, total_pnl, started_at, updated_at) VALUES (1, ?, ?, 0, ?, ?)",
            (initial_balance, initial_balance, now, now),
        )

    def get_simulation_state(self) -> Optional[dict]:
        rows = self.execute("SELECT * FROM simulation_state WHERE id=1")
        return dict(rows[0]) if rows else None

    def update_simulation_balance(self, balance: float, total_pnl: float) -> None:
        now = datetime.utcnow().isoformat()
        self.execute(
            "UPDATE simulation_state SET current_balance=?, total_pnl=?, updated_at=? WHERE id=1",
            (balance, total_pnl, now),
        )
