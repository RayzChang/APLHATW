from __future__ import annotations

from loguru import logger

from core.scheduler.shared import get_runtime_services


def job_check_simulation_stops():
    logger.debug("Scheduler [Check Stops]: Starting scan...")
    try:
        fetcher, simulator, _, _ = get_runtime_services()

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
            logger.info(f"Scheduler [Check Stops]: {len(actions)} risk action(s): {actions}")
            from core.notification.line_bot import notify_sell

            for act in actions:
                if act.get("action") == "SELL":
                    sid = act["stock_id"]
                    sell_trade = next(
                        (t for t in reversed(simulator.trade_history) if t.get("stock_id") == sid and t.get("type") == "SELL"),
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

