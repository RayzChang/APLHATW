from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TradeSignal(BaseModel):
    signal_id: str
    symbol: str
    action: str = "NO_TRADE"
    source: str = "AUTO_SCAN"
    confidence: float = 0.0
    current_price: float = 0.0
    entry_price: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    position_size_pct: float = 0.0
    reason: str = ""
    created_at: datetime

