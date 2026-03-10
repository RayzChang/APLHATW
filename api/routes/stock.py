"""
股票數據 API — 單股分析與即時報價
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Request, HTTPException

from api.routes.analysis import _run_analysis

_executor = ThreadPoolExecutor(max_workers=4)

router = APIRouter()

@router.get("/analyze/{stock_id}")
async def analyze_stock_deep(stock_id: str, request: Request):
    """
    呼叫 Orchestrator 進行單股深度分析（技術、情緒、風控、決策）
    """
    loop = asyncio.get_event_loop()
    
    def _run_blocking():
        return _run_analysis(request, stock_id, False)

    try:
        result = await loop.run_in_executor(_executor, _run_blocking)
        if not result:
            raise HTTPException(status_code=404, detail=f"找不到股票 {stock_id} 的分析資料")
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Deep analysis error for {stock_id}: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"深度分析過程發生錯誤: {str(e)}")

@router.get("/quote/{stock_id}")
async def get_stock_quote(stock_id: str, request: Request):
    """
    取得單一股票即時報價。
    盤中：TWSE MIS API 即時價。
    休市/週末：fallback 到 FinMind 最後一筆收盤價。
    """
    from datetime import datetime, timedelta
    loop = asyncio.get_event_loop()
    
    def _fetch_blocking():
        fetcher = request.app.state.fetcher

        # 先嘗試即時報價
        res = fetcher.fetch_realtime_quote(stock_id)
        if res:
            return res

        # 即時無資料（休市）→ 用 FinMind 最近 10 個交易日收盤價補足
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
            df = fetcher.fetch_klines(stock_id, start, end)
            if df is not None and not df.empty:
                last = df.iloc[-1]
                prev = df.iloc[-2] if len(df) >= 2 else last
                price = float(last["close"])
                prev_close = float(prev["close"])
                change = round(price - prev_close, 2)
                change_pct = round(change / prev_close * 100, 2) if prev_close else 0.0
                return {
                    "price": price,
                    "name": fetcher.get_symbol_name(stock_id),
                    "open": float(last.get("open", price)),
                    "high": float(last.get("high", price)),
                    "low": float(last.get("low", price)),
                    "volume": int(last.get("volume", 0)),
                    "change": change,
                    "change_pct": change_pct,
                    "yesterday_close": prev_close,
                    "is_realtime": False,
                    "note": "休市中，顯示最後收盤價",
                }
        except Exception:
            pass
        return None

    try:
        result = await loop.run_in_executor(_executor, _fetch_blocking)
        if result:
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"抓取行情失敗: {str(e)}")

    raise HTTPException(status_code=404, detail=f"查無此股票行情: {stock_id}")
