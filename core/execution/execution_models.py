from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExecutionResult(BaseModel):
    executed: bool = False
    reason: str = ""
    shares: int = 0
    cost: float = 0.0
    remaining_cash: float = 0.0
    signal_id: str | None = None
    stock_id: str | None = None
    action: str = "NO_TRADE"


class Position(BaseModel):
    stock_id: str
    name: str = ""
    shares: int = 0
    avg_cost: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    highest_price: float = 0.0
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TradeRecord(BaseModel):
    timestamp: datetime | None = None
    stock_id: str
    stock_name: str = ""
    action: str
    price: float = 0.0
    shares: int = 0
    total_value: float = 0.0
    fee: float = 0.0
    tax: float = 0.0
    pnl: float | None = None
    pnl_pct: float | None = None
    remaining_cash: float = 0.0
    raw: dict[str, Any] = Field(default_factory=dict)


class Portfolio(BaseModel):
    total_assets: float = 0.0
    cash: float = 0.0
    positions_value: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    realized_pnl: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    closed_trades: int = 0
    position_count: int = 0
    positions: list[Position] = Field(default_factory=list)
    trade_history: list[TradeRecord] = Field(default_factory=list)

