"""
V2 Trading API
- GET  /portfolio
- GET  /positions
- GET  /trades
- GET  /trades/export
- GET  /scan/status
- POST /risk/check
- POST /scan/toggle
- POST /scan/run
- POST /reset
"""

import asyncio
import csv
import io
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import StreamingResponse

from core.execution.portfolio_service import PortfolioService

_executor = ThreadPoolExecutor(max_workers=4)

router = APIRouter()
portfolio_service = PortfolioService()


def _refresh_portfolio_prices(request: Request):
    simulator = request.app.state.simulator
    fetcher = request.app.state.fetcher

    if not simulator.positions:
        return simulator

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
    return simulator


@router.get("/portfolio")
async def get_portfolio_summary(request: Request):
    from api.routes.simulation import scan_state

    loop = asyncio.get_event_loop()

    def _update_and_get():
        simulator = _refresh_portfolio_prices(request)
        portfolio = portfolio_service.build_portfolio(simulator)
        raw = simulator.get_portfolio_summary()
        equity_curve = []
        for entry in simulator.equity_curve:
            ts = entry.get("timestamp", "")
            equity_curve.append(
                {
                    "date": ts[:10] if ts else ts,
                    "equity": entry.get("total_assets", 0),
                    "benchmark": entry.get("total_assets", 0),
                }
            )

        return {
            **raw,
            "total_profit": raw.get("total_pnl", 0),
            "total_profit_pct": raw.get("total_pnl_pct", 0),
            "position_count": raw.get("positions_count", 0),
            "equity_curve": equity_curve,
            "portfolio_v2": portfolio.model_dump(mode="json"),
            "scan_state": dict(scan_state),
        }

    return await loop.run_in_executor(_executor, _update_and_get)


@router.get("/positions")
async def get_current_positions(request: Request):
    from datetime import datetime as _dt

    loop = asyncio.get_event_loop()

    def _fetch_blocking():
        simulator = _refresh_portfolio_prices(request)
        portfolio = portfolio_service.build_portfolio(simulator)
        now = _dt.now()
        normalized = []

        for p in portfolio.positions:
            hold_days = 0
            try:
                ts = p.timestamp.isoformat() if p.timestamp else ""
                if ts:
                    hold_days = (now - _dt.fromisoformat(ts)).days
            except Exception:
                pass

            normalized.append(
                {
                    **p.model_dump(mode="json"),
                    "profit": p.unrealized_pnl,
                    "profit_pct": p.unrealized_pnl_pct,
                    "break_even_price": round(p.entry_price * (1 + simulator.commission_rate * 2), 2),
                    "hold_days": hold_days,
                }
            )
        return normalized

    return await loop.run_in_executor(_executor, _fetch_blocking)


@router.get("/trades")
async def get_trade_history(request: Request):
    loop = asyncio.get_event_loop()

    def _fetch_blocking():
        simulator = request.app.state.simulator
        portfolio = portfolio_service.build_portfolio(simulator)
        normalized = []
        for trade in portfolio.trade_history:
            payload = trade.raw.copy()
            payload.update(
                {
                    "timestamp": trade.timestamp.isoformat() if trade.timestamp else payload.get("timestamp", ""),
                    "action": trade.action,
                    "stock_name": trade.stock_name,
                    "total_value": round(trade.total_value, 2),
                    "profit": trade.pnl,
                    "profit_pct": trade.pnl_pct,
                }
            )
            normalized.append(payload)
        return normalized

    return await loop.run_in_executor(_executor, _fetch_blocking)


@router.get("/trades/export")
def export_trades_csv(request: Request):
    simulator = request.app.state.simulator

    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(["時間", "操作", "股票代號", "股票名稱", "股數", "成交價", "總金額", "手續費", "交易稅", "損益(元)", "損益(%)", "剩餘現金"])

    for t in simulator.trade_history:
        action = t.get("type", t.get("action", ""))
        shares = t.get("shares", 0)
        price = t.get("price", 0)
        total = t.get("total_cost", shares * price) if action == "BUY" else shares * price
        writer.writerow(
            [
                t.get("timestamp", ""),
                "買入" if action == "BUY" else "賣出",
                t.get("stock_id", ""),
                t.get("name", t.get("stock_name", "")),
                shares,
                round(price, 2),
                round(total, 2),
                round(t.get("fee", 0), 2),
                round(t.get("tax", 0), 2),
                round(t.get("pnl", 0), 2) if t.get("pnl") is not None else "",
                round(t.get("pnl_pct", 0), 2) if t.get("pnl_pct") is not None else "",
                round(t.get("remaining_cash", 0), 2),
            ]
        )

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=AlphaTW_trades.csv"},
    )


@router.get("/scan/status")
async def get_scan_status():
    from api.routes.simulation import scan_state

    return dict(scan_state)


@router.post("/risk/check")
def check_stops(request: Request):
    simulator = request.app.state.simulator
    fetcher = request.app.state.fetcher

    if not simulator.positions:
        return {"checked": 0, "actions": []}

    prices = {}
    for sid in simulator.positions:
        try:
            quote = fetcher.fetch_realtime_quote(sid)
            if quote and quote.get("price", 0) > 0:
                prices[sid] = quote["price"]
        except Exception:
            pass

    actions = simulator.check_risk_management(prices)
    return {"checked": len(prices), "actions": actions}


@router.post("/scan/toggle")
def toggle_auto_scan():
    from api.routes.simulation import scan_state

    new_state = not scan_state.get("auto_scan_enabled", False)
    scan_state["auto_scan_enabled"] = new_state

    if new_state:
        scan_state["message"] = "自動交易已啟用，等待交易時段開始掃描..."
        if scan_state.get("market_status") == "WAITING":
            scan_state["market_status"] = "CLOSED"
    else:
        scan_state["market_status"] = "WAITING"
        if not scan_state.get("is_scanning"):
            scan_state["message"] = "自動交易已關閉"

    return {
        "status": "ok",
        "auto_scan_enabled": new_state,
        "message": f"無間斷掃描已{'開啟' if new_state else '關閉'}",
    }


@router.post("/scan/run")
async def run_analysis_cycle(background_tasks: BackgroundTasks):
    from api.routes.simulation import scan_state
    from core.scheduler import job_daily_market_scan

    if scan_state["is_scanning"]:
        return {"status": "error", "message": "全市場掃描已在進行中"}

    background_tasks.add_task(job_daily_market_scan)
    return {"status": "started", "message": "分析循環已啟動"}


@router.post("/reset")
def reset_simulation(request: Request):
    simulator = request.app.state.simulator
    simulator.reset(new_capital=simulator.initial_capital)
    return {"status": "ok", "message": "模擬帳戶已重置"}
