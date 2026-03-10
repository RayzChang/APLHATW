from __future__ import annotations

from datetime import datetime
from typing import Any

from core.execution.execution_models import Portfolio, Position, TradeRecord


class PortfolioService:
    """Phase 1 adapter that maps simulator state into V2 portfolio models."""

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    def build_portfolio(self, simulator) -> Portfolio:
        summary = simulator.get_portfolio_summary()
        positions = [self._build_position(item) for item in summary.get("positions", [])]
        trades = [self._build_trade(item) for item in simulator.trade_history]

        return Portfolio(
            total_assets=float(summary.get("total_assets", 0.0)),
            cash=float(summary.get("cash", 0.0)),
            positions_value=float(summary.get("positions_value", 0.0)),
            total_pnl=float(summary.get("total_pnl", 0.0)),
            total_pnl_pct=float(summary.get("total_pnl_pct", 0.0)),
            realized_pnl=float(summary.get("realized_pnl", 0.0)),
            win_rate=float(summary.get("win_rate", 0.0)),
            total_trades=int(summary.get("total_trades", 0)),
            closed_trades=int(summary.get("closed_trades", 0)),
            position_count=int(summary.get("positions_count", len(positions))),
            positions=positions,
            trade_history=trades,
        )

    def _build_position(self, item: dict[str, Any]) -> Position:
        return Position(
            stock_id=item.get("stock_id", ""),
            name=item.get("name", ""),
            shares=int(item.get("shares", 0)),
            avg_cost=float(item.get("avg_cost", 0.0)),
            entry_price=float(item.get("entry_price", 0.0)),
            current_price=float(item.get("current_price", 0.0)),
            market_value=float(item.get("market_value", 0.0)),
            unrealized_pnl=float(item.get("unrealized_pnl", 0.0)),
            unrealized_pnl_pct=float(item.get("unrealized_pnl_pct", 0.0)),
            stop_loss_price=float(item.get("stop_loss_price", 0.0)),
            take_profit_price=float(item.get("take_profit_price", 0.0)),
            highest_price=float(item.get("highest_price", 0.0)),
            timestamp=self._parse_timestamp(item.get("timestamp")),
        )

    def _build_trade(self, item: dict[str, Any]) -> TradeRecord:
        action = item.get("type", item.get("action", ""))
        shares = int(item.get("shares", 0))
        price = float(item.get("price", 0.0))
        total_value = item.get("total_cost", shares * price) if action == "BUY" else shares * price

        return TradeRecord(
            timestamp=self._parse_timestamp(item.get("timestamp")),
            stock_id=item.get("stock_id", ""),
            stock_name=item.get("stock_name", item.get("name", "")),
            action=action,
            price=price,
            shares=shares,
            total_value=float(total_value),
            fee=float(item.get("fee", 0.0)),
            tax=float(item.get("tax", 0.0)),
            pnl=float(item["pnl"]) if item.get("pnl") is not None else None,
            pnl_pct=float(item["pnl_pct"]) if item.get("pnl_pct") is not None else None,
            remaining_cash=float(item.get("remaining_cash", 0.0)),
            raw=dict(item),
        )

