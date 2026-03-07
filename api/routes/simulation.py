"""模擬交易 API"""

from fastapi import APIRouter
from pydantic import BaseModel

from core.execution.simulation_engine import SimulationEngine
from database.db_manager import DatabaseManager
from config.settings import DEFAULT_WATCHLIST

router = APIRouter()
db = DatabaseManager()


class SimulationRequest(BaseModel):
    symbols: list[str] | None = None
    strategies: list[str] | None = None
    days: int = 5
    initial_balance: float | None = None  # 可自訂金額，如 50 萬、100 萬


@router.post("/run")
def run_simulation_api(req: SimulationRequest):
    from config.settings import SIMULATION_INITIAL_BALANCE
    amount = req.initial_balance or SIMULATION_INITIAL_BALANCE
    engine = SimulationEngine(db)
    result = engine.run_simulation(
        symbols=req.symbols or DEFAULT_WATCHLIST[:30],
        strategies=req.strategies,
        days=req.days,
        initial_balance=amount,
    )
    return result


@router.get("/state")
def get_simulation_state():
    engine = SimulationEngine(db)
    state = db.get_simulation_state()
    open_trades = db.get_open_trades()
    return {
        "balance": engine.get_balance(),
        "state": state,
        "open_trades_count": len(open_trades),
    }


@router.get("/trades")
def get_trades():
    trades = db.get_open_trades()
    return {"trades": trades}


# 全域掃描狀態
scan_state = {
    "is_scanning": False,
    "current": 0,
    "total": 0,
    "message": ""
}

@router.post("/scan")
def trigger_manual_scan():
    """手動觸發每日全市場掃描與自動交易"""
    from core.scheduler import job_daily_market_scan
    import threading
    
    if scan_state["is_scanning"]:
        return {"ok": False, "message": "全市場掃描已經在進行中，請稍後重試"}
        
    # 在背景非同步執行以避免卡住 HTTP 請求
    t = threading.Thread(target=job_daily_market_scan)
    t.start()
    return {"ok": True, "message": "已成功在背景啟動全市場掃描"}

@router.get("/scan/status")
def get_scan_status():
    """取得全市場掃描與 AI 分析的即時進度"""
    return scan_state


@router.post("/reset")
def reset_simulation():
    """清空模擬交易資料庫與庫存，恢復初始資金"""
    from core.db.database import SessionLocal, engine, Base
    from core.db.models import Portfolio, Position, TradeHistory
    from config.settings import SIMULATION_INITIAL_BALANCE
    
    session = SessionLocal()
    try:
        session.query(Position).delete()
        session.query(TradeHistory).delete()
        session.query(Portfolio).delete()
        
        portfolio = Portfolio(
            total_assets=SIMULATION_INITIAL_BALANCE,
            available_cash=SIMULATION_INITIAL_BALANCE
        )
        session.add(portfolio)
        session.commit()
    finally:
        session.close()
    
    return {"ok": True, "message": "模擬庫存已清空，資金已重置"}
