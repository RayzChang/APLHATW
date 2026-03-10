"""
智慧選股 API
- POST /          → 技術面快速分析（不執行交易）
- POST /agent     → 四 Agent 深度分析 + 自動執行模擬交易
- POST /manual    → 四 Agent 深度分析（僅分析，不交易）
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Request
from pydantic import BaseModel

from core.analysis.stock_analysis import analyze_stock
from core.data.news_fetcher import NewsFetcher
from core.agents.technical_analyst import TechnicalAnalystAgent
from core.agents.sentiment_analyst import SentimentAnalystAgent
from core.agents.risk_manager import RiskManagerAgent
from core.agents.chief_decision_maker import ChiefDecisionMakerAgent

_executor = ThreadPoolExecutor(max_workers=4)

router = APIRouter()


class AnalyzeRequest(BaseModel):
    symbols: list[str]


@router.post("/")
async def analyze_stocks(req: AnalyzeRequest):
    """
    技術面快速分析（不呼叫 AI，純指標計算）。
    回傳建議方向、掛單位置、指標解釋。
    """
    loop = asyncio.get_event_loop()
    
    def _run_batch():
        results = []
        for symbol in req.symbols:
            symbol = symbol.strip().upper()
            if not symbol:
                continue
            r = analyze_stock(symbol)
            if r:
                results.append({
                    "symbol":        r.symbol,
                    "name":          r.name,
                    "close":         r.close,
                    "change_pct":    r.change_pct,
                    "recommendation":r.recommendation,
                    "suggested_buy": r.suggested_buy,
                    "suggested_sell":r.suggested_sell,
                    "explanation":   r.explanation,
                    "technical":     r.technical,
                    "fundamental":   r.fundamental,
                    "chip":          r.chip,
                    "patterns":      r.patterns,
                })
        return results

    results = await loop.run_in_executor(_executor, _run_batch)
    return {"count": len(results), "results": results}


def _run_agent_pipeline(symbol: str, simulator_summary: dict, current_position_shares: int) -> dict:
    """
    執行四 Agent 分析流程，回傳各份報告與最終決策。
    """
    r = analyze_stock(symbol)
    if not r:
        return {"error": f"無法取得 {symbol} 技術資料"}

    current_price = r.close
    name          = r.name
    technical_data = {
        "technical":   r.technical,
        "fundamental": r.fundamental,
        "chip":        r.chip,
        "patterns":    r.patterns,
    }

    # 新聞情緒
    news_fetcher = NewsFetcher()
    news_items   = news_fetcher.fetch_stock_news(symbol, name, limit=5)

    # Portfolio 資訊（提供給風控 Agent）
    portfolio = {
        "total_assets":           simulator_summary["total_assets"],
        "available_cash":         simulator_summary["cash"],
        "current_position_size":  current_position_shares,
        "suggested_sl":           r.close * 0.95,   # 預設 5%，Orchestrator 會覆蓋
        "atr":                    r.technical.get("atr", 0),
    }

    # 初始化 Agents
    tech_agent  = TechnicalAnalystAgent()
    sent_agent  = SentimentAnalystAgent(enable_search=True)
    risk_agent  = RiskManagerAgent()
    chief_agent = ChiefDecisionMakerAgent()

    # 逐層分析
    tech_report  = tech_agent.analyze(symbol, name, current_price, technical_data)
    sent_report  = sent_agent.analyze(symbol, name, news_items)
    risk_report  = risk_agent.analyze(symbol, name, current_price, portfolio)
    decision     = chief_agent.analyze(symbol, name, current_price,
                                       tech_report, sent_report, risk_report)

    return {
        "symbol":        symbol,
        "name":          name,
        "current_price": current_price,
        "reports": {
            "technical": tech_report,
            "sentiment": sent_report,
            "risk":      risk_report,
        },
        "decision": decision,
    }


@router.post("/agent")
async def analyze_with_agents(req: AnalyzeRequest, request: Request):
    """
    四 Agent 深度分析，並將決策結果執行進模擬帳戶。
    """
    if not req.symbols:
        return {"error": "No symbols provided"}

    symbol    = req.symbols[0].strip().upper()
    loop      = asyncio.get_event_loop()
    
    def _do_pipeline():
        simulator = request.app.state.simulator
        summary   = simulator.get_portfolio_summary()
        cur_pos   = simulator.positions.get(symbol, {})
        cur_shares = cur_pos.get("shares", 0)

        result = _run_agent_pipeline(symbol, summary, cur_shares)
        if "error" in result:
            return result

        decision = result.get("decision", {})
        action   = decision.get("action", "HOLD")

        trade_result = None
        if action in ("BUY", "SELL"):
            signal = {
                "action":           action,
                "stock_id":         symbol,
                "name":             result["name"],
                "current_price":    result["current_price"],
                "confidence":       decision.get("confidence", 0.0),
                "position_size_pct":decision.get("position_size_pct", 10),
                "stop_loss_price":  decision.get("stop_loss_price"),
                "take_profit_price":decision.get("take_profit_price"),
            }
            trade_result = simulator.execute_signal(signal)

        result["trade_result"] = trade_result
        return result

    return await loop.run_in_executor(_executor, _do_pipeline)


@router.post("/manual")
async def analyze_manual(req: AnalyzeRequest, request: Request):
    """
    四 Agent 深度分析（僅分析，不執行任何交易）。
    適合智慧選股頁面使用。
    """
    if not req.symbols:
        return {"error": "No symbols provided"}

    symbol = req.symbols[0].strip().upper()
    loop   = asyncio.get_event_loop()
    
    def _do_pipeline():
        simulator = request.app.state.simulator
        summary   = simulator.get_portfolio_summary()
        cur_pos   = simulator.positions.get(symbol, {})
        cur_shares = cur_pos.get("shares", 0)
        return _run_agent_pipeline(symbol, summary, cur_shares)

    return await loop.run_in_executor(_executor, _do_pipeline)
