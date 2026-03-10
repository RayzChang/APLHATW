from __future__ import annotations

from datetime import datetime

from core.decision.signal_models import TradeSignal
from core.execution.execution_models import ExecutionResult
from core.risk.exposure_manager import ExposureManager


class ExecutionEngine:
    """Consumes TradeSignal and mutates simulator state through a narrow interface."""

    def __init__(self, commission_rate: float, tax_rate: float, max_position_pct: float):
        self.commission_rate = commission_rate
        self.tax_rate = tax_rate
        self.exposure_manager = ExposureManager(max_position_pct=max_position_pct)

    def execute(self, simulator, signal: dict | TradeSignal) -> ExecutionResult:
        signal_data = simulator._normalize_signal(signal)
        action = signal_data.get("action", "HOLD")
        confidence = float(signal_data.get("confidence", 0.0) or 0.0)
        stock_id = signal_data.get("stock_id")
        price = float(signal_data.get("current_price", 0.0) or 0.0)
        signal_id = signal_data.get("signal_id")

        if not stock_id or price <= 0:
            return ExecutionResult(
                executed=False,
                reason="無效的訊號資料",
                shares=0,
                cost=0,
                remaining_cash=simulator.cash,
                signal_id=signal_id,
                stock_id=stock_id,
                action=action,
            )

        if action == "BUY" and confidence >= 0.7:
            return self._execute_buy(simulator, signal_data, signal_id, stock_id, action, price)
        if action == "SELL" and stock_id in simulator.positions:
            return self._execute_sell(simulator, signal_id, stock_id, action, price)

        return ExecutionResult(
            executed=False,
            reason="無動作",
            shares=0,
            cost=0,
            remaining_cash=simulator.cash,
            signal_id=signal_id,
            stock_id=stock_id,
            action=action,
        )

    def _execute_buy(self, simulator, signal_data: dict, signal_id: str | None, stock_id: str, action: str, price: float) -> ExecutionResult:
        can_trade, reason = simulator.can_open_new_position()
        if not can_trade:
            return ExecutionResult(
                executed=False,
                reason=reason,
                shares=0,
                cost=0,
                remaining_cash=simulator.cash,
                signal_id=signal_id,
                stock_id=stock_id,
                action=action,
            )

        if stock_id in simulator.positions:
            return ExecutionResult(
                executed=False,
                reason="已持有部位",
                shares=0,
                cost=0,
                remaining_cash=simulator.cash,
                signal_id=signal_id,
                stock_id=stock_id,
                action=action,
            )

        available = self.exposure_manager.calculate_target_allocation(simulator.cash, signal_data.get("position_size_pct", 10))
        shares = self.exposure_manager.calculate_lot_shares(available, price)
        if shares < 1000:
            reason = f"資金不足：需要 {price*1000:,.0f} 元買一張，可用資金 {available:,.0f} 元"
            return ExecutionResult(
                executed=False,
                reason=reason,
                shares=0,
                cost=0,
                remaining_cash=simulator.cash,
                signal_id=signal_id,
                stock_id=stock_id,
                action=action,
            )

        while shares >= 1000:
            cost_base = shares * price
            fee = cost_base * self.commission_rate
            total_cost = cost_base + fee
            if total_cost <= simulator.cash:
                break
            shares -= 1000

        if shares < 1000:
            return ExecutionResult(
                executed=False,
                reason="可用現金不足以支付含手續費之成本",
                shares=0,
                cost=0,
                remaining_cash=simulator.cash,
                signal_id=signal_id,
                stock_id=stock_id,
                action=action,
            )

        simulator.cash -= total_cost
        simulator.positions[stock_id] = {
            "shares": shares,
            "avg_cost": total_cost / shares,
            "entry_price": price,
            "current_price": price,
            "highest_price": price,
            "stop_loss_price": signal_data.get("stop_loss_price", price * 0.95),
            "take_profit_price": signal_data.get("take_profit_price", price * 1.1),
            "name": signal_data.get("name", stock_id),
            "timestamp": datetime.now().isoformat(),
        }
        simulator.trade_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "stock_id": stock_id,
                "type": "BUY",
                "price": price,
                "shares": shares,
                "fee": fee,
                "total_cost": total_cost,
                "remaining_cash": simulator.cash,
            }
        )
        simulator.save_state()
        return ExecutionResult(
            executed=True,
            reason=f"已買入 {shares} 股",
            shares=shares,
            cost=round(total_cost, 2),
            remaining_cash=round(simulator.cash, 2),
            signal_id=signal_id,
            stock_id=stock_id,
            action=action,
        )

    def _execute_sell(self, simulator, signal_id: str | None, stock_id: str, action: str, price: float) -> ExecutionResult:
        pos = simulator.positions.pop(stock_id)
        shares = pos["shares"]
        amount = shares * price
        fee = amount * self.commission_rate
        tax = amount * self.tax_rate
        total_receive = amount - fee - tax
        pnl = total_receive - (shares * pos["avg_cost"])

        simulator.cash += total_receive
        simulator.trade_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "stock_id": stock_id,
                "type": "SELL",
                "price": price,
                "shares": shares,
                "fee": fee,
                "tax": tax,
                "pnl": pnl,
                "pnl_pct": (pnl / (shares * pos["avg_cost"])) * 100,
                "remaining_cash": simulator.cash,
            }
        )
        simulator.save_state()
        return ExecutionResult(
            executed=True,
            reason=f"已賣出 {shares} 股，獲利 {pnl:.2f}",
            shares=shares,
            cost=0,
            remaining_cash=round(simulator.cash, 2),
            signal_id=signal_id,
            stock_id=stock_id,
            action=action,
        )
