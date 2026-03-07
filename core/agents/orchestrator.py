import datetime
import json
from loguru import logger

from core.agents.technical_analyst import TechnicalAnalystAgent
from core.agents.sentiment_analyst import SentimentAnalystAgent
from core.agents.risk_manager import RiskManagerAgent
from core.agents.chief_decision_maker import ChiefDecisionMakerAgent
from core.data.tw_data_fetcher import TWDataFetcher
from core.risk.sl_tp_calculator import SLTPCalculator

class TradingOrchestrator:
    """
    交易編排器，負責協調各個 Agent 與資料抓取器，執行完整的股票分析流程。
    """

    def __init__(self):
        logger.info("Initializing TradingOrchestrator...")
        
        # 初始化各個 Agent，現在預設會從 settings.py 讀取模型與溫度
        self.technical_agent = TechnicalAnalystAgent()
        self.sentiment_agent = SentimentAnalystAgent(enable_search=True)
        self.risk_agent = RiskManagerAgent()
        self.chief_agent = ChiefDecisionMakerAgent()
        
        # 初始化工具
        self.fetcher = TWDataFetcher()
        self.risk_calc = SLTPCalculator()

    def run_full_analysis(self, stock_id: str) -> dict:
        """
        執行完整的交易分析流程。
        """
        try:
            logger.info(f"Step 1: Fetching realtime quote for {stock_id}...")
            realtime = self.fetcher.fetch_realtime_quote(stock_id)
            if not realtime or "price" not in realtime:
                logger.warning(f"Failed to fetch realtime quote for {stock_id}")
                return {"error": "無法取得即時報價"}
                
            current_price = realtime["price"]
            name = realtime.get("name", stock_id)
            
            logger.info(f"Step 2: Fetching 90 days klines for {stock_id}...")
            start_date = (datetime.datetime.now() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
            kline_df = self.fetcher.fetch_stock_daily(stock_id, start_date)
            if kline_df.empty:
                logger.warning(f"No kline data found for {stock_id}")
                return {"error": "無法取得 K 線資料"}

            logger.info("Step 3: Calculating risk metrics (ATR, SL, TP, BE, Swings)...")
            atr = self.risk_calc.calculate_atr(kline_df)
            atr_stop = self.risk_calc.calculate_atr_stop_loss(current_price, atr, multiplier=2.0)
            swing_low, swing_high = self.risk_calc.get_swing_points(kline_df, lookback=20)
            fibonacci_tp = self.risk_calc.calculate_fibonacci_tp(current_price, swing_low, swing_high, atr, level=0.618)
            breakeven_price = self.risk_calc.calculate_breakeven_stop(current_price)

            logger.info("Step 4: Calling analysis agents sequentially...")
            
            # 1. Technical Analysis
            # 適配 TechnicalAnalystAgent.analyze(symbol, name, current_price, technical_data)
            tech_data = {
                "atr": atr,
                "swing_high": swing_high,
                "swing_low": swing_low,
                "daily_high": float(kline_df['high'].iloc[-1]),
                "daily_low": float(kline_df['low'].iloc[-1]),
                "daily_close": float(kline_df['close'].iloc[-1]),
                "volume": int(kline_df['volume'].iloc[-1])
            }
            technical_report = self.technical_agent.analyze(stock_id, name, current_price, tech_data)
            
            # 2. Sentiment Analysis
            # 適配 SentimentAnalystAgent.analyze(symbol, name, news_items)
            # 這裡暫時傳入空列表，因為 Orchestrator 流程中未提及抓新聞，且 SA 會處理 enable_search 下的自主搜尋
            sentiment_report = self.sentiment_agent.analyze(stock_id, name, [])
            
            # 3. Risk Management
            # 適配 RiskManagerAgent.analyze(symbol, name, current_price, portfolio)
            mock_portfolio = {
                "total_assets": 1000000, 
                "available_cash": 1000000, 
                "current_position_size": 0,
                "suggested_sl": atr_stop,
                "atr": atr
            }
            risk_report = self.risk_agent.analyze(stock_id, name, current_price, mock_portfolio)

            logger.info("Step 5: Generating final decision with ChiefDecisionMaker...")
            
            # 最終防呆檢查：確保 TP 與 SL 位於現價的合理側
            if fibonacci_tp <= current_price:
                fibonacci_tp = round(current_price * 1.05, 2)
            if atr_stop >= current_price:
                atr_stop = round(current_price * 0.95, 2)

            # 適配 ChiefDecisionMakerAgent.analyze(symbol, name, current_price, tech_report, sent_report, risk_report)
            decision = self.chief_agent.analyze(
                stock_id, name, current_price, 
                technical_report, sentiment_report, risk_report
            )
            
            # 注入程式計算的 TP/SL
            decision["take_profit_price"] = fibonacci_tp
            decision["stop_loss_price"] = atr_stop

            logger.info(f"Step 6: Analysis complete for {stock_id}.")
            return {
                "symbol": stock_id,
                "stock_id": stock_id,
                "name": name,
                "current_price": current_price,
                "decision": {
                    "action": decision.get("action", "HOLD"),
                    "confidence": decision.get("confidence", 0.0),
                    "reasoning": decision.get("reasoning", ""),
                    "take_profit_price": decision.get("take_profit_price"),
                    "stop_loss_price": decision.get("stop_loss_price"),
                    "position_size_pct": decision.get("position_size_pct", 0)
                },
                "atr": atr,
                "technical_report": technical_report,
                "sentiment_report": sentiment_report,
                "risk_report": risk_report,
                "timestamp": datetime.datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Orchestrator Error analyzing {stock_id}: {e}")
            return {"error": str(e)}
