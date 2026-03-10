from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from core.analysis.analysis_models import AnalysisResult
from core.decision.signal_models import TradeSignal


class DecisionEngine:
    """Convert AnalysisResult into an executable TradeSignal."""

    def __init__(
        self,
        min_confidence: float = 0.7,
        max_position_pct: float = 20.0,
        min_risk_reward: float = 1.5,
        require_positive_alignment: bool = True,
    ):
        self.min_confidence = min_confidence
        self.max_position_pct = max_position_pct
        self.min_risk_reward = min_risk_reward
        self.require_positive_alignment = require_positive_alignment

    def configure(
        self,
        min_confidence: float | None = None,
        min_risk_reward: float | None = None,
        max_position_pct: float | None = None,
        require_positive_alignment: bool | None = None,
    ) -> None:
        if min_confidence is not None:
            self.min_confidence = min_confidence
        if min_risk_reward is not None:
            self.min_risk_reward = min_risk_reward
        if max_position_pct is not None:
            self.max_position_pct = max_position_pct
        if require_positive_alignment is not None:
            self.require_positive_alignment = require_positive_alignment

    def build_signal(self, analysis_result: AnalysisResult, source: str = "AUTO_SCAN") -> TradeSignal:
        action = (analysis_result.final_decision.action or "HOLD").upper()
        confidence = float(analysis_result.final_decision.confidence or 0.0)
        position_size_pct = min(float(analysis_result.execution_plan.position_size_pct or 0.0), self.max_position_pct)
        risk_ratio = float(analysis_result.risk_summary.risk_reward_ratio or 0.0)
        technical_score = float(analysis_result.technical_summary.score or 0.0)
        sentiment_score = float(analysis_result.sentiment_summary.score or 0.0)

        final_action = action
        if action == "BUY":
            if confidence < self.min_confidence or position_size_pct <= 0:
                final_action = "NO_TRADE"
            elif risk_ratio < self.min_risk_reward:
                final_action = "NO_TRADE"
            elif self.require_positive_alignment and technical_score <= 0 and sentiment_score <= 0:
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
