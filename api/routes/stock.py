"""
股票數據 API — 單股分析與即時報價
"""

from fastapi import APIRouter, Request, HTTPException

router = APIRouter()

@router.get("/analyze/{stock_id}")
async def analyze_stock_deep(stock_id: str, request: Request):
    """
    呼叫 Orchestrator 進行單股深度分析（技術、情緒、風控、決策）
    """
    orchestrator = request.app.state.orchestrator
    try:
        # 執行完整 AI 分析流程
        result = orchestrator.run_full_analysis(stock_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"找不到股票 {stock_id} 的分析資料")
        return result
    except Exception as e:
        import traceback
        print(f"Deep analysis error for {stock_id}: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"深度分析過程發生錯誤: {str(e)}")

@router.get("/quote/{stock_id}")
async def get_stock_quote(stock_id: str, request: Request):
    """
    取得單一股票即時報價 (TWSE MIS API)
    """
    fetcher = request.app.state.fetcher
    try:
        res = fetcher.fetch_realtime_quote(stock_id)
        if not res:
            raise HTTPException(status_code=404, detail=f"查無此股票行情: {stock_id}")
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"抓取行情失敗: {str(e)}")
