"""使用者自選清單 API — 儲存、取得、分析"""

from fastapi import APIRouter
from pydantic import BaseModel

from core.analysis.stock_analysis import analyze_stock
from config.settings import DEFAULT_WATCHLIST

router = APIRouter()

# 簡易記憶體儲存（實際可改用 DB）
_watchlist: list[str] = list(DEFAULT_WATCHLIST)


class WatchlistRequest(BaseModel):
    symbols: list[str]


@router.get("/")
def get_watchlist():
    """取得使用者自選清單"""
    return {"symbols": _watchlist}


@router.post("/")
def save_watchlist(req: WatchlistRequest):
    """儲存使用者自選清單"""
    global _watchlist
    _watchlist = [s.strip().upper() for s in req.symbols if s.strip()]
    return {"symbols": _watchlist}


@router.post("/analyze")
def analyze_watchlist():
    """分析自選清單內所有標的"""
    results = []
    for symbol in _watchlist:
        r = analyze_stock(symbol)
        if r:
            results.append({
                "symbol": r.symbol,
                "name": r.name,
                "close": r.close,
                "change_pct": r.change_pct,
                "recommendation": r.recommendation,
                "suggested_buy": r.suggested_buy,
                "suggested_sell": r.suggested_sell,
                "explanation": r.explanation,
                "technical": r.technical,
                "fundamental": r.fundamental,
                "chip": r.chip,
            })
    return {"count": len(results), "results": results}
