"""選股器 API"""

from fastapi import APIRouter
from pydantic import BaseModel

from core.screener.stock_screener import run_screener
from config.settings import DEFAULT_WATCHLIST, FINMIND_TOKEN

router = APIRouter()


class ScreenerRequest(BaseModel):
    symbols: list[str] | None = None
    strategies: list[str]


@router.post("/run")
def run_screener_api(req: ScreenerRequest):
    symbols = req.symbols or DEFAULT_WATCHLIST
    results = run_screener(symbols, req.strategies)
    out = {
        "count": len(results),
        "results": [
            {
                "symbol": r.symbol,
                "name": r.name,
                "close": r.close,
                "change_pct": r.change_pct,
                "signal": r.signal,
                "strategy_id": r.strategy_id,
                "strategy_name": r.strategy_name,
            }
            for r in results
        ],
    }
    if len(results) == 0 and symbols and not (FINMIND_TOKEN or "").strip():
        out["hint"] = "請在專案 .env 設定 FINMIND_TOKEN（至 https://finmindtrade.com/ 申請）才能取得行情資料。"
    return out
