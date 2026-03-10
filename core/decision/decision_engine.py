from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from core.analysis.analysis_models import AnalysisResult
from core.decision.signal_models import TradeSignal


class DecisionEngine:
    """Convert AnalysisResult into an executable TradeSignal."""

    def __init__(self, min_confidence: float = 0.7, max_position_pct: float = 20.0):
        self.min_confidence = min_confidence
        self.max_position_pct = max_position_pct

    def build_signal(self, analysis_result: AnalysisResult, source: str = "AUTO_SCAN") -> TradeSignal:
        action = (analysis_result.final_decision.action or "HOLD").upper()
        confidence = float(analysis_result.final_decision.confidence or 0.0)
        position_size_pct = min(float(analysis_result.execution_plan.position_size_pct or 0.0), self.max_position_pct)

        final_action = action
        if action == "BUY":
            if confidence < self.min_confidence or position_size_pct <= 0:
                final_action = "NO_TRADE"
        elif action not in {"SELL", "HOLD"}:
            final_action = "NO_TRADE"

        return TradeSignal(
            signal_id=str(uuid4()),
            symbol=analysis_result.symbol,
            action=final_action,
            source=source,
            confidence=confidence,
            current_price=analysis_result.quote.current_price,
            entry_price=analysis_result.execution_plan.entry_price,
            stop_loss_price=analysis_result.execution_plan.stop_loss_price,
            take_profit_price=analysis_result.execution_plan.take_profit_price,
            position_size_pct=position_size_pct,
            reason=analysis_result.final_decision.reasoning,
            created_at=datetime.now(),
        )

