"""SQLite 資料表定義 — 台股交易推手"""

TABLES = {
    "trades": """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            symbol_name TEXT,
            market_type TEXT,
            side TEXT NOT NULL CHECK(side IN ('LONG', 'SHORT')),
            entry_price REAL NOT NULL,
            exit_price REAL,
            quantity REAL NOT NULL,
            amount REAL,
            status TEXT NOT NULL DEFAULT 'OPEN'
                CHECK(status IN ('OPEN', 'CLOSED', 'CANCELLED')),
            pnl REAL,
            pnl_pct REAL,
            fee REAL DEFAULT 0,
            strategy_name TEXT,
            exit_reason TEXT,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "simulation_state": """
        CREATE TABLE IF NOT EXISTS simulation_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            initial_balance REAL NOT NULL,
            current_balance REAL NOT NULL,
            total_pnl REAL DEFAULT 0,
            started_at TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "screener_results": """
        CREATE TABLE IF NOT EXISTS screener_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            symbol_name TEXT,
            strategy_id TEXT,
            signal_type TEXT,
            close_price REAL,
            change_pct REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "backtest_results": """
        CREATE TABLE IF NOT EXISTS backtest_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            symbol_name TEXT,
            strategy_id TEXT,
            total_return REAL,
            win_rate REAL,
            trade_count INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)",
    "CREATE INDEX IF NOT EXISTS idx_trades_opened ON trades(opened_at)",
]
