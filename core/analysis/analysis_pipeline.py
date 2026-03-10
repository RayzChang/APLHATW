from __future__ import annotations

from typing import Any

from core.agents.chief_decision_maker import ChiefDecisionMakerAgent
from core.agents.risk_manager import RiskManagerAgent
from core.agents.sentiment_analyst import SentimentAnalystAgent
from core.agents.technical_analyst import TechnicalAnalystAgent
from core.analysis.analysis_context_builder import AnalysisContext, AnalysisContextBuilder
from core.analysis.analysis_models import AgentReports, AnalysisResult, ExecutionPlan, FinalDecision, MarketContext, QuoteSnapshot, RiskSummary, SentimentSummary, TechnicalSummary
from core.decision.decision_engine import DecisionEngine


class AnalysisPipeline:
    """Unified analysis entrypoint for single-symbol analysis."""

    def __init__(
        self,
        context_builder: AnalysisContextBuilder,
        technical_agent: TechnicalAnalystAgent | None = None,
        sentiment_agent: SentimentAnalystAgent | None = None,
        risk_agent: RiskManagerAgent | None = None,
        chief_agent: ChiefDecisionMakerAgent | None = None,
        decision_engine: DecisionEngine | None = None,
    ):
        self.context_builder = context_builder
        self.technical_agent = technical_agent or TechnicalAnalystAgent()
        self.sentiment_agent = sentiment_agent or SentimentAnalystAgent(enable_search=True)
        self.risk_agent = risk_agent or RiskManagerAgent()
        self.chief_agent = chief_agent or ChiefDecisionMakerAgent()
        self.decision_engine = decision_engine or DecisionEngine()

    def analyze_symbol(self, query: str, portfolio: dict[str, Any] | None = None) -> AnalysisResult:
        context = self.context_builder.build(query, portfolio=portfolio)
        return self.run(context)

    def run(self, context: AnalysisContext) -> AnalysisResult:
        current_price = float(context.quote.get("price", 0.0) or 0.0)
        if current_price <= 0 and context.stock_analysis:
            current_price = float(context.stock_analysis.close)
        technical_report = self.technical_agent.analyze_context(self._build_technical_payload(context))
        sentiment_report = self.sentiment_agent.analyze_context(self._build_sentiment_payload(context))
        risk_report = self.risk_agent.analyze_context(self._build_risk_payload(context))
        decision_raw = self.chief_agent.analyze_context(
            {
                "symbol": context.symbol,
                "name": context.name,
                "current_price": current_price,
                "technical_report": technical_report,
                "sentiment_report": sentiment_report,
                "risk_report": risk_report,
            }
        )

        technical_summary = self._build_technical_summary(context)
        sentiment_summary = self._build_sentiment_summary(context)
        risk_summary = self._build_risk_summary(context)
        final_decision = self._build_final_decision(decision_raw)
        execution_plan = self._build_execution_plan(context, final_decision, risk_summary)

        return AnalysisResult(
            symbol=context.symbol,
            name=context.name,
            query=context.query,
            timestamp=context.timestamp,
            market_context=MarketContext(**context.market_context),
            quote=QuoteSnapshot(
                current_price=current_price,
                open=float(context.quote.get("open", current_price) or current_price),
                high=float(context.quote.get("high", current_price) or current_price),
                low=float(context.quote.get("low", current_price) or current_price),
                volume=int(context.quote.get("volume", 0) or 0),
                change=float(context.quote.get("change", 0.0) or 0.0),
                change_pct=float(context.quote.get("change_pct", 0.0) or 0.0),
                is_realtime=bool(context.quote.get("is_realtime", False)),
            ),
            technical_summary=technical_summary,
            sentiment_summary=sentiment_summary,
            risk_summary=risk_summary,
            agent_reports=AgentReports(
                technical_report=technical_report,
                sentiment_report=sentiment_report,
                risk_report=risk_report,
                chief_report=str(decision_raw),
            ),
            final_decision=final_decision,
            execution_plan=execution_plan,
        )

    def build_trade_signal(self, analysis_result: AnalysisResult, source: str = "AUTO_SCAN"):
        return self.decision_engine.build_signal(analysis_result, source=source)

    def _build_technical_payload(self, context: AnalysisContext) -> dict[str, Any]:
        analysis = context.stock_analysis
        data = {
            "atr": context.risk_metrics.get("atr", 0.0),
            "swing_high": context.risk_metrics.get("swing_high", 0.0),
            "swing_low": context.risk_metrics.get("swing_low", 0.0),
            "daily_high": float(context.quote.get("high", context.quote.get("price", 0.0)) or 0.0),
            "daily_low": float(context.quote.get("low", context.quote.get("price", 0.0)) or 0.0),
            "daily_close": float(context.quote.get("price", 0.0) or 0.0),
            "volume": int(context.quote.get("volume", 0) or 0),
        }
        if analysis:
            data.update(analysis.technical)
            data["patterns"] = analysis.patterns
            data["fundamental"] = analysis.fundamental
            data["chip"] = analysis.chip
        return {"symbol": context.symbol, "name": context.name, "current_price": float(context.quote.get("price", 0.0) or 0.0), "technical_data": data}

    def _build_sentiment_payload(self, context: AnalysisContext) -> dict[str, Any]:
        return {"symbol": context.symbol, "name": context.name, "news_items": context.news_items}

    def _build_risk_payload(self, context: AnalysisContext) -> dict[str, Any]:
        portfolio = {
            "total_assets": context.portfolio.get("total_assets", 1_000_000),
            "available_cash": context.portfolio.get("cash", context.portfolio.get("available_cash", 1_000_000)),
            "current_position_size": context.portfolio.get("current_position_size", 0),
            "suggested_sl": context.risk_metrics.get("stop_loss_price", 0.0),
            "take_profit_price": context.risk_metrics.get("take_profit_price", 0.0),
            "atr": context.risk_metrics.get("atr", 0.0),
            "stop_loss_price": context.risk_metrics.get("stop_loss_price", 0.0),
        }
        return {"symbol": context.symbol, "name": context.name, "current_price": float(context.quote.get("price", 0.0) or 0.0), "portfolio": portfolio}

    def _build_technical_summary(self, context: AnalysisContext) -> TechnicalSummary:
        analysis = context.stock_analysis
        indicators = analysis.technical if analysis else {}
        ma5 = indicators.get("ma5")
        ma20 = indicators.get("ma20")
        trend = "SIDEWAYS"
        if ma5 and ma20:
            trend = "BULLISH" if ma5 > ma20 else "BEARISH" if ma5 < ma20 else "SIDEWAYS"
        return TechnicalSummary(
            score=3 if analysis and analysis.recommendation == "建議買入" else -3 if analysis and analysis.recommendation == "建議賣出" else 0,
            trend=trend,
            indicators=indicators,
            support=list(analysis.suggested_buy) if analysis else [],
            resistance=list(analysis.suggested_sell) if analysis else [],
        )

    def _build_sentiment_summary(self, context: AnalysisContext) -> SentimentSummary:
        sentiment_map = {"positive": 1, "neutral": 0, "negative": -1}
        score = sum(sentiment_map.get(item.sentiment, 0) for item in context.news_items)
        label = "positive" if score > 1 else "negative" if score < -1 else "neutral"
        return SentimentSummary(
            score=float(score),
            sentiment_label=label,
            headline_summary=[item.title for item in context.news_items[:3]],
            news_items=[{"title": item.title, "summary": item.summary, "published": item.published.isoformat(), "url": item.url, "sentiment": item.sentiment} for item in context.news_items],
        )

    def _build_risk_summary(self, context: AnalysisContext) -> RiskSummary:
        price = float(context.quote.get("price", 0.0) or 0.0)
        stop_loss = float(context.risk_metrics.get("stop_loss_price", 0.0) or 0.0)
        take_profit = float(context.risk_metrics.get("take_profit_price", 0.0) or 0.0)
        risk_amount = max(price - stop_loss, 0.0)
        reward_amount = max(take_profit - price, 0.0)
        ratio = round(reward_amount / risk_amount, 2) if risk_amount > 0 else 0.0
        suggested_position_size_pct = self._estimate_position_size_pct(price, stop_loss, ratio)
        total_assets = float(context.portfolio.get("total_assets", 1_000_000) or 1_000_000)
        return RiskSummary(
            risk_score=round(risk_amount / price * 100, 2) if price else 0.0,
            suggested_stop_loss=stop_loss,
            suggested_take_profit=take_profit,
            suggested_position_size_pct=suggested_position_size_pct,
            max_loss_amount=round(total_assets * suggested_position_size_pct / 100 * (risk_amount / price), 2) if price else 0.0,
            risk_reward_ratio=ratio,
        )

    def _build_final_decision(self, decision_raw: dict[str, Any]) -> FinalDecision:
        return FinalDecision(
            action=str(decision_raw.get("action", "HOLD")).upper(),
            confidence=float(decision_raw.get("confidence", 0.0) or 0.0),
            reasoning=str(decision_raw.get("reasoning", decision_raw.get("raw", ""))),
            score=float(decision_raw.get("score", 0.0) or 0.0),
            score_breakdown=str(decision_raw.get("score_breakdown", "")),
        )

    def _build_execution_plan(self, context: AnalysisContext, final_decision: FinalDecision, risk_summary: RiskSummary) -> ExecutionPlan:
        decision_position_size = 0.0
        if final_decision.action == "BUY":
            decision_position_size = risk_summary.suggested_position_size_pct
        return ExecutionPlan(
            entry_price=float(context.quote.get("price", 0.0) or 0.0),
            stop_loss_price=risk_summary.suggested_stop_loss,
            take_profit_price=risk_summary.suggested_take_profit,
            position_size_pct=decision_position_size,
        )

    @staticmethod
    def _estimate_position_size_pct(price: float, stop_loss: float, ratio: float) -> float:
        if price <= 0 or stop_loss <= 0:
            return 0.0
        stop_loss_pct = ((price - stop_loss) / price) * 100
        if ratio < 1.5:
            return 0.0
        if stop_loss_pct < 3:
            return 0.0
        if stop_loss_pct < 5:
            return 5.0
        if stop_loss_pct < 8:
            return 10.0
        return 15.0
