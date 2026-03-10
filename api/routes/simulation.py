"""
模擬交易 API — 投資組合管理與自動循環
"""

import asyncio
import csv
import io
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import StreamingResponse

_executor = ThreadPoolExecutor(max_workers=4)

router = APIRouter()

scan_state = {
    "is_scanning": False,
    "current": 0,
    "total": 0,
    "message": "待機中",
    "auto_scan_enabled": False,
    "market_status": "WAITING",
    "daily_api_cost_twd": 0.0,
    "last_scan_time": None,
    "last_scan_summary": "",
    "stocks_screened": 0,
    "candidates_found": 0,
    "orders_placed": 0,
}


@router.get("/portfolio")
async def get_portfolio_summary(request: Request):
    """
    取得模擬投資組合資產概覽。
    若有持倉，自動抓取即時報價計算真實損益。
    """
    loop = asyncio.get_event_loop()

    def _update_and_get():
        simulator = request.app.state.simulator
        fetcher = request.app.state.fetcher

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

        raw = simulator.get_portfolio_summary()
        equity_curve = []
        for entry in simulator.equity_curve:
            ts = entry.get("timestamp", "")
            try:
                date_str = ts[:10]
            except Exception:
                date_str = ts
            equity_curve.append(
                {
                    "date": date_str,
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
        }

    return await loop.run_in_executor(_executor, _update_and_get)


@router.post("/check_stops")
def check_stops(request: Request):
    """
    手動觸發一次停損 / 停利 / 追蹤止損檢查。
    """
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


@router.post("/toggle_auto_scan")
def toggle_auto_scan():
    """
    切換無間斷全市場掃描的開啟/關閉狀態。
    """
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


@router.post("/run_cycle")
async def run_analysis_cycle(background_tasks: BackgroundTasks):
    """
    手動啟動一次全市場掃描與 AI 自動交易循環（背景執行）。
    """
    from core.scheduler import job_daily_market_scan

    if scan_state["is_scanning"]:
        return {"status": "error", "message": "全市場掃描已在進行中"}

    background_tasks.add_task(job_daily_market_scan)
    return {"status": "started", "message": "分析循環已啟動"}


@router.post("/reset")
def reset_simulation(request: Request):
    """清空模擬交易紀錄、部位與資產，恢復初始狀態。"""
    simulator = request.app.state.simulator
    simulator.reset(new_capital=simulator.initial_capital)
    return {"status": "ok", "message": "模擬帳戶已重置"}


@router.get("/trades")
async def get_trade_history(request: Request):
    """取得完整交易歷史紀錄列表（欄位已正規化供前端使用）。"""
    loop = asyncio.get_event_loop()

    def _fetch_blocking():
        simulator = request.app.state.simulator

        normalized = []
        for t in simulator.trade_history:
            action = t.get("type", t.get("action", ""))
            shares = t.get("shares", 0)
            price = t.get("price", 0)

            total_value = t.get("total_cost", shares * price) if action == "BUY" else shares * price

            normalized.append(
                {
                    **t,
                    "action": action,
                    "stock_name": t.get("stock_name", t.get("name", "")),
                    "total_value": round(total_value, 2),
                    "profit": t.get("pnl", t.get("profit")),
                    "profit_pct": t.get("pnl_pct", t.get("profit_pct")),
                }
            )
        return normalized

    return await loop.run_in_executor(_executor, _fetch_blocking)


@router.get("/positions")
async def get_current_positions(request: Request):
    """取得當前持倉清單（含即時損益）。"""
    from datetime import datetime as _dt

    loop = asyncio.get_event_loop()

    def _fetch_blocking():
        simulator = request.app.state.simulator
        fetcher = request.app.state.fetcher

        if not simulator.positions:
            return []

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
        now = _dt.now()

        normalized = []
        for p in summary.get("positions", []):
            hold_days = 0
            try:
                ts = p.get("timestamp", "")
                if ts:
                    entry_dt = _dt.fromisoformat(ts)
                    hold_days = (now - entry_dt).days
            except Exception:
                pass

            be_price = round(p["entry_price"] * (1 + simulator.commission_rate * 2), 2)
            normalized.append(
                {
                    **p,
                    "profit": p.get("unrealized_pnl", 0),
                    "profit_pct": p.get("unrealized_pnl_pct", 0),
                    "break_even_price": be_price,
                    "hold_days": hold_days,
                }
            )

        return normalized

    return await loop.run_in_executor(_executor, _fetch_blocking)


@router.get("/trades/export")
def export_trades_csv(request: Request):
    """將歷史交易紀錄匯出為 CSV 檔案下載。"""
    simulator = request.app.state.simulator

    buf = io.StringIO()
    buf.write("\ufeff")

    writer = csv.writer(buf)
    writer.writerow(
        [
            "時間",
            "操作",
            "股票代號",
            "股票名稱",
            "股數",
            "成交價",
            "總金額",
            "手續費",
            "交易稅",
            "損益(元)",
            "損益(%)",
            "剩餘現金",
        ]
    )

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
    """
    取得 AI 自動掃描的即時進度。
    """
    return dict(scan_state)
