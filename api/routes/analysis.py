"""
V2 Analysis API
- GET  /symbol/{stock_id}  → 單股深度分析
- POST /manual            → 深度分析（不交易）
- POST /trade             → 深度分析後依訊號執行模擬交易
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

_executor = ThreadPoolExecutor(max_workers=4)

router = APIRouter()


class AnalysisRequest(BaseModel):
    symbols: list[str]


def _run_analysis(request: Request, stock_id: str, execute_trade: bool = False):
    simulator = request.app.state.simulator
    pipeline = request.app.state.analysis_pipeline

    summary = simulator.get_portfolio_summary()
    cur_pos = simulator.positions.get(stock_id, {})
    summary["current_position_size"] = cur_pos.get("shares", 0)

    analysis_result = pipeline.analyze_symbol(stock_id, portfolio=summary)
    result = analysis_result.to_legacy_payload()

    if execute_trade:
        signal = pipeline.build_trade_signal(analysis_result, source="MANUAL_ANALYSIS")
        if signal.action in ("BUY", "SELL"):
            result["trade_result"] = simulator.execute_signal(signal)
        else:
            result["trade_result"] = None

    return result


@router.get("/symbol/{stock_id}")
async def analyze_symbol(stock_id: str, request: Request):
    loop = asyncio.get_event_loop()

    try:
        result = await loop.run_in_executor(_executor, _run_analysis, request, stock_id, False)
        if not result:
            raise HTTPException(status_code=404, detail=f"找不到股票 {stock_id} 的分析資料")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析過程發生錯誤: {str(e)}")


@router.post("/manual")
async def analyze_manual(req: AnalysisRequest, request: Request):
    if not req.symbols:
        return {"error": "No symbols provided"}

    symbol = req.symbols[0].strip().upper()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _run_analysis, request, symbol, False)


@router.post("/trade")
async def analyze_and_trade(req: AnalysisRequest, request: Request):
    if not req.symbols:
        return {"error": "No symbols provided"}

    symbol = req.symbols[0].strip().upper()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _run_analysis, request, symbol, True)
