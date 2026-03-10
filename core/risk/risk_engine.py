from __future__ import annotations

from core.decision.signal_models import TradeSignal
from core.risk.stop_manager import StopManager


class RiskEngine:
    """Evaluates open positions and emits exit or stop-update actions."""

    def __init__(self, commission_rate: float = 0.001425, trailing_pct: float = 0.015):
        self.stop_manager = StopManager(commission_rate=commission_rate, trailing_pct=trailing_pct)

    def evaluate_positions(self, positions: dict, current_prices: dict) -> list[dict]:
        actions: list[dict] = []

        for sid, position in positions.items():
            if sid not in current_prices:
                continue

            current_price = current_prices[sid]
            position["current_price"] = current_price

            should_exit, reason = self.stop_manager.should_exit(position, current_price)
            if should_exit:
                actions.append({"stock_id": sid, "action": "SELL", "reason": reason, "price": current_price})
                continue

            for update in self.stop_manager.update_dynamic_stops(position, current_price):
                actions.append({"stock_id": sid, **update})

        return actions

    @staticmethod
    def build_exit_signal(stock_id: str, price: float, reason: str = "風控觸發") -> TradeSignal:
        from datetime import datetime

        return TradeSignal(
            signal_id=f"risk-exit-{stock_id}-{int(datetime.now().timestamp())}",
            symbol=stock_id,
            action="SELL",
            source="RISK_ENGINE",
            confidence=1.0,
            current_price=price,
            entry_price=price,
            stop_loss_price=0.0,
            take_profit_price=0.0,
            position_size_pct=0.0,
            reason=reason,
            created_at=datetime.now(),
        )

