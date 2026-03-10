from __future__ import annotations


class ExposureManager:
    """Position sizing helper for execution decisions."""

    def __init__(self, max_position_pct: float = 0.2):
        self.max_position_pct = max_position_pct

    def calculate_target_allocation(self, cash: float, position_size_pct: float) -> float:
        requested_pct = max(float(position_size_pct or 0.0) / 100.0, 0.0)
        target_pct = min(requested_pct, self.max_position_pct)
        return cash * target_pct

    @staticmethod
    def calculate_lot_shares(available_cash: float, price: float, lot_size: int = 1000) -> int:
        if available_cash <= 0 or price <= 0:
            return 0
        return int(available_cash / price / lot_size) * lot_size

