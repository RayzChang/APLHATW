"""
投資組合 API — 委派給 TradeSimulator（已統一交易系統）
"""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/summary")
def get_portfolio_summary(request: Request):
    """帳戶總資產、可用餘額、損益概覽"""
    simulator = request.app.state.simulator
    fetcher   = request.app.state.fetcher

    if simulator.positions:
        prices = {}
        for sid in simulator.positions:
            try:
                quote = fetcher.fetch_realtime_quote(sid)
                if quote and quote.get("price", 0) > 0:
                    prices[sid] = quote["price"]
            except Exception:
                pass
        if prices:
            simulator.update_current_prices(prices)

    summary = simulator.get_portfolio_summary()
    from config.settings import SIMULATION_INITIAL_BALANCE
    total_profit = summary.get("total_assets", SIMULATION_INITIAL_BALANCE) - SIMULATION_INITIAL_BALANCE
    profit_pct = round(total_profit / SIMULATION_INITIAL_BALANCE * 100, 2) if SIMULATION_INITIAL_BALANCE else 0.0

    return {
        "total_assets":      round(summary.get("total_assets", 0), 2),
        "available_cash":    round(summary.get("cash", 0), 2),
        "total_profit":      round(total_profit, 2),
        "total_profit_pct":  profit_pct,
        "position_count":    summary.get("position_count", 0),
        "unrealized_pnl":    round(summary.get("unrealized_pnl", 0), 2),
    }


@router.get("/positions")
def get_open_positions(request: Request):
    """庫存清單（含即時損益）"""
    simulator = request.app.state.simulator
    fetcher   = request.app.state.fetcher

    prices = {}
    for sid in simulator.positions:
        try:
            quote = fetcher.fetch_realtime_quote(sid)
            if quote and quote.get("price", 0) > 0:
                prices[sid] = quote["price"]
        except Exception:
            pass
    if prices:
        simulator.update_current_prices(prices)

    summary = simulator.get_portfolio_summary()
    positions = summary.get("positions_detail", [])
    return {"count": len(positions), "positions": positions}


@router.get("/history")
def get_trade_history(request: Request):
    """最近 50 筆交易記錄"""
    simulator = request.app.state.simulator
    trades = list(simulator.trade_history)[-50:]
    trades_reversed = list(reversed(trades))
    return {"count": len(trades_reversed), "history": trades_reversed}
