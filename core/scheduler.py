import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.data.news_fetcher import NewsFetcher
from loguru import logger

# Initialize a global scheduler instance
scheduler = AsyncIOScheduler()

def job_fetch_news():
    """定期抓取新聞並記錄情緒分析 (供未來的 Agent 使用)"""
    logger.info("Scheduler: Fetching latest news & sentiment...")
    try:
        fetcher = NewsFetcher()
        news_items = fetcher.fetch_latest_news(limit=10)
        # 這裡未來會將抓取下來的新聞存入資料庫 (DB) 供「市場情緒分析師 Agent」取用
        # 目前僅記錄日誌
        for idx, item in enumerate(news_items):
            logger.debug(f"News [{item.sentiment}]: {item.title}")
    except Exception as e:
        logger.error(f"Scheduler job_fetch_news failed: {e}")

from core.data.tw_data_fetcher import TWDataFetcher
from core.screener.stock_screener import run_screener
from core.agents.technical_analyst import TechnicalAnalystAgent
from core.agents.sentiment_analyst import SentimentAnalystAgent
from core.agents.risk_manager import RiskManagerAgent
from core.agents.chief_decision_maker import ChiefDecisionMakerAgent

def job_daily_market_scan():
    """每日盤後 (例: 15:30) 掃描全市場並由 AI 自動交易"""
    from api.routes.simulation import scan_state
    
    scan_state["is_scanning"] = True
    scan_state["current"] = 0
    scan_state["total"] = 0
    scan_state["message"] = "正在取得全市場股票清單..."
    
    logger.info("Scheduler: Starting daily full market scan...")
    try:
        from core.execution.trading_engine import TradingEngine
        from core.db.database import SessionLocal
        
        fetcher = TWDataFetcher()
        df_stocks = fetcher.get_stock_list("all")
        if df_stocks.empty:
            logger.error("Scheduler: failed to fetch stock list.")
            scan_state["message"] = "取得股票清單失敗"
            scan_state["is_scanning"] = False
            return

        symbols = df_stocks["stock_id"].tolist()
        logger.info(f"Scheduler: Scanning {len(symbols)} symbols...")
        scan_state["message"] = f"正在透過策略快篩 {len(symbols)} 檔股票..."

        # 這裡示範使用幾個常見策略過濾
        strategies = ["buy_score", "volume_surge"]
        # 注意: 實際執行全市場 2000 檔 API 請求可能會耗時過久，實務上可分批或使用本地資料庫快取
        # 這裡為了展示，取前 50 支，或可以在生產環境全跑
        shortlist_results = run_screener(symbols[:50], strategies, fetcher)
        
        buy_candidates = [r for r in shortlist_results if r.signal == "BUY"]
        logger.info(f"Scheduler: Found {len(buy_candidates)} candidates.")

        if not buy_candidates:
            scan_state["message"] = "無符合策略的標的"
            scan_state["is_scanning"] = False
            return

        tech_agent = TechnicalAnalystAgent()
        sent_agent = SentimentAnalystAgent()
        risk_agent = RiskManagerAgent()
        chief_agent = ChiefDecisionMakerAgent()

        db = SessionLocal()
        trading_engine = TradingEngine(db)

        scan_state["total"] = len(buy_candidates)
        scan_state["current"] = 0
        scan_state["message"] = "正在交由 AI 探員進行各股深度分析..."

        for idx, candidate in enumerate(buy_candidates):
            symbol = candidate.symbol
            scan_state["current"] = idx + 1
            scan_state["message"] = f"AI 探員分析中: {candidate.name} ({symbol}) [{idx+1}/{len(buy_candidates)}]"
            
            logger.info(f"Scheduler: AI analyzing {symbol}...")
            # 簡化分析
            tech_report = tech_agent.analyze(symbol, candidate.name, None)
            sent_report = sent_agent.analyze(symbol, list())
            risk_report = risk_agent.analyze(symbol, candidate.close)
            
            decision = chief_agent.analyze(
                symbol, candidate.name, candidate.close, 
                str(tech_report), str(sent_report), str(risk_report)
            )

            if decision.get("action") == "BUY" and decision.get("confidence", 0) > 0.7:
                amount = 1000 # 假設固定買 1 張
                trading_engine.execute_order(
                    symbol=symbol,
                    name=candidate.name,
                    action="BUY",
                    amount=amount,
                    price=candidate.close,
                    reason=f"AI Daily Scan: {decision.get('reasoning')}"
                )
                logger.info(f"Scheduler: Executed BUY order for {symbol}")
        
        scan_state["message"] = "全市場掃描與自動交易已完成"
        
    except Exception as e:
        logger.error(f"Scheduler job_daily_market_scan failed: {e}")
        scan_state["message"] = f"分析過程發生錯誤: {e}"
    finally:
        scan_state["is_scanning"] = False
        if 'db' in locals():
            db.close()

from core.risk.dynamic_stops import DynamicStopsEngine
from core.notifications.line_notify import LineNotifier
from core.db.database import SessionLocal
from core.db.models import Position as DBPosition
from core.risk.dynamic_stops import Position as LogicPosition
from core.trading.engine import TradingEngine

def job_check_simulation_stops():
    """定期檢查模擬交易的停損停利 (盤中每分鐘檢查)"""
    logger.debug("Scheduler [Check Stops]: Starting scan...")
    
    db = SessionLocal()
    try:
        trading_engine = TradingEngine(db)
        # 更新總資產市值
        trading_engine.evaluate_portfolio_value()
        
        # 讀取真實持倉
        db_positions = db.query(DBPosition).all()
        if not db_positions:
            return
            
        engine = DynamicStopsEngine(break_even_pct=3.0, trailing_stop_pct=5.0)
        notifier = LineNotifier()
        
        for db_pos in db_positions:
            # 轉換為邏輯用的 Position 結構
            pos = LogicPosition(
                symbol=db_pos.symbol,
                amount=db_pos.amount,
                entry_price=db_pos.entry_price,
                current_price=db_pos.current_price,
                high_price_since_entry=db_pos.high_price_since_entry,
                stop_loss_price=db_pos.stop_loss_price,
                take_profit_price=db_pos.take_profit_price
            )
            
            result = engine.evaluate_position(pos)
            
            if result.action_required:
                logger.info(f"Risk event for {pos.symbol}: {result.reason}")
                
                if result.action_type in ["STOP_LOSS", "TAKE_PROFIT"]:
                    # 執行引擎掛出賣出平倉單
                    success = trading_engine.execute_order(
                        symbol=db_pos.symbol, 
                        name=db_pos.name, 
                        action="SELL", 
                        amount=db_pos.amount, 
                        price=db_pos.current_price, 
                        reason=f"風控觸發: {result.reason}"
                    )
                    
                elif result.action_type == "UPDATE_STOP" and result.new_stop_price:
                    # 更新資料庫裡該筆訂單的 stop_loss_price
                    db_pos.stop_loss_price = result.new_stop_price
                    db.commit()
                    notifier.alert_trade(action=result.action_type, symbol=pos.symbol, price=result.new_stop_price, reason=result.reason)
    finally:
        db.close()

def init_scheduler():
    """初始化並註冊所有排程任務"""
    
    # 1. 新聞抓取 (每小時抓一次，例如 09:00 - 14:00 盤中每小時)
    scheduler.add_job(
        job_fetch_news,
        IntervalTrigger(minutes=60),
        id="fetch_news",
        name="Fetch news & sentiment periodically",
        replace_existing=True
    )

    # 2. 每日盤後自動掃描與交易 (例如每天 16:00 執行)
    scheduler.add_job(
        job_daily_market_scan,
        CronTrigger(day_of_week="mon-fri", hour=16, minute=0),
        id="daily_market_scan",
        name="Daily full market scan and AI auto-trading",
        replace_existing=True
    )
    
    # 3. 模擬交易停損/停利監控 (例如盤中每 1 分鐘檢查)
    # CronTrigger 範例：週一至週五的 09:00 到 13:30，每分鐘檢查
    scheduler.add_job(
        job_check_simulation_stops,
        CronTrigger(day_of_week="mon-fri", hour="9-13", minute="*"),
        id="check_simulation_stops",
        name="Monitor paper trading stops",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Global Background Scheduler Started.")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Global Background Scheduler Shutdown.")
