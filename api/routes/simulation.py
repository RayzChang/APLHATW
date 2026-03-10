"""
Legacy simulation routes.
Keep old endpoints for frontend compatibility, delegate logic to V2 trading routes.
"""

from fastapi import APIRouter, BackgroundTasks, Request

from api.routes.trading import (
    check_stops as v2_check_stops,
    export_trades_csv as v2_export_trades_csv,
    get_current_positions as v2_get_current_positions,
    get_portfolio_summary as v2_get_portfolio_summary,
    get_scan_status as v2_get_scan_status,
    get_trade_history as v2_get_trade_history,
    reset_simulation as v2_reset_simulation,
    run_analysis_cycle as v2_run_analysis_cycle,
    toggle_auto_scan as v2_toggle_auto_scan,
)

router = APIRouter()

scan_state = {
    "is_scanning": False,
    "current": 0,
    "total": 0,
    "message": "待機中",
    "auto_scan_enabled": False,
    "market_status": "WAITING",
    "daily_api_cost_twd": 0.0,
    "last_scan_time": None,
    "last_scan_summary": "",
    "stocks_screened": 0,
    "candidates_found": 0,
    "orders_placed": 0,
    "no_trade_streak": 0,
    "adaptive_mode": "STRICT",
    "adaptive_thresholds": {
        "min_confidence": 0.7,
        "min_risk_reward": 1.5,
        "max_position_pct": 20.0,
    },
}


@router.get("/portfolio")
async def get_portfolio_summary(request: Request):
    return await v2_get_portfolio_summary(request)


@router.post("/check_stops")
async def check_stops(request: Request):
    return v2_check_stops(request)


@router.post("/toggle_auto_scan")
async def toggle_auto_scan():
    return v2_toggle_auto_scan()


@router.post("/run_cycle")
async def run_analysis_cycle(background_tasks: BackgroundTasks):
    return await v2_run_analysis_cycle(background_tasks)


@router.post("/reset")
async def reset_simulation(request: Request):
    return v2_reset_simulation(request)


@router.get("/trades")
async def get_trade_history(request: Request):
    return await v2_get_trade_history(request)


@router.get("/positions")
async def get_current_positions(request: Request):
    return await v2_get_current_positions(request)


@router.get("/trades/export")
async def export_trades_csv(request: Request):
    return v2_export_trades_csv(request)


@router.get("/scan/status")
async def get_scan_status(request: Request):
    return await v2_get_scan_status(request)
