"""單股分析 API — 建議、掛單位置、能不能買、解釋"""

from fastapi import APIRouter
from pydantic import BaseModel

from core.analysis.stock_analysis import analyze_stock

router = APIRouter()


class AnalyzeRequest(BaseModel):
    symbols: list[str]


@router.post("/")
def analyze_stocks(req: AnalyzeRequest):
    """分析使用者輸入的標的，回傳建議、掛單位置、解釋"""
    results = []
    for symbol in req.symbols:
        symbol = symbol.strip().upper()
        if not symbol:
            continue
        r = analyze_stock(symbol)
        if r:
            results.append({
                "symbol": r.symbol,
                "name": r.name,
                "close": r.close,
                "change_pct": r.change_pct,
                "recommendation": r.recommendation,
                "suggested_buy": r.suggested_buy,
                "suggested_sell": r.suggested_sell,
                "explanation": r.explanation,
                "technical": r.technical,
                "fundamental": r.fundamental,
                "chip": r.chip,
            })
    return {"count": len(results), "results": results}

from core.data.news_fetcher import NewsFetcher
from core.agents.technical_analyst import TechnicalAnalystAgent
from core.agents.sentiment_analyst import SentimentAnalystAgent
from core.agents.risk_manager import RiskManagerAgent
from core.agents.chief_decision_maker import ChiefDecisionMakerAgent
from core.db.database import SessionLocal
from core.trading.engine import TradingEngine

@router.post("/agent")
async def analyze_with_agents(req: AnalyzeRequest):
    """多智能體分析流程 (Multi-Agent Pipeline)"""
    if not req.symbols:
        return {"error": "No symbols provided"}
        
    symbol = req.symbols[0].strip().upper()  # 目前先支援單檔深度分析
    
    # 1. 取得基本技術面與籌碼面
    r = analyze_stock(symbol)
    if not r:
        return {"error": f"無法取得 {symbol} 技術資料"}

    current_price = r.close
    name = r.name
    technical_data = {
        "technical": r.technical,
        "fundamental": r.fundamental,
        "chip": r.chip
    }
    
    # 2. 取得新聞與情緒
    fetcher = NewsFetcher()
    news_items = fetcher.fetch_latest_news(limit=5)
    
    db = SessionLocal()
    try:
        # 3. 取得真實投資組合
        trading_engine = TradingEngine(db)
        portfolio_obj = trading_engine.get_portfolio()
        from core.db.models import Position as DBPosition
        position_obj = db.query(DBPosition).filter(DBPosition.symbol == symbol).first()

        portfolio = {
            "total_assets": portfolio_obj.total_assets,
            "available_cash": portfolio_obj.available_cash,
            "current_position_size": position_obj.amount if position_obj else 0
        }
        
        # 4. 初始化 Agents
        tech_agent = TechnicalAnalystAgent()
        sent_agent = SentimentAnalystAgent()
        risk_agent = RiskManagerAgent()
        chief_agent = ChiefDecisionMakerAgent()
        
        # 5. 生成子報告
        tech_report = tech_agent.analyze(symbol, name, current_price, technical_data)
        sent_report = sent_agent.analyze(symbol, name, news_items)
        risk_report = risk_agent.analyze(symbol, name, current_price, portfolio)
        
        # 6. 最終決策
        decision = chief_agent.analyze(symbol, name, current_price, tech_report, sent_report, risk_report)
        
        # 7. 執行交易
        action = decision.get("action")
        if action in ["BUY", "SELL"]:
            # 將建議的百分比 (0-100) 轉換為實際股數 (1張=1000股)
            pct = decision.get("position_size_pct", 0) / 100.0
            
            if action == "BUY":
                # 用可用現金的 pct 換算能買多少股，無條件捨去至千 (只買整張)
                budget = portfolio_obj.available_cash * pct
                raw_shares = int(budget // current_price)
                amount = (raw_shares // 1000) * 1000
            else: # SELL
                # 賣出目前庫存的 pct，無條件捨去至千
                total_shares = position_obj.amount if position_obj else 0
                raw_shares = int(total_shares * pct)
                amount = (raw_shares // 1000) * 1000

            # 確保交易量有效 (>=1000) 才會觸發
            if amount >= 1000:
                trading_engine.execute_order(
                    symbol=symbol,
                    name=name,
                    action=action,
                    amount=amount,
                    price=current_price,
                    reason=decision.get("reasoning", ""),
                    stop_loss_price=decision.get("stop_loss_price"),
                    take_profit_price=decision.get("take_profit_price")
                )
    finally:
        db.close()
    
    return {
        "symbol": symbol,
        "name": name,
        "current_price": current_price,
        "reports": {
            "technical": tech_report,
            "sentiment": sent_report,
            "risk": risk_report
        },
        "decision": decision
    }
@router.post("/manual")
async def analyze_manual(req: AnalyzeRequest):
    """人工選股器分析流程 (僅分析，不執行交易)"""
    if not req.symbols:
        return {"error": "No symbols provided"}
        
    symbol = req.symbols[0].strip().upper()
    
    # 1. 取得基本技術面與籌碼面
    r = analyze_stock(symbol)
    if not r:
        return {"error": f"無法取得 {symbol} 技術資料"}

    current_price = r.close
    name = r.name
    technical_data = {
        "technical": r.technical,
        "fundamental": r.fundamental,
        "chip": r.chip
    }
    
    # 2. 取得新聞與情緒
    fetcher = NewsFetcher()
    news_items = fetcher.fetch_latest_news(limit=5)
    
    db = SessionLocal()
    try:
        trading_engine = TradingEngine(db)
        portfolio_obj = trading_engine.get_portfolio()
        from core.db.models import Position as DBPosition
        position_obj = db.query(DBPosition).filter(DBPosition.symbol == symbol).first()

        portfolio = {
            "total_assets": portfolio_obj.total_assets,
            "available_cash": portfolio_obj.available_cash,
            "current_position_size": position_obj.amount if position_obj else 0
        }
        
        # 4. 初始化 Agents
        tech_agent = TechnicalAnalystAgent()
        sent_agent = SentimentAnalystAgent()
        risk_agent = RiskManagerAgent()
        chief_agent = ChiefDecisionMakerAgent()
        
        # 5. 生成子報告
        tech_report = tech_agent.analyze(symbol, name, current_price, technical_data)
        sent_report = sent_agent.analyze(symbol, name, news_items)
        risk_report = risk_agent.analyze(symbol, name, current_price, portfolio)
        
        # 6. 最終決策
        decision = chief_agent.analyze(symbol, name, current_price, tech_report, sent_report, risk_report)
        
    finally:
        db.close()
    
    return {
        "symbol": symbol,
        "name": name,
        "current_price": current_price,
        "reports": {
            "technical": tech_report,
            "sentiment": sent_report,
            "risk": risk_report
        },
        "decision": decision
    }
