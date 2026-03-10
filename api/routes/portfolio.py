"""
Legacy portfolio routes.
Delegate to V2 trading endpoints where possible.
"""

from fastapi import APIRouter, Request

from api.routes.trading import get_current_positions as v2_get_current_positions
from api.routes.trading import get_portfolio_summary as v2_get_portfolio_summary
from api.routes.trading import get_trade_history as v2_get_trade_history

router = APIRouter()


@router.get("/summary")
async def get_portfolio_summary(request: Request):
    data = await v2_get_portfolio_summary(request)
    positions = data.get("portfolio_v2", {}).get("positions", [])
    unrealized_pnl = round(sum(float(p.get("unrealized_pnl", 0) or 0) for p in positions), 2)
    return {
        "total_assets": round(data.get("total_assets", 0), 2),
        "available_cash": round(data.get("cash", 0), 2),
        "total_profit": round(data.get("total_profit", 0), 2),
        "total_profit_pct": round(data.get("total_profit_pct", 0), 2),
        "position_count": data.get("position_count", 0),
        "unrealized_pnl": unrealized_pnl,
    }


@router.get("/positions")
async def get_open_positions(request: Request):
    positions = await v2_get_current_positions(request)
    return {"count": len(positions), "positions": positions}


@router.get("/history")
async def get_trade_history(request: Request):
    trades = await v2_get_trade_history(request)
    trades_reversed = list(reversed(trades[-50:]))
    return {"count": len(trades_reversed), "history": trades_reversed}
