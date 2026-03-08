"""
模擬交易 API — 投資組合管理與自動循環
"""

import csv
import io
from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import StreamingResponse

router = APIRouter()

# 全域掃描狀態（供 scheduler 更新，前端輪詢）
scan_state = {
    "is_scanning":       False,
    "current":           0,
    "total":             0,
    "message":           "",
    # 擴充欄位 —————————————————————————
    "last_scan_time":    None,   # ISO 字串，上次掃描完成時間
    "last_scan_summary": "",     # 上次掃描結果一行摘要
    "stocks_screened":   0,      # 第一層：下載到有效資料的股票數
    "candidates_found":  0,      # 第一層：技術評分 ≥ 1 的候選數
    "orders_placed":     0,      # 第二層：AI 決定下單的數量
}


@router.get("/portfolio")
def get_portfolio_summary(request: Request):
    """
    取得模擬投資組合資產概覽。
    若有持倉，自動抓取即時報價計算真實損益。
    """
    simulator = request.app.state.simulator
    fetcher   = request.app.state.fetcher

    # 若有持倉，先更新即時報價
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

    # 轉換 equity_curve 格式供前端圖表使用
    equity_curve = []
    for entry in simulator.equity_curve:
        ts = entry.get("timestamp", "")
        try:
            date_str = ts[:10]  # "2026-03-08"
        except Exception:
            date_str = ts
        equity_curve.append({
            "date": date_str,
            "equity": entry.get("total_assets", 0),
            "benchmark": entry.get("total_assets", 0),  # 未接 0050，暫用同值
        })

    return {
        **raw,
        "total_profit":     raw.get("total_pnl", 0),
        "total_profit_pct": raw.get("total_pnl_pct", 0),
        "position_count":   raw.get("positions_count", 0),
        "equity_curve":     equity_curve,
    }


@router.post("/check_stops")
def check_stops(request: Request):
    """
    手動觸發一次停損 / 停利 / 追蹤止損檢查。
    通常由排程器自動呼叫，也可前端手動觸發。
    """
    simulator = request.app.state.simulator
    fetcher   = request.app.state.fetcher

    if not simulator.positions:
        return {"checked": 0, "actions": []}

    # 抓取所有持倉的即時報價
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
    simulator.reset()
    return {"status": "ok", "message": "模擬帳戶已重置"}


@router.get("/trades")
def get_trade_history(request: Request):
    """取得完整交易歷史紀錄列表（欄位已正規化供前端使用）。"""
    simulator = request.app.state.simulator

    normalized = []
    for t in simulator.trade_history:
        action = t.get("type", t.get("action", ""))
        shares = t.get("shares", 0)
        price  = t.get("price", 0)

        # total_value：買入用 total_cost，賣出用 shares*price
        if action == "BUY":
            total_value = t.get("total_cost", shares * price)
        else:
            total_value = shares * price

        normalized.append({
            **t,
            "action":      action,
            "stock_name":  t.get("stock_name", t.get("name", "")),
            "total_value": round(total_value, 2),
            "profit":      t.get("pnl", t.get("profit")),
            "profit_pct":  t.get("pnl_pct", t.get("profit_pct")),
        })

    return normalized


@router.get("/positions")
def get_current_positions(request: Request):
    """取得當前持倉清單（含即時損益）。"""
    from datetime import datetime as _dt

    simulator = request.app.state.simulator
    fetcher   = request.app.state.fetcher

    if not simulator.positions:
        return []

    # 更新即時報價
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
        # 計算持倉天數
        hold_days = 0
        try:
            ts = p.get("timestamp", "")
            if ts:
                entry_dt = _dt.fromisoformat(ts)
                hold_days = (now - entry_dt).days
        except Exception:
            pass

        # 保本價 = 進場價 * (1 + 來回手續費)
        be_price = round(p["entry_price"] * (1 + simulator.commission_rate * 2), 2)

        normalized.append({
            **p,
            "profit":          p.get("unrealized_pnl", 0),
            "profit_pct":      p.get("unrealized_pnl_pct", 0),
            "break_even_price": be_price,
            "hold_days":       hold_days,
        })

    return normalized


@router.get("/trades/export")
def export_trades_csv(request: Request):
    """將歷史交易紀錄匯出為 CSV 檔案下載。"""
    simulator = request.app.state.simulator

    buf = io.StringIO()
    buf.write("\ufeff")  # BOM for Excel UTF-8

    writer = csv.writer(buf)
    writer.writerow([
        "時間", "操作", "股票代號", "股票名稱",
        "股數", "成交價", "總金額", "手續費", "交易稅",
        "損益(元)", "損益(%)", "剩餘現金",
    ])

    for t in simulator.trade_history:
        action = t.get("type", t.get("action", ""))
        shares = t.get("shares", 0)
        price  = t.get("price", 0)
        total  = t.get("total_cost", shares * price) if action == "BUY" else shares * price

        writer.writerow([
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
        ])

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=AlphaTW_trades.csv"},
    )


@router.get("/scan/status")
def get_scan_status():
    """
    取得 AI 自動掃描的即時進度與上次掃描摘要。
    前端每秒輪詢（掃描中）或每 30 秒輪詢（非掃描中）。
    """
    from datetime import datetime as _dt

    # 計算距上次掃描多久
    last_scan_ago = None
    if scan_state.get("last_scan_time"):
        try:
            diff = _dt.now() - _dt.fromisoformat(scan_state["last_scan_time"])
            total_min = int(diff.total_seconds() / 60)
            if total_min < 60:
                last_scan_ago = f"{total_min} 分鐘前"
            else:
                last_scan_ago = f"{total_min // 60} 小時前"
        except Exception:
            last_scan_ago = None

    return {
        **scan_state,
        "last_scan_ago": last_scan_ago,
        # 下次掃描時間說明（靜態文字，排程固定在 9:10 / 12:30）
        "next_scan_info": "每個交易日 09:10 及 12:30 自動執行",
    }
