"""回測 API"""

from fastapi import APIRouter
from pydantic import BaseModel

from core.backtest.strategy_backtest import run_backtest
from config.settings import DEFAULT_WATCHLIST

router = APIRouter()


class BacktestRequest(BaseModel):
    symbols: list[str] | None = None
    strategy_id: str
    months: int = 6


@router.post("/run")
def run_backtest_api(req: BacktestRequest):
    symbols = req.symbols or DEFAULT_WATCHLIST
    results = run_backtest(symbols, req.strategy_id, req.months)
    return {
        "count": len(results),
        "results": [
            {
                "symbol": r.symbol,
                "name": r.name,
                "close": r.close,
                "total_return": r.total_return,
                "win_rate": r.win_rate,
                "trade_count": r.trade_count,
            }
            for r in results
        ],
    }
