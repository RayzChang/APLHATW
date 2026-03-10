from __future__ import annotations

from core.risk.sl_tp_calculator import SLTPCalculator


class StopManager:
    """Encapsulates stop-loss / take-profit update rules for open positions."""

    def __init__(self, commission_rate: float = 0.001425, trailing_pct: float = 0.015):
        self.commission_rate = commission_rate
        self.trailing_pct = trailing_pct

    def update_dynamic_stops(self, position: dict, current_price: float) -> list[dict]:
        actions: list[dict] = []
        entry_price = float(position.get("entry_price", 0.0) or 0.0)
        highest_price = max(float(position.get("highest_price", current_price) or current_price), current_price)
        position["highest_price"] = highest_price

        if entry_price <= 0:
            return actions

        profit_pct = (current_price - entry_price) / entry_price

        if profit_pct >= 0.015:
            breakeven_price = SLTPCalculator.calculate_breakeven_stop(entry_price, self.commission_rate)
            if float(position.get("stop_loss_price", 0.0) or 0.0) < breakeven_price:
                position["stop_loss_price"] = breakeven_price
                actions.append({"action": "UPDATE_SL", "reason": "保本觸發", "new_sl": breakeven_price})

        if profit_pct >= 0.03:
            trailing_stop = SLTPCalculator.calculate_trailing_stop(current_price, highest_price, self.trailing_pct)
            if float(position.get("stop_loss_price", 0.0) or 0.0) < trailing_stop:
                position["stop_loss_price"] = trailing_stop
                actions.append({"action": "UPDATE_SL", "reason": "追蹤止損更新", "new_sl": trailing_stop})

        return actions

    @staticmethod
    def should_exit(position: dict, current_price: float) -> tuple[bool, str]:
        stop_loss = float(position.get("stop_loss_price", 0.0) or 0.0)
        take_profit = float(position.get("take_profit_price", 0.0) or 0.0)

        if stop_loss > 0 and current_price <= stop_loss:
            return True, "止損觸發"
        if take_profit > 0 and current_price >= take_profit:
            return True, "止盈觸發"
        return False, ""

