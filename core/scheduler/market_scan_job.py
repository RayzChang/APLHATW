from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger

from core.scheduler.shared import get_runtime_services


def job_daily_market_scan():
    from api.routes.simulation import scan_state

    if scan_state.get("is_scanning"):
        logger.warning("Scheduler: scan already running, skipping.")
        return

    scan_state.update(
        {
            "is_scanning": True,
            "current": 0,
            "total": 0,
            "message": "正在初始化全市場掃描...",
            "stocks_screened": 0,
            "candidates_found": 0,
            "orders_placed": 0,
            "last_scan_summary": "",
        }
    )

    logger.info("Scheduler: Starting full-market AI scan...")

    try:
        fetcher, simulator, analysis_pipeline, screening_service = get_runtime_services()

        scan_state["message"] = "從 FinMind 取得全市場上市/上櫃股票清單..."
        all_stocks = fetcher.get_all_stock_ids_with_market()
        if not all_stocks:
            scan_state["message"] = "取得股票清單失敗，掃描中止"
            return

        tradable_map: dict[str, str] = {}
        for sid, mtype in all_stocks.items():
            if len(sid) == 4 and sid.isdigit() and not sid.startswith("0"):
                suffix = ".TW" if mtype == "twse" else ".TWO"
                tradable_map[f"{sid}{suffix}"] = sid

        logger.info(f"Scheduler: {len(tradable_map)} tradable common stocks")

        scan_state["message"] = f"批量下載 {len(tradable_map)} 支普通股歷史 K 線（yfinance，免費）..."
        from core.backtest.portfolio_backtest import _yf_batch_download

        end_dt = datetime.now()
        start_str = (end_dt - timedelta(days=120)).strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")

        yf_data = _yf_batch_download(list(tradable_map.keys()), start_str, end_str)
        if not yf_data:
            scan_state["message"] = "無法下載股票資料，掃描中止"
            return

        scan_state["stocks_screened"] = len(yf_data)
        scan_state["message"] = f"計算 {len(yf_data)} 支股票技術指標，篩選買入候選..."

        top_candidates = screening_service.rank_market_data(yf_data, tradable_map, top_n=30, min_score=3)
        scan_state["candidates_found"] = len(top_candidates)

        if not top_candidates:
            msg = (
                f"今日掃描 {len(yf_data)} 支股票，"
                f"無符合技術指標的標的（所有股票評分均 < 1），"
                f"市場可能整體偏空，不強行建倉。"
            )
            scan_state["message"] = msg
            scan_state["last_scan_summary"] = msg
            scan_state["last_scan_time"] = datetime.now().isoformat()
            logger.info(f"Scheduler: {msg}")
            return

        logger.info(f"Scheduler: 技術篩選完成！{len(top_candidates)} 個候選，AI 精析中...")
        scan_state["message"] = f"技術篩選完成！找到 {len(top_candidates)} 個候選標的，AI 四探員精析中..."
        scan_state["total"] = len(top_candidates)

        orders_placed = 0
        for idx, candidate in enumerate(top_candidates):
            symbol = candidate.symbol
            stock_name = candidate.name or fetcher.get_symbol_name(symbol)
            scan_state["current"] = idx + 1
            scan_state["message"] = f"AI 精析 {stock_name}({symbol}) [{idx+1}/{len(top_candidates)}]，技術評分={candidate.score}"
            logger.info(f"Scheduler: AI analyzing {symbol} score={candidate.score}")

            try:
                summary = simulator.get_portfolio_summary()
                summary["current_position_size"] = simulator.positions.get(symbol, {}).get("shares", 0)
                analysis_result = analysis_pipeline.analyze_symbol(symbol, portfolio=summary)
                scan_state["daily_api_cost_twd"] = scan_state.get("daily_api_cost_twd", 0.0) + 0.32

                signal = analysis_pipeline.build_trade_signal(analysis_result, source="AUTO_SCAN")
                logger.info(
                    f"Scheduler: {symbol} → {signal.action} confidence={signal.confidence:.0%} "
                    f"[Cost: {scan_state['daily_api_cost_twd']:.2f} TWD]"
                )

                if signal.action == "BUY" and signal.confidence >= 0.7:
                    result = simulator.execute_signal(signal)
                    if result and result.get("executed"):
                        orders_placed += 1
                        logger.info(f"Scheduler: BUY order placed → {symbol}")
                        from core.notification.line_bot import notify_buy

                        notify_buy(
                            stock_id=symbol,
                            name=stock_name,
                            price=signal.current_price,
                            shares=result.get("shares", 0),
                            confidence=signal.confidence,
                            stop_loss=signal.stop_loss_price,
                            take_profit=signal.take_profit_price,
                        )
            except Exception as inner_e:
                logger.warning(f"Scheduler: Error analyzing {symbol}: {inner_e}")

        summary_msg = (
            f"掃描完成！共掃描 {len(yf_data)} 支股票 → "
            f"技術篩選出 {len(top_candidates)} 個候選 → AI 決定買入 {orders_placed} 檔"
        )
        scan_state["orders_placed"] = orders_placed
        scan_state["last_scan_time"] = datetime.now().isoformat()
        scan_state["last_scan_summary"] = summary_msg
        scan_state["message"] = summary_msg
        logger.info(f"Scheduler: {summary_msg}")

        from core.notification.line_bot import notify_scan_complete

        notify_scan_complete(len(yf_data), len(top_candidates), orders_placed)

    except Exception as e:
        err_msg = f"掃描過程發生錯誤: {e}"
        logger.error(f"Scheduler job_daily_market_scan failed: {e}")
        scan_state["message"] = err_msg
        scan_state["last_scan_time"] = datetime.now().isoformat()
        scan_state["last_scan_summary"] = err_msg
    finally:
        scan_state["is_scanning"] = False

