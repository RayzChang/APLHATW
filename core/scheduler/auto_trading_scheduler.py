from __future__ import annotations

import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from core.scheduler.market_scan_job import job_daily_market_scan
from core.scheduler.risk_monitor_job import job_check_simulation_stops
from core.scheduler.shared import job_fetch_news

scheduler = AsyncIOScheduler()


async def continuous_market_scan_loop():
    from api.routes.simulation import scan_state

    logger.info("Scheduler: Continuous scan loop started waiting in background...")

    while True:
        try:
            if not scan_state.get("auto_scan_enabled", False):
                scan_state["market_status"] = "WAITING"
                await asyncio.sleep(5)
                continue

            now = datetime.now()
            is_weekday = now.weekday() < 5
            current_minutes = now.hour * 60 + now.minute
            open_minutes = 9 * 60
            close_minutes = 13 * 60 + 30
            is_open = is_weekday and (open_minutes <= current_minutes <= close_minutes)

            if not is_open:
                scan_state["market_status"] = "CLOSED"
                scan_state["message"] = "非交易時間，待機中..."
                await asyncio.sleep(60)
                continue

            scan_state["market_status"] = "OPEN"

            if not scan_state.get("is_scanning", False):
                logger.info("Scheduler [Continuous]: Triggering market scan...")
                try:
                    import anyio.to_thread

                    await anyio.to_thread.run_sync(job_daily_market_scan)
                except Exception as e:
                    logger.error(f"Continuous scan error: {e}")

                scan_state["message"] = "掃描完成。冷卻中 (倒數 15 分鐘)..."
                logger.info("Scheduler [Continuous]: Scan finished. Cooling down for 15 minutes...")

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


def init_scheduler():
    scheduler.add_job(
        job_fetch_news,
        IntervalTrigger(minutes=60),
        id="fetch_news",
        name="每小時抓取新聞",
        replace_existing=True,
    )

    for hour, minute, jid in [(9, 10, "scan_morning"), (12, 30, "scan_afternoon")]:
        scheduler.add_job(
            job_daily_market_scan,
            CronTrigger(day_of_week="mon-fri", hour=hour, minute=minute),
            id=jid,
            name=f"全市場 AI 掃描 {hour:02d}:{minute:02d}",
            replace_existing=True,
        )

    scheduler.add_job(
        job_check_simulation_stops,
        CronTrigger(day_of_week="mon-fri", hour="9-12", minute="*"),
        id="check_simulation_stops",
        name="盤中停損/停利監控",
        replace_existing=True,
    )
    scheduler.add_job(
        job_check_simulation_stops,
        CronTrigger(day_of_week="mon-fri", hour=13, minute="0-30"),
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

