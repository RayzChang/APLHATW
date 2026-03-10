"""
Legacy analyze routes.
Keep existing endpoints, but delegate deep analysis work to V2 analysis routes.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request
from pydantic import BaseModel

from api.routes.analysis import analyze_and_trade as v2_analyze_and_trade
from api.routes.analysis import analyze_manual as v2_analyze_manual
from core.analysis.stock_analysis import analyze_stock

_executor = ThreadPoolExecutor(max_workers=4)

router = APIRouter()


class AnalyzeRequest(BaseModel):
    symbols: list[str]


@router.post("/")
async def analyze_stocks(req: AnalyzeRequest):
    loop = asyncio.get_event_loop()

    def _run_batch():
        results = []
        for symbol in req.symbols:
            symbol = symbol.strip().upper()
            if not symbol:
                continue
            r = analyze_stock(symbol)
            if r:
                results.append(
                    {
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
                        "patterns": r.patterns,
                    }
                )
        return results

    results = await loop.run_in_executor(_executor, _run_batch)
    return {"count": len(results), "results": results}


@router.post("/manual")
async def analyze_manual(req: AnalyzeRequest, request: Request):
    return await v2_analyze_manual(req, request)


@router.post("/agent")
async def analyze_with_agents(req: AnalyzeRequest, request: Request):
    return await v2_analyze_and_trade(req, request)
