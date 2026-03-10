"""回測 API"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from core.backtest.strategy_backtest import run_backtest
from core.backtest.portfolio_backtest import run_portfolio_backtest, run_full_market_backtest, _YF_DOWNLOAD_LOCK
from config.settings import DEFAULT_WATCHLIST, SIMULATION_INITIAL_BALANCE, BACKTEST_UNIVERSE

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=2)


# ─── 策略回測（單一策略，多標的）─────────────────────────────────────────────

class BacktestRequest(BaseModel):
    symbols: list[str] | None = None
    strategy_id: str
    months: int = 6


@router.post("/run")
async def run_backtest_api(req: BacktestRequest, request: Request):
    symbols = req.symbols or DEFAULT_WATCHLIST
    fetcher = getattr(request.app.state, "fetcher", None)
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        _executor,
        lambda: run_backtest(symbols, req.strategy_id, req.months, fetcher=fetcher),
    )
    return {
        "count": len(results),
        "results": [
            {
                "symbol":       r.symbol,
                "name":         r.name,
                "close":        r.close,
                "total_return": r.total_return,
                "win_rate":     r.win_rate,
                "trade_count":  r.trade_count,
            }
            for r in results
        ],
    }


# ─── 投資組合回測（30 日、百萬本金、全策略）──────────────────────────────────

class PortfolioBacktestRequest(BaseModel):
    symbols: list[str] | None = None
    days: int = 30
    initial_capital: float | None = None
    buy_score_threshold: int = 1     # 1 = 多方訊號 > 空方；2 = 更嚴格
    full_market: bool = False        # True = 全市場掃描（yfinance），False = 精選標的（FinMind）


def _backtest_response(result, days: int) -> dict:
    return {
        "summary": {
            "initial_capital":          result.initial_capital,
            "final_capital":            result.final_capital,
            "total_return_pct":         result.total_return_pct,
            "total_pnl":                result.total_pnl,
            "benchmark_return_pct":     result.benchmark_return_pct,
            "total_trades":             result.total_trades,
            "closed_trades":            result.closed_trades,
            "win_trades":               result.win_trades,
            "loss_trades":              result.loss_trades,
            "win_rate":                 result.win_rate,
            "max_drawdown_pct":         result.max_drawdown_pct,
            "profit_factor":            result.profit_factor,
            "max_concurrent_positions": result.max_concurrent_positions,
            "days":                     days,
            "symbols_scanned":          result.symbols_loaded,
            "trading_days":             result.trading_days_count,
            "no_signal_reason":         result.no_signal_reason,
        },
        "equity_curve": result.equity_curve,
        "trades":       result.trades,
        "symbol_stats": result.symbol_stats,
    }


@router.post("/portfolio")
async def run_portfolio_backtest_api(req: PortfolioBacktestRequest, request: Request):
    """
    執行投資組合回測。

    - full_market=false（預設）：精選標的模式，使用 FinMind 抓 ~50 支台灣各產業龍頭
    - full_market=true：全市場模式，用 yfinance 批量下載全部台股（TWSE+TPEX ~3600 支），
      掃描所有普通股，與 AI 線上交易邏輯完全一致
    """
    initial_capital = req.initial_capital or SIMULATION_INITIAL_BALANCE
    fetcher         = getattr(request.app.state, "fetcher", None)

    # 若全市場模式下 yfinance 鎖已被 AI 掃描排程佔用，直接提示使用者等待
    if req.full_market and _YF_DOWNLOAD_LOCK.locked():
        raise HTTPException(
            status_code=409,
            detail="AI 全市場掃描正在下載市場資料，請等待掃描完成後（約 3–5 分鐘）再執行回測。"
        )

    loop = asyncio.get_event_loop()
    if req.full_market:
        result = await loop.run_in_executor(
            _executor,
            lambda: run_full_market_backtest(
                days=req.days,
                initial_capital=initial_capital,
                buy_score_threshold=req.buy_score_threshold,
                fetcher=fetcher,
            ),
        )
    else:
        symbols = req.symbols or list(BACKTEST_UNIVERSE)
        result = await loop.run_in_executor(
            _executor,
            lambda: run_portfolio_backtest(
                symbols=symbols,
                days=req.days,
                initial_capital=initial_capital,
                buy_score_threshold=req.buy_score_threshold,
                fetcher=fetcher,
            ),
        )

    return _backtest_response(result, req.days)
