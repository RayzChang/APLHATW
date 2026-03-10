"""
系統設定 API
===========
提供前端 SettingsModal 讀取/更新後端設定，目前支援：
 - 模擬交易初始資金（需同時重設模擬器）
 - 模擬宇宙（觀察清單）
 - LINE 推播通知開關
 - 查看目前 API Key 狀態（不回傳實際 Key）
"""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel

router = APIRouter()


class SettingsUpdateRequest(BaseModel):
    initial_capital: float | None = None
    watchlist: list[str] | None = None
    reset_simulator: bool = False
    line_notify_enabled: bool | None = None


_executor = ThreadPoolExecutor(max_workers=4)


@router.get("/")
async def get_settings(request: Request):
    """取得目前系統設定（不含機密 Key）"""
    loop = asyncio.get_event_loop()

    def _fetch_settings():
        simulator = getattr(request.app.state, "simulator", None)
        summary = simulator.get_portfolio_summary() if simulator else {}

        from config.settings import AGENT_MODELS, SIMULATION_INITIAL_BALANCE, SIMULATION_UNIVERSE
        from core.notification.line_bot import get_enabled as line_enabled
        from core.notification.line_bot import is_configured as line_configured

        current_watchlist = getattr(request.app.state, "watchlist", list(SIMULATION_UNIVERSE))
        initial_capital = simulator.initial_capital if simulator else SIMULATION_INITIAL_BALANCE

        return {
            "initial_capital": initial_capital,
            "current_cash": round(summary.get("cash", initial_capital), 2),
            "current_assets": round(summary.get("total_assets", initial_capital), 2),
            "watchlist": list(current_watchlist),
            "agent_models": AGENT_MODELS,
            "has_finmind_token": bool(os.getenv("FINMIND_TOKEN", "")),
            "has_gemini_key": bool(os.getenv("GEMINI_API_KEY", "")),
            "has_line_token": line_configured(),
            "line_notify_enabled": line_enabled(),
        }

    return await loop.run_in_executor(_executor, _fetch_settings)


@router.post("/")
async def update_settings(req: SettingsUpdateRequest, request: Request):
    """
    更新系統設定。
    """
    loop = asyncio.get_event_loop()

    def _do_update():
        simulator = getattr(request.app.state, "simulator", None)
        changes: list[str] = []

        if req.initial_capital is not None:
            if req.initial_capital < 10_000:
                raise ValueError("initial_capital 最少 10,000 TWD")
            if simulator:
                simulator.initial_capital = req.initial_capital
            if simulator and req.reset_simulator:
                simulator.reset(new_capital=req.initial_capital)
                logger.info(f"Settings: 模擬器已重設，新資金 = {req.initial_capital:,.0f}")
                changes.append(f"模擬器已重設（初始資金 {req.initial_capital:,.0f} TWD）")
            else:
                changes.append(f"initial_capital 設定為 {req.initial_capital:,.0f}（下次重設時生效）")

        if req.watchlist is not None:
            watchlist = [item.strip().upper() for item in req.watchlist if item and item.strip()]
            if len(watchlist) == 0:
                raise ValueError("watchlist 不可為空")
            request.app.state.watchlist = watchlist
            changes.append(f"watchlist 更新為 {watchlist}")

        if req.line_notify_enabled is not None:
            from core.notification.line_bot import is_configured, set_enabled

            if req.line_notify_enabled and not is_configured():
                raise ValueError("LINE 推播尚未設定 — 請在 .env 填入 LINE_CHANNEL_ACCESS_TOKEN 和 LINE_USER_ID 後重啟後端")
            set_enabled(req.line_notify_enabled)
            state_text = "開啟" if req.line_notify_enabled else "關閉"
            changes.append(f"LINE 推播通知已{state_text}")

        return changes

    try:
        changes = await loop.run_in_executor(_executor, _do_update)
        if not changes:
            return {"success": True, "message": "無變更", "changes": []}
        return {"success": True, "message": "設定已更新", "changes": changes}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
