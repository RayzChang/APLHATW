"""
模擬交易 API — 投資組合管理與自動循環
"""

from fastapi import APIRouter, Request, BackgroundTasks

router = APIRouter()

# 全域掃描狀態 (供 scheduler 更新，前端輪詢)
scan_state = {
    "is_scanning": False,
    "current": 0,
    "total": 0,
    "message": ""
}

@router.get("/portfolio")
def get_portfolio_summary(request: Request):
    """取得模擬投資組合資產概覽"""
    simulator = request.app.state.simulator
    return simulator.get_portfolio_summary()

@router.post("/run_cycle")
async def run_analysis_cycle(background_tasks: BackgroundTasks):
    """
    手動啟動一次全市場掃描與 AI 自動交易循環。
    背景執行，不等待完成。
    """
    from core.scheduler import job_daily_market_scan
    
    if scan_state["is_scanning"]:
        return {"status": "error", "message": "全市場掃描已在進行中"}
        
    background_tasks.add_task(job_daily_market_scan)
    return {"status": "started", "message": "分析循環已啟動"}

@router.post("/reset")
def reset_simulation(request: Request):
    """清空模擬交易紀錄、部位與資產，恢復初始狀態"""
    simulator = request.app.state.simulator
    simulator.reset()
    return {"status": "ok", "message": "模擬帳戶已重置"}

@router.get("/trades")
def get_trade_history(request: Request):
    """取得完整交易歷史紀錄列表"""
    simulator = request.app.state.simulator
    return simulator.trade_history

@router.get("/positions")
def get_current_positions(request: Request):
    """取得當前持倉清單（含股數、均價等資訊）"""
    simulator = request.app.state.simulator
    # simulator.positions 是字典，轉換為列表方便前端呈現
    results = []
    for sid, data in simulator.positions.items():
        results.append({
            "stock_id": sid,
            **data
        })
    return results

@router.get("/scan/status")
def get_scan_status():
    """取得背景掃描的即時進度 (由 scheduler 更新)"""
    return scan_state
