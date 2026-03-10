from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MarketContext(BaseModel):
    market_trend: str = "UNKNOWN"
    market_risk_level: str = "MEDIUM"
    market_index: float | None = None
    market_change_pct: float | None = None
    is_market_open: bool = False
    source: str = "unavailable"


class QuoteSnapshot(BaseModel):
    current_price: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: int = 0
    change: float = 0.0
    change_pct: float = 0.0
    is_realtime: bool = False


class TechnicalSummary(BaseModel):
    score: int = 0
    trend: str = "SIDEWAYS"
    indicators: dict[str, Any] = Field(default_factory=dict)
    support: list[float] = Field(default_factory=list)
    resistance: list[float] = Field(default_factory=list)


class SentimentSummary(BaseModel):
    score: float = 0.0
    sentiment_label: str = "neutral"
    headline_summary: list[str] = Field(default_factory=list)
    news_items: list[dict[str, Any]] = Field(default_factory=list)


class RiskSummary(BaseModel):
    risk_score: float = 0.0
    suggested_stop_loss: float = 0.0
    suggested_take_profit: float = 0.0
    suggested_position_size_pct: float = 0.0
    max_loss_amount: float = 0.0
    risk_reward_ratio: float = 0.0


class AgentReports(BaseModel):
    technical_report: str = ""
    sentiment_report: str = ""
    risk_report: str = ""
    chief_report: str = ""


class FinalDecision(BaseModel):
    action: str = "HOLD"
    confidence: float = 0.0
    reasoning: str = ""
    score: float = 0.0
    score_breakdown: str = ""


class ExecutionPlan(BaseModel):
    entry_price: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    position_size_pct: float = 0.0


class AnalysisResult(BaseModel):
    symbol: str
    name: str
    query: str
    timestamp: datetime
    market_context: MarketContext
    quote: QuoteSnapshot
    technical_summary: TechnicalSummary
    sentiment_summary: SentimentSummary
    risk_summary: RiskSummary
    agent_reports: AgentReports
    final_decision: FinalDecision
    execution_plan: ExecutionPlan

    def to_legacy_payload(self) -> dict[str, Any]:
        """Adapter for the current frontend / API payload shape."""
        return {
            "symbol": self.symbol,
            "stock_id": self.symbol,
            "name": self.name,
            "current_price": self.quote.current_price,
            "quote": self.quote.model_dump(),
            "market_context": self.market_context.model_dump(),
            "technical_summary": self.technical_summary.model_dump(),
            "sentiment_summary": self.sentiment_summary.model_dump(),
            "risk_summary": self.risk_summary.model_dump(),
            "decision": {
                "action": self.final_decision.action,
                "confidence": self.final_decision.confidence,
                "reasoning": self.final_decision.reasoning,
                "score": self.final_decision.score,
                "score_breakdown": self.final_decision.score_breakdown,
                "position_size_pct": self.execution_plan.position_size_pct,
                "stop_loss_price": self.execution_plan.stop_loss_price,
                "take_profit_price": self.execution_plan.take_profit_price,
            },
            "execution_plan": self.execution_plan.model_dump(),
            "technical_report": self.agent_reports.technical_report,
            "sentiment_report": self.agent_reports.sentiment_report,
            "risk_report": self.agent_reports.risk_report,
            "chief_report": self.agent_reports.chief_report,
            "timestamp": self.timestamp.isoformat(),
        }

