from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.db.database import get_db
from core.db.models import Portfolio, Position, TradeHistory
from core.trading.engine import TradingEngine

router = APIRouter()

@router.get("/summary")
def get_portfolio_summary(db: Session = Depends(get_db)):
    """取得帳戶總資產、可用餘額、以及計算獲利狀態"""
    engine = TradingEngine(db)
    engine.evaluate_portfolio_value() # 強制更新一次總資產
    
    portfolio = engine.get_portfolio()
    
    # 這裡先假定初始資產是常數，未來可在 settings 統一讀取，計算總獲利
    from config.settings import SIMULATION_INITIAL_BALANCE
    total_profit = portfolio.total_assets - SIMULATION_INITIAL_BALANCE
    profit_pct = (total_profit / SIMULATION_INITIAL_BALANCE) * 100

    # 取得本月獲利 (簡化做法：加總 TradeHistory 本月的 SELL 淨利，或是簡單概算)
    # 這邊簡單回傳總體損益作為 proxy
    
    return {
        "total_assets": round(portfolio.total_assets, 2),
        "available_cash": round(portfolio.available_cash, 2),
        "total_profit": round(total_profit, 2),
        "total_profit_pct": round(profit_pct, 2),
    }

@router.get("/positions")
def get_open_positions(db: Session = Depends(get_db)):
    """取得庫存清單"""
    positions = db.query(Position).all()
    results = []
    for p in positions:
        profit_val = (p.current_price - p.entry_price) * p.amount
        profit_pct = ((p.current_price - p.entry_price) / p.entry_price) * 100 if p.entry_price > 0 else 0
        
        results.append({
            "id": p.id,
            "symbol": p.symbol,
            "name": p.name,
            "amount": p.amount,
            "entry_price": round(p.entry_price, 2),
            "current_price": round(p.current_price, 2),
            "profit": round(profit_val, 2),
            "profit_pct": round(profit_pct, 2),
            "stop_loss_price": p.stop_loss_price,
            "take_profit_price": p.take_profit_price
        })
    return {"count": len(results), "positions": results}

@router.get("/history")
def get_trade_history(db: Session = Depends(get_db)):
    """取得交易明細"""
    histories = db.query(TradeHistory).order_by(TradeHistory.created_at.desc()).limit(50).all()
    results = []
    for h in histories:
        results.append({
            "id": h.id,
            "symbol": h.symbol,
            "name": h.name,
            "action": h.action,
            "amount": h.amount,
            "price": h.price,
            "fee": h.fee,
            "tax": h.tax,
            "reason": h.reason,
            "created_at": h.created_at.isoformat()
        })
    return {"count": len(results), "history": results}
