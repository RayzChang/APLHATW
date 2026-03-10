"""
AlphaTW 背景排程器
==================

任務清單：
1. job_fetch_news          — 每小時抓取市場新聞
2. job_daily_market_scan   — 盤中自動掃描全市場並由 AI 下單（9:10 / 12:30）
3. job_check_simulation_stops — 盤中每分鐘監控持倉停損/停利（9:00–13:30）

全市場掃描流程（兩層篩選）：
  第一層：yfinance 批量下載全部 TWSE+TPEX 普通股歷史 K 線
          → 計算技術指標，依評分排序，取評分 ≥ 1 的前 30 名
          → 此層免費，不消耗 Gemini / FinMind 配額
  第二層：對前 30 名候選股執行四個 AI Agent 精析（Gemini API）
          → 只有 AI 信心 ≥ 70% 且決策為 BUY，才實際下模擬單
"""

import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.data.news_fetcher import NewsFetcher
from loguru import logger

scheduler = AsyncIOScheduler()


# ─── 新聞抓取 ─────────────────────────────────────────────────────────────────

def job_fetch_news():
    """定期抓取新聞並記錄（供 Sentiment Agent 使用）"""
    logger.info("Scheduler: Fetching latest news...")
    try:
        fetcher = NewsFetcher()
        news_items = fetcher.fetch_latest_news(limit=10)
        for item in news_items:
            logger.debug(f"News [{item.sentiment}]: {item.title}")
    except Exception as e:
        logger.error(f"Scheduler job_fetch_news failed: {e}")


# ─── 全市場 AI 掃描與自動交易 ────────────────────────────────────────────────

from core.data.tw_data_fetcher import TWDataFetcher
from core.agents.technical_analyst import TechnicalAnalystAgent
from core.agents.sentiment_analyst import SentimentAnalystAgent
from core.agents.risk_manager import RiskManagerAgent
from core.agents.chief_decision_maker import ChiefDecisionMakerAgent


def job_daily_market_scan():
    """
    盤中全市場掃描與 AI 自動交易。

    第一層：yfinance 批量下載全部普通股歷史 K 線，技術指標評分，
            取評分 ≥ 1 的前 30 名候選（免費、不消耗 FinMind 配額）。
    第二層：對每個候選股執行四 Agent AI 精析，
            信心 ≥ 70% 且 BUY → 模擬下單。
    """
    from api.routes.simulation import scan_state

    # 防止重複執行
    if scan_state.get("is_scanning"):
        logger.warning("Scheduler: scan already running, skipping.")
        return

    scan_state.update({
        "is_scanning":       True,
        "current":           0,
        "total":             0,
        "message":           "正在初始化全市場掃描...",
        "stocks_screened":   0,
        "candidates_found":  0,
        "orders_placed":     0,
        "last_scan_summary": "",
    })

    logger.info("Scheduler: Starting full-market AI scan...")

    try:
        # ── 共用 app.state 實例（避免重複 FinMind 登入）─────────────────
        try:
            from api.app import _GLOBAL_APP_STATE
            fetcher   = _GLOBAL_APP_STATE.fetcher
            simulator = _GLOBAL_APP_STATE.simulator
        except Exception:
            fetcher = TWDataFetcher()
            from core.execution.simulator import TradeSimulator
            simulator = TradeSimulator()

        # ── 第一層 Step 1：取全市場股票清單（1 次 FinMind API）─────────
        scan_state["message"] = "從 FinMind 取得全市場上市/上櫃股票清單..."
        all_stocks = fetcher.get_all_stock_ids_with_market()

        if not all_stocks:
            scan_state["message"] = "取得股票清單失敗，掃描中止"
            return

        # 只保留 4 碼普通股（排除 ETF 00xxx）
        tradable_map: dict[str, str] = {}   # {yf_ticker: stock_id}
        for sid, mtype in all_stocks.items():
            if len(sid) == 4 and sid.isdigit() and not sid.startswith("0"):
                suffix = ".TW" if mtype == "twse" else ".TWO"
                tradable_map[f"{sid}{suffix}"] = sid

        logger.info(f"Scheduler: {len(tradable_map)} tradable common stocks")

        # ── 第一層 Step 2：yfinance 批量下載歷史 K 線────────────────────
        scan_state["message"] = (
            f"批量下載 {len(tradable_map)} 支普通股歷史 K 線（yfinance，免費）..."
        )

        from core.backtest.portfolio_backtest import _yf_batch_download
        from core.analysis.indicators import add_all_indicators, calc_buy_sell_score

        end_dt    = datetime.now()
        start_str = (end_dt - timedelta(days=120)).strftime("%Y-%m-%d")
        end_str   = end_dt.strftime("%Y-%m-%d")

        yf_data = _yf_batch_download(list(tradable_map.keys()), start_str, end_str)

        if not yf_data:
            scan_state["message"] = "無法下載股票資料，掃描中止"
            return

        scan_state["stocks_screened"] = len(yf_data)

        # ── 第一層 Step 3：計算技術指標，依評分排序 ─────────────────────
        scan_state["message"] = (
            f"計算 {len(yf_data)} 支股票技術指標，篩選買入候選..."
        )

        # {yf_ticker: (score, last_row_with_indicators)}
        scored: list[tuple[int, str, float, object]] = []

        for yf_ticker, raw_df in yf_data.items():
            sid = tradable_map.get(yf_ticker)
            if not sid:
                continue
            try:
                df = add_all_indicators(raw_df.copy())
                df = df.dropna(subset=["rsi", "macd_hist", "ma20"]).reset_index(drop=True)
                if df.empty:
                    continue
                last_row = df.iloc[-1]
                score    = calc_buy_sell_score(last_row)
                close    = float(last_row["close"])
                vol      = float(last_row.get("volume", 0))
                if close >= 10 and vol >= 500_000 and score >= 3:
                    scored.append((score, sid, close, last_row))
            except Exception as e:
                logger.debug(f"Indicator error {sid}: {e}")

        # 依分數降序排列，取前 30 名
        scored.sort(key=lambda x: x[0], reverse=True)
        top_candidates = scored[:30]

        scan_state["candidates_found"] = len(top_candidates)

        if not top_candidates:
            msg = (
                f"今日掃描 {len(yf_data)} 支股票，"
                f"無符合技術指標的標的（所有股票評分均 < 1），"
                f"市場可能整體偏空，不強行建倉。"
            )
            scan_state["message"]           = msg
            scan_state["last_scan_summary"] = msg
            scan_state["last_scan_time"]    = datetime.now().isoformat()
            logger.info(f"Scheduler: {msg}")
            return

        logger.info(
            f"Scheduler: 技術篩選完成！{len(top_candidates)} 個候選，AI 精析中..."
        )
        scan_state["message"] = (
            f"技術篩選完成！找到 {len(top_candidates)} 個候選標的，"
            f"AI 四探員精析中..."
        )
        scan_state["total"] = len(top_candidates)

        # ── 第二層：四 Agent AI 精析 ──────────────────────────────────
        tech_agent   = TechnicalAnalystAgent()
        sent_agent   = SentimentAnalystAgent(enable_search=True)
        risk_agent   = RiskManagerAgent()
        chief_agent  = ChiefDecisionMakerAgent()
        news_fetcher = NewsFetcher()

        orders_placed = 0

        for idx, (score, symbol, yf_close, last_row) in enumerate(top_candidates):
            scan_state["current"] = idx + 1
            stock_name = fetcher.get_symbol_name(symbol)
            scan_state["message"] = (
                f"AI 精析 {stock_name}({symbol}) "
                f"[{idx+1}/{len(top_candidates)}]，技術評分={score}"
            )
            logger.info(f"Scheduler: AI analyzing {symbol} score={score}")

            try:
                # 取即時報價（TWSE-MIS 優先，休市 fallback FinMind 最後收盤）
                quote = fetcher.fetch_realtime_quote(symbol)
                if not quote or quote.get("price", 0) <= 0:
                    logger.warning(f"Scheduler: no live price for {symbol}, skip")
                    continue
                live_price = quote["price"]

                # 從已下載的 yfinance 指標 Row 建立技術資料給 Tech Agent
                def _safe(key: str, default=0.0) -> float:
                    import pandas as pd
                    v = last_row.get(key, default)
                    if v is None or (isinstance(v, float) and __import__("math").isnan(v)):
                        return float(default)
                    return float(v)

                tech_data = {
                    "rsi":       _safe("rsi"),
                    "k":         _safe("stoch_k"),
                    "d":         _safe("stoch_d"),
                    "macd":      _safe("macd"),
                    "macd_hist": _safe("macd_hist"),
                    "ma5":       _safe("ma5"),
                    "ma20":      _safe("ma20"),
                    "ma60":      _safe("ma60"),
                    "bb_upper":  _safe("bb_upper"),
                    "bb_lower":  _safe("bb_lower"),
                    "bb_mid":    _safe("bb_mid"),
                    "atr":       _safe("atr"),
                    "volume":    _safe("volume"),
                    "close":     _safe("close", live_price),
                    "tech_score": score,
                    "daily_high": _safe("high", live_price * 1.01),
                    "daily_low":  _safe("low",  live_price * 0.99),
                }

                # 新聞（Sentiment Agent）
                news_items = news_fetcher.fetch_stock_news(symbol, stock_name, limit=3)

                # 組合投資組合資訊（Risk Agent）
                summary = simulator.get_portfolio_summary()
                portfolio_data = {
                    "total_assets":          summary.get("total_assets", 1_000_000),
                    "available_cash":        summary.get("cash", 1_000_000),
                    "current_position_size": simulator.positions.get(symbol, {}).get("shares", 0),
                    "suggested_sl":          round(live_price - 2 * tech_data["atr"], 2)
                                             if tech_data["atr"] > 0 else round(live_price * 0.95, 2),
                    "atr":                   tech_data["atr"],
                }

                # 四 Agent 串聯分析
                tech_report  = tech_agent.analyze(symbol, stock_name, live_price, tech_data)
                sent_report  = sent_agent.analyze(symbol, stock_name, news_items)
                risk_report  = risk_agent.analyze(symbol, stock_name, live_price, portfolio_data)
                decision     = chief_agent.analyze(
                    symbol, stock_name, live_price,
                    tech_report, sent_report, risk_report
                )
                
                # 簡單計算預估花費 (4個Agent約消耗總計 $0.01 美金 = $0.32 台幣)
                scan_state["daily_api_cost_twd"] = scan_state.get("daily_api_cost_twd", 0.0) + 0.32

                action     = decision.get("action", "HOLD")
                confidence = decision.get("confidence", 0)

                logger.info(
                    f"Scheduler: {symbol} → {action} "
                    f"confidence={confidence:.0%} "
                    f"[Cost: {scan_state['daily_api_cost_twd']:.2f} TWD]"
                )

                # 只有 BUY 且信心 ≥ 70% 才下單
                if action == "BUY" and confidence >= 0.7:
                    atr = tech_data["atr"]
                    sl  = round(live_price - 2 * atr, 2) if atr > 0 else round(live_price * 0.95, 2)
                    tp  = round(live_price + 3 * atr, 2) if atr > 0 else round(live_price * 1.10, 2)
                    signal = {
                        "action":            "BUY",
                        "stock_id":          symbol,
                        "name":              stock_name,
                        "current_price":     live_price,
                        "confidence":        confidence,
                        "position_size_pct": decision.get("position_size_pct", 10),
                        "stop_loss_price":   decision.get("stop_loss_price") or sl,
                        "take_profit_price": decision.get("take_profit_price") or tp,
                    }
                    result = simulator.execute_signal(signal)
                    if result and result.get("executed"):
                        orders_placed += 1
                        logger.info(f"Scheduler: BUY order placed → {symbol}")

                        from core.notification.line_bot import notify_buy
                        notify_buy(
                            stock_id=symbol,
                            name=stock_name,
                            price=live_price,
                            shares=result.get("shares", 0),
                            confidence=confidence,
                            stop_loss=signal["stop_loss_price"],
                            take_profit=signal["take_profit_price"],
                        )

            except Exception as inner_e:
                logger.warning(f"Scheduler: Error analyzing {symbol}: {inner_e}")

        # ── 完成 ────────────────────────────────────────────────────────
        summary_msg = (
            f"掃描完成！共掃描 {len(yf_data)} 支股票 → "
            f"技術篩選出 {len(top_candidates)} 個候選 → "
            f"AI 決定買入 {orders_placed} 檔"
        )
        scan_state["orders_placed"]     = orders_placed
        scan_state["last_scan_time"]    = datetime.now().isoformat()
        scan_state["last_scan_summary"] = summary_msg
        scan_state["message"]           = summary_msg
        logger.info(f"Scheduler: {summary_msg}")

        from core.notification.line_bot import notify_scan_complete
        notify_scan_complete(len(yf_data), len(top_candidates), orders_placed)

    except Exception as e:
        err_msg = f"掃描過程發生錯誤: {e}"
        logger.error(f"Scheduler job_daily_market_scan failed: {e}")
        scan_state["message"]           = err_msg
        scan_state["last_scan_time"]    = datetime.now().isoformat()
        scan_state["last_scan_summary"] = err_msg
    finally:
        scan_state["is_scanning"] = False


# ─── 停損/停利監控 ──────────────────────────────────────────────────────────

def job_check_simulation_stops():
    """
    盤中每分鐘監控停損/停利/追蹤止損。
    監控時段：週一至週五 09:00–13:30（涵蓋全部盤中時段）
    """
    logger.debug("Scheduler [Check Stops]: Starting scan...")
    try:
        simulator = None
        fetcher   = None
        try:
            from api.app import _GLOBAL_APP_STATE
            simulator = _GLOBAL_APP_STATE.simulator
            fetcher   = _GLOBAL_APP_STATE.fetcher
        except Exception:
            from core.execution.simulator import TradeSimulator
            simulator = TradeSimulator()
            fetcher   = TWDataFetcher()

        if not simulator.positions:
            logger.debug("Scheduler [Check Stops]: No open positions, skipping.")
            return

        prices = {}
        for sid in simulator.positions:
            try:
                quote = fetcher.fetch_realtime_quote(sid)
                if quote and quote.get("price", 0) > 0:
                    prices[sid] = quote["price"]
            except Exception as e:
                logger.warning(f"Scheduler [Check Stops]: Cannot fetch price {sid}: {e}")

        if not prices:
            return

        actions = simulator.check_risk_management(prices)
        if actions:
            logger.info(
                f"Scheduler [Check Stops]: {len(actions)} risk action(s): {actions}"
            )
            from core.notification.line_bot import notify_sell
            for act in actions:
                if act.get("action") == "SELL":
                    sid = act["stock_id"]
                    sell_trade = next(
                        (t for t in reversed(simulator.trade_history)
                         if t.get("stock_id") == sid and t.get("type") == "SELL"),
                        None,
                    )
                    if sell_trade:
                        notify_sell(
                            stock_id=sid,
                            name=sell_trade.get("name", sid),
                            price=act.get("price", 0),
                            shares=sell_trade.get("shares", 0),
                            reason=act.get("reason", "風控觸發"),
                            pnl=sell_trade.get("pnl", 0),
                            pnl_pct=sell_trade.get("pnl_pct", 0),
                        )
        else:
            logger.debug("Scheduler [Check Stops]: All positions healthy.")
    except Exception as e:
        logger.error(f"Scheduler job_check_simulation_stops failed: {e}")


# ─── 無間斷全市場掃描迴圈 ────────────────────────────────────────────────────────

import asyncio

async def continuous_market_scan_loop():
    """
    無間斷全市場掃描背景迴圈。
    只要前端開啟 auto_scan_enabled，就在開盤時間內不斷執行掃描，
    每次掃描完成後冷卻 15 分鐘。
    """
    from api.routes.simulation import scan_state
    
    logger.info("Scheduler: Continuous scan loop started waiting in background...")
    
    while True:
        try:
            # 1. 檢查是否啟用
            if not scan_state.get("auto_scan_enabled", False):
                scan_state["market_status"] = "WAITING"
                await asyncio.sleep(5)
                continue
                
            # 2. 判斷是否為台股開盤時間：週一到週五 09:00 - 13:30
            now = datetime.now()
            is_weekday = now.weekday() < 5  # 0-4 is Mon-Fri
            
            # 將時間轉換為分鐘數方便比較
            current_minutes = now.hour * 60 + now.minute
            open_minutes = 9 * 60        # 09:00
            close_minutes = 13 * 60 + 30 # 13:30
            
            is_open = is_weekday and (open_minutes <= current_minutes <= close_minutes)
            
            if not is_open:
                scan_state["market_status"] = "CLOSED"
                scan_state["message"] = "非交易時間，待機中..."
                await asyncio.sleep(60) # 休息一分鐘再確認
                continue
                
            # --- 進入開盤時間且已啟用 ---
            scan_state["market_status"] = "OPEN"
            
            # 確認沒有別的掃描正在進行
            if not scan_state.get("is_scanning", False):
                logger.info("Scheduler [Continuous]: Triggering market scan...")
                # 執行原本的單次掃描邏輯（會自動更新各種狀態）
                try:
                    import anyio.to_thread
                    # 使用 anyio 的 run_sync 避免阻塞並保留 anyio backend context (修復 NoEventLoopError)
                    await anyio.to_thread.run_sync(job_daily_market_scan)
                except Exception as e:
                    logger.error(f"Continuous scan error: {e}")
                    
                # 3. 掃描完成後冷卻 15 分鐘
                scan_state["message"] = "掃描完成。冷卻中 (倒數 15 分鐘)..."
                logger.info("Scheduler [Continuous]: Scan finished. Cooling down for 15 minutes...")
                
                # 分段倒數，以便隨時響應停止指令
                for i in range(15 * 60):
                    if not scan_state.get("auto_scan_enabled", False):
                        break
                    if i % 60 == 0:
                        mins_left = 15 - (i // 60)
                        scan_state["message"] = f"冷卻中 (倒數 {mins_left} 分鐘)..."
                    await asyncio.sleep(1)
            else:
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info("Scheduler: Continuous loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Scheduler [Continuous] outer loop error: {e}")
            await asyncio.sleep(10)


# ─── 初始化 ─────────────────────────────────────────────────────────────────

def init_scheduler():
    """初始化並啟動所有排程任務"""

    # 1. 新聞抓取（每小時一次）
    scheduler.add_job(
        job_fetch_news,
        IntervalTrigger(minutes=60),
        id="fetch_news",
        name="每小時抓取新聞",
        replace_existing=True,
    )

    # 2. 全市場 AI 掃描
    #    09:10 — 開盤後確認方向，建立上午部位
    #    12:30 — 下午盤前再掃一次，補充/調整部位
    for hour, minute, jid in [(9, 10, "scan_morning"), (12, 30, "scan_afternoon")]:
        scheduler.add_job(
            job_daily_market_scan,
            CronTrigger(day_of_week="mon-fri", hour=hour, minute=minute),
            id=jid,
            name=f"全市場 AI 掃描 {hour:02d}:{minute:02d}",
            replace_existing=True,
        )

    # 3. 停損/停利監控（盤中每分鐘，09:00–13:30）
    scheduler.add_job(
        job_check_simulation_stops,
        CronTrigger(
            day_of_week="mon-fri",
            hour="9-12",
            minute="*",
        ),
        id="check_simulation_stops",
        name="盤中停損/停利監控",
        replace_existing=True,
    )
    scheduler.add_job(
        job_check_simulation_stops,
        CronTrigger(
            day_of_week="mon-fri",
            hour=13,
            minute="0-30",
        ),
        id="check_simulation_stops_close",
        name="收盤前停損/停利監控 13:00–13:30",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Global Background Scheduler Started.")



def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Global Background Scheduler Shutdown.")


