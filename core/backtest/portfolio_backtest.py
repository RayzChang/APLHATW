"""
AlphaTW 投資組合回測引擎
=======================
兩種回測模式：

1. run_portfolio_backtest()  — 精選標的模式（FinMind 抓歷史 K 線）
   適合少量指定標的的快速回測。

2. run_full_market_backtest() — 全市場掃描模式（yfinance 批量下載）
   使用 yfinance 一次下載全部台股（TWSE 2336 + TPEX 1326），
   模擬若 AI 系統在過去 N 天掃描台股全市場的真實績效。

買入邏輯（與線上模擬系統一致）
--------------------------------
 - 計算 RSI / KD / MACD / MA20 / 布林帶 5 個技術指標
 - 各指標投票：看多 +1，看空 -1
 - 評分 >= 1 且目前持倉 < max_positions → 建倉
 - 停損  = entry - 2×ATR14
 - 停利  = entry + 3×ATR14
 - 最長持倉 20 個交易日後強制出場

注意：不呼叫 Gemini（避免費用與速度問題），用相同技術指標複現 AI 的量化決策。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import threading

import pandas as pd
from loguru import logger

# 全局鎖：防止回測和掃描排程同時下載 yfinance 造成衝突
_YF_DOWNLOAD_LOCK = threading.Lock()

from core.analysis.indicators import add_all_indicators, calc_buy_sell_score
from core.data.tw_data_fetcher import TWDataFetcher


# ─── 資料結構 ─────────────────────────────────────────────────────────────────

@dataclass
class _Position:
    symbol: str
    name: str
    shares: int
    entry_price: float
    entry_date: str
    avg_cost: float       # 含手續費每股成本
    stop_loss: float
    take_profit: float


@dataclass
class PortfolioBacktestResult:
    initial_capital: float
    final_capital: float
    total_return_pct: float
    total_pnl: float = 0.0

    # Benchmark
    benchmark_return_pct: float = 0.0

    # 統計
    total_trades: int = 0
    closed_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    win_rate: float = 0.0
    max_drawdown_pct: float = 0.0
    profit_factor: float = 0.0
    max_concurrent_positions: int = 0

    # 診斷資訊
    symbols_loaded: int = 0
    trading_days_count: int = 0
    no_signal_reason: str = ""

    # 時間序列
    equity_curve: list[dict] = field(default_factory=list)

    # 交易記錄
    trades: list[dict] = field(default_factory=list)

    # 各標的績效
    symbol_stats: list[dict] = field(default_factory=list)


# ─── 主函式 ───────────────────────────────────────────────────────────────────

def run_portfolio_backtest(
    symbols: list[str],
    days: int = 30,
    initial_capital: float = 1_000_000.0,
    max_position_pct: float = 0.20,
    max_positions: int = 5,
    commission_rate: float = 0.001425,
    tax_rate: float = 0.003,
    buy_score_threshold: int = 1,    # 降到 1：只要多於看空訊號就考慮進場
    max_hold_days: int = 20,
    stop_multiplier: float = 2.0,
    target_multiplier: float = 3.0,
    fetcher: Optional[TWDataFetcher] = None,
) -> PortfolioBacktestResult:
    """
    對 symbols 進行過去 days 天的投資組合回測。

    Parameters
    ----------
    symbols               : 要掃描的股票代碼清單
    days                  : 回測天數（日曆天）
    initial_capital       : 初始資金（台幣）
    max_position_pct      : 單檔最大部位 % (0~1)
    max_positions         : 最多同時持有幾檔
    buy_score_threshold   : 進場最低技術評分（1 = 多方訊號多於空方）
    max_hold_days         : 最長持倉交易日（之後強制出場）
    stop_multiplier       : 停損距離（倍 ATR）
    target_multiplier     : 停利距離（倍 ATR）
    """
    if fetcher is None:
        fetcher = TWDataFetcher()

    # ── 1. 抓取資料（+90 天暖機期讓指標穩定）──────────────────────────────
    end_date    = datetime.now()
    warmup_days = 90
    fetch_start = (end_date - timedelta(days=days + warmup_days)).strftime("%Y-%m-%d")
    fetch_end   = end_date.strftime("%Y-%m-%d")

    stock_data: dict[str, pd.DataFrame] = {}
    stock_names: dict[str, str]         = {}

    # 排除 ETF，ETF 不適合技術分析交易（但可以用作基準）
    etf_symbols = {"0050", "0056", "00878", "00632R"}
    tradable = [s for s in symbols if s not in etf_symbols]

    logger.info(f"Backtest: 準備抓取 {len(tradable)} 個標的的歷史資料 ...")
    for symbol in tradable:
        try:
            df = fetcher.fetch_klines(symbol, fetch_start, fetch_end)
            if df is None or df.empty or len(df) < 35:
                logger.debug(f"Backtest: {symbol} 資料不足，跳過")
                continue
            df = add_all_indicators(df)
            df = df.dropna(subset=["rsi", "macd_hist", "ma20"]).reset_index(drop=True)
            df["date"] = pd.to_datetime(df["date"])
            stock_data[symbol] = df
            stock_names[symbol] = fetcher.get_symbol_name(symbol)
        except Exception as e:
            logger.warning(f"Backtest: {symbol} 資料錯誤: {e}")

    logger.info(f"Backtest: 成功載入 {len(stock_data)}/{len(tradable)} 個標的")

    # ── 2. 取得 0050 基準 ─────────────────────────────────────────────────
    benchmark_series: Optional[pd.Series] = None
    try:
        df_050 = fetcher.fetch_klines("0050", fetch_start, fetch_end)
        if df_050 is not None and not df_050.empty:
            df_050["date"] = pd.to_datetime(df_050["date"])
            benchmark_series = df_050.set_index("date")["close"]
    except Exception as e:
        logger.warning(f"Backtest: 無法取得 0050 基準: {e}")

    # ── 3. 確定回測交易日 ─────────────────────────────────────────────────
    cutoff    = (end_date - timedelta(days=days)).date()
    all_dates: set = set()
    for df in stock_data.values():
        for d in df[df["date"].dt.date >= cutoff]["date"].dt.date:
            all_dates.add(d)
    trading_days = sorted(all_dates)

    if not trading_days:
        reason = (
            f"找不到 {cutoff} 之後的交易日。"
            f"可能原因：FinMind Token 未設定或已超過流量限制，導致資料下載失敗。"
            f"已載入標的數：{len(stock_data)}"
        )
        logger.error(f"Backtest: {reason}")
        return PortfolioBacktestResult(
            initial_capital=initial_capital,
            final_capital=initial_capital,
            total_return_pct=0.0,
            symbols_loaded=len(stock_data),
            trading_days_count=0,
            no_signal_reason=reason,
        )

    logger.info(f"Backtest: 回測期間 {trading_days[0]} ~ {trading_days[-1]}，共 {len(trading_days)} 個交易日")

    # ── 4. 逐日模擬 ───────────────────────────────────────────────────────
    cash        = float(initial_capital)
    positions: dict[str, _Position] = {}
    trades: list[dict] = []
    equity_curve: list[dict] = []
    symbol_pnl: dict[str, list[float]] = {}
    max_concurrent = 0

    benchmark_start_price: Optional[float] = None
    score_debug: dict[str, list[int]] = {}   # 記錄每日評分，供診斷

    for day in trading_days:
        # 當日各持倉估算收盤價
        current_prices: dict[str, float] = {}
        for sym, pos in positions.items():
            df = stock_data.get(sym)
            if df is None:
                continue
            rows = df[df["date"].dt.date == day]
            if not rows.empty:
                current_prices[sym] = float(rows.iloc[0]["close"])
            else:
                prev = df[df["date"].dt.date < day]
                if not prev.empty:
                    current_prices[sym] = float(prev.iloc[-1]["close"])

        pos_value  = sum(current_prices.get(s, p.entry_price) * p.shares for s, p in positions.items())
        total_value = cash + pos_value
        max_concurrent = max(max_concurrent, len(positions))

        # Benchmark
        bench_equity: float = total_value
        if benchmark_series is not None:
            bench_rows = benchmark_series[benchmark_series.index.date <= day]
            if not bench_rows.empty:
                bench_close = float(bench_rows.iloc[-1])
                if benchmark_start_price is None:
                    benchmark_start_price = bench_close
                if benchmark_start_price and benchmark_start_price > 0:
                    bench_equity = initial_capital * (bench_close / benchmark_start_price)

        equity_curve.append({
            "date":      str(day),
            "equity":    round(total_value, 2),
            "benchmark": round(bench_equity, 2),
        })

        # ── a. 賣出檢查 ───────────────────────────────────────────────────
        to_close: list[tuple[str, float, str]] = []

        for sym, pos in positions.items():
            df = stock_data.get(sym)
            if df is None:
                continue
            rows = df[df["date"].dt.date == day]
            if rows.empty:
                continue

            close     = float(rows.iloc[0]["close"])
            row       = rows.iloc[0]
            entry_dt  = pd.Timestamp(pos.entry_date).date()
            days_held = sum(1 for d in trading_days if entry_dt <= d < day)

            reason = None
            if close <= pos.stop_loss:
                reason = "止損觸發"
            elif close >= pos.take_profit:
                reason = "止盈觸發"
            elif days_held >= max_hold_days:
                reason = f"持倉滿 {max_hold_days} 日"
            else:
                score = calc_buy_sell_score(row)
                if score <= -2:
                    reason = f"技術反轉 (評分={score})"

            if reason:
                to_close.append((sym, close, reason))

        for sym, close, reason in to_close:
            pos        = positions.pop(sym)
            amount     = pos.shares * close
            fee        = amount * commission_rate
            tax        = amount * tax_rate
            received   = amount - fee - tax
            cost_basis = pos.shares * pos.avg_cost
            pnl        = received - cost_basis
            pnl_pct    = pnl / cost_basis * 100 if cost_basis else 0.0
            cash      += received

            trades.append({
                "symbol":      sym,
                "name":        pos.name,
                "action":      "SELL",
                "date":        str(day),
                "price":       round(close, 2),
                "shares":      pos.shares,
                "value":       round(amount, 2),
                "fee":         round(fee + tax, 2),
                "pnl":         round(pnl, 2),
                "pnl_pct":     round(pnl_pct, 2),
                "reason":      reason,
                "entry_price": pos.entry_price,
                "entry_date":  pos.entry_date,
            })
            symbol_pnl.setdefault(sym, []).append(pnl_pct)

        # ── b. 買入掃描（已達上限就略過）────────────────────────────────
        if len(positions) >= max_positions:
            continue

        for sym, df in stock_data.items():
            if sym in positions:
                continue
            if len(positions) >= max_positions:
                break

            rows = df[df["date"].dt.date == day]
            if rows.empty:
                continue
            row   = rows.iloc[0]
            close = float(row["close"])
            if close <= 0:
                continue

            score = calc_buy_sell_score(row)
            score_debug.setdefault(sym, []).append(score)

            if score < buy_score_threshold:
                continue

            # 計算當前總資產（含持倉市值）
            live_pos_val = sum(
                current_prices.get(s, p.entry_price) * p.shares
                for s, p in positions.items()
            )
            live_total = cash + live_pos_val
            max_invest = live_total * max_position_pct
            available  = min(cash * 0.95, max_invest)

            shares = int(available / close / 1000) * 1000
            if shares < 1000:
                continue

            cost_base  = shares * close
            fee        = cost_base * commission_rate
            total_cost = cost_base + fee
            while shares >= 1000 and total_cost > cash:
                shares    -= 1000
                cost_base  = shares * close
                fee        = cost_base * commission_rate
                total_cost = cost_base + fee
            if shares < 1000:
                continue

            atr = float(row.get("atr", 0))
            if pd.isna(atr) or atr <= 0:
                atr = close * 0.02
            stop_loss   = round(close - stop_multiplier * atr, 2)
            take_profit = round(close + target_multiplier * atr, 2)

            cash -= total_cost
            positions[sym] = _Position(
                symbol=sym,
                name=stock_names.get(sym, sym),
                shares=shares,
                entry_price=close,
                entry_date=str(day),
                avg_cost=total_cost / shares,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            logger.debug(f"Backtest BUY: {sym} @{close} score={score} shares={shares}")

            trades.append({
                "symbol":      sym,
                "name":        stock_names.get(sym, sym),
                "action":      "BUY",
                "date":        str(day),
                "price":       round(close, 2),
                "shares":      shares,
                "value":       round(cost_base, 2),
                "fee":         round(fee, 2),
                "pnl":         None,
                "pnl_pct":     None,
                "reason":      f"技術評分={score}",
                "entry_price": close,
                "entry_date":  str(day),
            })

    # ── 5. 強制平倉（回測結束）────────────────────────────────────────────
    last_day = trading_days[-1]
    for sym, pos in list(positions.items()):
        df = stock_data.get(sym)
        if df is None:
            continue
        last_rows = df[df["date"].dt.date <= last_day]
        if last_rows.empty:
            continue
        close    = float(last_rows.iloc[-1]["close"])
        amount   = pos.shares * close
        fee      = amount * commission_rate
        tax      = amount * tax_rate
        received = amount - fee - tax
        pnl      = received - pos.shares * pos.avg_cost
        pnl_pct  = pnl / (pos.shares * pos.avg_cost) * 100 if pos.avg_cost else 0.0
        cash    += received

        trades.append({
            "symbol":      sym,
            "name":        pos.name,
            "action":      "SELL",
            "date":        str(last_day),
            "price":       round(close, 2),
            "shares":      pos.shares,
            "value":       round(amount, 2),
            "fee":         round(fee + tax, 2),
            "pnl":         round(pnl, 2),
            "pnl_pct":     round(pnl_pct, 2),
            "reason":      "回測結束平倉",
            "entry_price": pos.entry_price,
            "entry_date":  pos.entry_date,
        })
        symbol_pnl.setdefault(sym, []).append(pnl_pct)

    # ── 6. 統計 ───────────────────────────────────────────────────────────
    final_capital    = round(cash, 2)
    total_pnl        = round(final_capital - initial_capital, 2)
    total_return_pct = round(total_pnl / initial_capital * 100, 2)

    sell_trades  = [t for t in trades if t["action"] == "SELL"]
    win_trades   = [t for t in sell_trades if (t.get("pnl") or 0) > 0]
    loss_trades  = [t for t in sell_trades if (t.get("pnl") or 0) <= 0]
    win_rate     = round(len(win_trades) / len(sell_trades) * 100, 1) if sell_trades else 0.0

    total_profit  = sum(t["pnl"] for t in win_trades  if t.get("pnl"))
    total_loss    = abs(sum(t["pnl"] for t in loss_trades if t.get("pnl")))
    profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else 999.9

    # 最大回撤
    peak   = equity_curve[0]["equity"] if equity_curve else initial_capital
    max_dd = 0.0
    for pt in equity_curve:
        eq = pt["equity"]
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd
    max_dd = round(max_dd, 2)

    # Benchmark 最終報酬
    bench_final_pct = 0.0
    if len(equity_curve) >= 2:
        b_start = equity_curve[0]["benchmark"]
        b_end   = equity_curve[-1]["benchmark"]
        if b_start > 0:
            bench_final_pct = round((b_end - b_start) / b_start * 100, 2)

    # 各標的績效
    symbol_stats = []
    for sym, pnls in symbol_pnl.items():
        wins = sum(1 for p in pnls if p > 0)
        symbol_stats.append({
            "symbol":        sym,
            "name":          stock_names.get(sym, sym),
            "trades":        len(pnls),
            "total_pnl_pct": round(sum(pnls), 2),
            "win_rate":      round(wins / len(pnls) * 100, 1),
        })
    symbol_stats.sort(key=lambda x: x["total_pnl_pct"], reverse=True)

    # 診斷訊息（若 0 交易）
    no_signal_reason = ""
    if not sell_trades:
        avg_scores = {
            sym: round(sum(scores) / len(scores), 1) if scores else 0
            for sym, scores in score_debug.items()
        }
        best = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)[:5]
        no_signal_reason = (
            f"回測期間內未產生任何交易。"
            f"已載入 {len(stock_data)} 個標的，{len(trading_days)} 個交易日。"
            f"平均評分最高的標的：{best}。"
            f"建議確認 FinMind Token 正確設定，或擴大回測天數。"
        )
        logger.warning(f"Backtest: {no_signal_reason}")

    logger.info(
        f"Backtest 完成: {len(trading_days)} 日, "
        f"{len(stock_data)} 標的, {len(sell_trades)} 筆交易, "
        f"報酬 {total_return_pct:+.2f}%"
    )

    return PortfolioBacktestResult(
        initial_capital=initial_capital,
        final_capital=final_capital,
        total_return_pct=total_return_pct,
        total_pnl=total_pnl,
        benchmark_return_pct=bench_final_pct,
        total_trades=len(trades),
        closed_trades=len(sell_trades),
        win_trades=len(win_trades),
        loss_trades=len(loss_trades),
        win_rate=win_rate,
        max_drawdown_pct=max_dd,
        profit_factor=profit_factor,
        max_concurrent_positions=max_concurrent,
        symbols_loaded=len(stock_data),
        trading_days_count=len(trading_days),
        no_signal_reason=no_signal_reason,
        equity_curve=equity_curve,
        trades=trades,
        symbol_stats=symbol_stats,
    )


# ─── 全市場回測（yfinance 批量下載）─────────────────────────────────────────

def _yf_batch_download(
    tickers: list[str],
    start: str,
    end: str,
    batch_size: int = 400,
) -> dict[str, pd.DataFrame]:
    """
    用 yfinance 批量下載多支股票歷史 K 線，回傳 {yf_ticker: DataFrame}。
    DataFrame 欄位：date(index→reset), open, high, low, close, volume

    使用預設格式（Level-0=price type, Level-1=ticker），多線程並行，速度最快。
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance 未安裝，請執行 pip install yfinance")
        return {}

    result: dict[str, pd.DataFrame] = {}

    for batch_start in range(0, len(tickers), batch_size):
        batch = tickers[batch_start: batch_start + batch_size]
        logger.info(
            f"yfinance 批量下載 {batch_start+1}~{batch_start+len(batch)}"
            f"/{len(tickers)} ..."
        )
        try:
            # 使用全局鎖，避免回測和掃描排程同時下載 yfinance 造成連線衝突
            with _YF_DOWNLOAD_LOCK:
                data = yf.download(
                    batch,
                    start=start,
                    end=end,
                    auto_adjust=True,
                    progress=False,
                    threads=True,
                )
            if data is None or data.empty:
                continue

            if isinstance(data.columns, pd.MultiIndex):
                # 預設格式：Level-0 = price type, Level-1 = ticker
                available_tickers = data.columns.get_level_values(1).unique()
                for ticker in available_tickers:
                    try:
                        df = data.xs(ticker, level=1, axis=1).copy()
                        df.index = pd.to_datetime(df.index)
                        df = df.rename(columns={
                            "Open": "open", "High": "high", "Low": "low",
                            "Close": "close", "Volume": "volume",
                        })
                        keep = [c for c in ["open", "high", "low", "close", "volume"]
                                if c in df.columns]
                        df = df[keep].dropna(subset=["close"])
                        df.index.name = "date"
                        df = df.reset_index()
                        df["date"] = pd.to_datetime(df["date"])
                        if len(df) >= 35:
                            result[ticker] = df
                    except Exception as e:
                        logger.debug(f"yfinance parse {ticker}: {e}")
            else:
                # 只有一支股票時為普通 DataFrame（不應發生，但安全處理）
                logger.debug("yfinance 返回非 MultiIndex，跳過此批次")
        except Exception as e:
            logger.warning(f"yfinance 批次 {batch_start} 錯誤: {e}")

    logger.info(f"yfinance 下載完成：{len(result)}/{len(tickers)} 支有效")
    return result


def run_full_market_backtest(
    days: int = 30,
    initial_capital: float = 1_000_000.0,
    max_position_pct: float = 0.15,
    max_positions: int = 5,
    commission_rate: float = 0.001425,
    tax_rate: float = 0.003,
    buy_score_threshold: int = 3,
    max_hold_days: int = 15,
    stop_multiplier: float = 2.0,
    target_multiplier: float = 3.0,
    fetcher: Optional[TWDataFetcher] = None,
) -> PortfolioBacktestResult:
    """
    全市場掃描回測。
    使用 yfinance 批量下載全部台股（TWSE + TPEX），
    對每支股票計算技術指標並模擬 AI 跟單交易。

    與 run_portfolio_backtest() 邏輯完全相同，
    差異只在資料來源（yfinance vs FinMind）與股票池（全市場 vs 精選）。
    """
    if fetcher is None:
        fetcher = TWDataFetcher()

    # ── 1. 取得全部股票清單（一次 FinMind API 呼叫）────────────────────────
    logger.info("全市場回測：從 FinMind 取得所有上市/上櫃股票清單...")
    all_stocks = fetcher.get_all_stock_ids_with_market()   # {sid: 'twse'|'tpex'}

    if not all_stocks:
        return PortfolioBacktestResult(
            initial_capital=initial_capital,
            final_capital=initial_capital,
            total_return_pct=0.0,
            symbols_loaded=0,
            trading_days_count=0,
            no_signal_reason="無法取得股票清單，請確認 FinMind Token 已設定。",
        )

    # 只保留 4 位數普通股（排除 ETF 00xxx、特別股 xxxP 等）
    tradable_map: dict[str, str] = {}   # {yf_ticker: stock_id}
    stock_names: dict[str, str] = {}

    for sid, mtype in all_stocks.items():
        # 4 位數字，且不是 ETF（不以 0 開頭）
        if not (len(sid) == 4 and sid.isdigit() and not sid.startswith("0")):
            continue
        suffix = ".TW" if mtype == "twse" else ".TWO"
        yf_ticker = f"{sid}{suffix}"
        tradable_map[yf_ticker] = sid
        stock_names[sid] = fetcher.get_symbol_name(sid)

    logger.info(f"全市場回測：過濾後共 {len(tradable_map)} 支可交易普通股")

    # ── 2. yfinance 批量下載（+90 天暖機期）────────────────────────────────
    end_date    = datetime.now()
    warmup_days = 90
    fetch_start = (end_date - timedelta(days=days + warmup_days)).strftime("%Y-%m-%d")
    fetch_end   = end_date.strftime("%Y-%m-%d")

    yf_data = _yf_batch_download(
        list(tradable_map.keys()),
        start=fetch_start,
        end=fetch_end,
    )

    # ── 3. 計算技術指標 ───────────────────────────────────────────────────
    stock_data: dict[str, pd.DataFrame] = {}   # {stock_id: df_with_indicators}

    logger.info(f"全市場回測：計算 {len(yf_data)} 支股票技術指標...")
    for yf_ticker, raw_df in yf_data.items():
        sid = tradable_map.get(yf_ticker)
        if not sid:
            continue
        try:
            df = add_all_indicators(raw_df.copy())
            df = df.dropna(subset=["rsi", "macd_hist", "ma20"]).reset_index(drop=True)
            df["date"] = pd.to_datetime(df["date"])
            if len(df) >= 20:
                stock_data[sid] = df
        except Exception as e:
            logger.debug(f"全市場指標計算 {sid}: {e}")

    logger.info(f"全市場回測：成功計算指標 {len(stock_data)} 支")

    # ── 4. 取得 0050 基準（yfinance）────────────────────────────────────────
    benchmark_series: Optional[pd.Series] = None
    try:
        import yfinance as yf
        df_050 = yf.download(
            "0050.TW", start=fetch_start, end=fetch_end,
            auto_adjust=True, progress=False,
        )
        if df_050 is not None and not df_050.empty:
            df_050.index = pd.to_datetime(df_050.index)
            df_050.index.name = "date"
            benchmark_series = df_050["Close"].rename("close")
    except Exception as e:
        logger.warning(f"全市場回測：無法取得 0050 基準: {e}")

    # ── 5. 確定回測交易日 ─────────────────────────────────────────────────
    cutoff = (end_date - timedelta(days=days)).date()
    all_dates: set = set()
    for df in stock_data.values():
        for d in df[df["date"].dt.date >= cutoff]["date"].dt.date:
            all_dates.add(d)
    trading_days = sorted(all_dates)

    if not trading_days:
        reason = (
            f"找不到 {cutoff} 之後的交易日。"
            f"已成功載入 {len(stock_data)} 個標的。"
            f"可能是 yfinance 資料未更新（台股通常延遲 1 個交易日）。"
        )
        logger.error(f"全市場回測: {reason}")
        return PortfolioBacktestResult(
            initial_capital=initial_capital,
            final_capital=initial_capital,
            total_return_pct=0.0,
            symbols_loaded=len(stock_data),
            trading_days_count=0,
            no_signal_reason=reason,
        )

    logger.info(
        f"全市場回測：回測期間 {trading_days[0]} ~ {trading_days[-1]}，"
        f"共 {len(trading_days)} 個交易日，{len(stock_data)} 支股票"
    )

    # ── 6. 逐日模擬（與 run_portfolio_backtest 完全相同邏輯）────────────────
    cash = float(initial_capital)
    positions: dict[str, _Position] = {}
    trades: list[dict] = []
    equity_curve: list[dict] = []
    symbol_pnl: dict[str, list[float]] = {}
    max_concurrent = 0

    benchmark_start_price: Optional[float] = None
    score_debug: dict[str, list[int]] = {}

    for day in trading_days:
        current_prices: dict[str, float] = {}
        for sym, pos in positions.items():
            df = stock_data.get(sym)
            if df is None:
                continue
            rows = df[df["date"].dt.date == day]
            if not rows.empty:
                current_prices[sym] = float(rows.iloc[0]["close"])
            else:
                prev = df[df["date"].dt.date < day]
                if not prev.empty:
                    current_prices[sym] = float(prev.iloc[-1]["close"])

        pos_value   = sum(current_prices.get(s, p.entry_price) * p.shares
                          for s, p in positions.items())
        total_value = cash + pos_value
        max_concurrent = max(max_concurrent, len(positions))

        bench_equity: float = total_value
        if benchmark_series is not None:
            bench_rows = benchmark_series[benchmark_series.index.date <= day]
            if not bench_rows.empty:
                bench_close = float(bench_rows.iloc[-1])
                if benchmark_start_price is None:
                    benchmark_start_price = bench_close
                if benchmark_start_price and benchmark_start_price > 0:
                    bench_equity = initial_capital * (bench_close / benchmark_start_price)

        equity_curve.append({
            "date":      str(day),
            "equity":    round(total_value, 2),
            "benchmark": round(bench_equity, 2),
        })

        # 賣出檢查
        to_close: list[tuple[str, float, str]] = []
        for sym, pos in positions.items():
            df = stock_data.get(sym)
            if df is None:
                continue
            rows = df[df["date"].dt.date == day]
            if rows.empty:
                continue
            close    = float(rows.iloc[0]["close"])
            row      = rows.iloc[0]
            entry_dt = pd.Timestamp(pos.entry_date).date()
            days_held = sum(1 for d in trading_days if entry_dt <= d < day)
            reason = None
            if close <= pos.stop_loss:
                reason = "止損觸發"
            elif close >= pos.take_profit:
                reason = "止盈觸發"
            elif days_held >= max_hold_days:
                reason = f"持倉滿 {max_hold_days} 日"
            else:
                score = calc_buy_sell_score(row)
                if score <= -2:
                    reason = f"技術反轉 (評分={score})"
            if reason:
                to_close.append((sym, close, reason))

        for sym, close, reason in to_close:
            pos        = positions.pop(sym)
            amount     = pos.shares * close
            fee        = amount * commission_rate
            tax        = amount * tax_rate
            received   = amount - fee - tax
            cost_basis = pos.shares * pos.avg_cost
            pnl        = received - cost_basis
            pnl_pct    = pnl / cost_basis * 100 if cost_basis else 0.0
            cash      += received
            trades.append({
                "symbol":      sym,
                "name":        pos.name,
                "action":      "SELL",
                "date":        str(day),
                "price":       round(close, 2),
                "shares":      pos.shares,
                "value":       round(amount, 2),
                "fee":         round(fee + tax, 2),
                "pnl":         round(pnl, 2),
                "pnl_pct":     round(pnl_pct, 2),
                "reason":      reason,
                "entry_price": pos.entry_price,
                "entry_date":  pos.entry_date,
            })
            symbol_pnl.setdefault(sym, []).append(pnl_pct)

        if len(positions) >= max_positions:
            continue

        buy_candidates: list[tuple[int, str, float, object]] = []
        for sym, df in stock_data.items():
            if sym in positions:
                continue
            rows = df[df["date"].dt.date == day]
            if rows.empty:
                continue
            row   = rows.iloc[0]
            close = float(row["close"])
            if close <= 10:
                continue
            vol = float(row.get("volume", 0))
            if vol < 500_000:
                continue
            score = calc_buy_sell_score(row)
            score_debug.setdefault(sym, []).append(score)
            if score >= buy_score_threshold:
                buy_candidates.append((score, sym, close, row))

        # 評分高的優先
        buy_candidates.sort(key=lambda x: x[0], reverse=True)

        for score, sym, close, row in buy_candidates:
            if len(positions) >= max_positions:
                break
            live_pos_val = sum(
                current_prices.get(s, p.entry_price) * p.shares
                for s, p in positions.items()
            )
            live_total = cash + live_pos_val
            max_invest = live_total * max_position_pct
            available  = min(cash * 0.95, max_invest)

            shares = int(available / close / 1000) * 1000
            if shares < 1000:
                continue

            cost_base  = shares * close
            fee        = cost_base * commission_rate
            total_cost = cost_base + fee
            while shares >= 1000 and total_cost > cash:
                shares    -= 1000
                cost_base  = shares * close
                fee        = cost_base * commission_rate
                total_cost = cost_base + fee
            if shares < 1000:
                continue

            atr = float(row.get("atr", 0))
            if pd.isna(atr) or atr <= 0:
                atr = close * 0.02
            stop_loss   = round(close - stop_multiplier * atr, 2)
            take_profit = round(close + target_multiplier * atr, 2)

            cash -= total_cost
            positions[sym] = _Position(
                symbol=sym,
                name=stock_names.get(sym, sym),
                shares=shares,
                entry_price=close,
                entry_date=str(day),
                avg_cost=total_cost / shares,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            logger.debug(
                f"全市場BUY: {sym}({stock_names.get(sym,sym)}) "
                f"@{close} score={score} shares={shares}"
            )
            trades.append({
                "symbol":      sym,
                "name":        stock_names.get(sym, sym),
                "action":      "BUY",
                "date":        str(day),
                "price":       round(close, 2),
                "shares":      shares,
                "value":       round(cost_base, 2),
                "fee":         round(fee, 2),
                "pnl":         None,
                "pnl_pct":     None,
                "reason":      f"全市場掃描 評分={score}",
                "entry_price": close,
                "entry_date":  str(day),
            })

    # ── 7. 強制平倉（回測結束）───────────────────────────────────────────
    last_day = trading_days[-1]
    for sym, pos in list(positions.items()):
        df = stock_data.get(sym)
        if df is None:
            continue
        last_rows = df[df["date"].dt.date <= last_day]
        if last_rows.empty:
            continue
        close    = float(last_rows.iloc[-1]["close"])
        amount   = pos.shares * close
        fee      = amount * commission_rate
        tax      = amount * tax_rate
        received = amount - fee - tax
        pnl      = received - pos.shares * pos.avg_cost
        pnl_pct  = pnl / (pos.shares * pos.avg_cost) * 100 if pos.avg_cost else 0.0
        cash    += received
        trades.append({
            "symbol":      sym,
            "name":        pos.name,
            "action":      "SELL",
            "date":        str(last_day),
            "price":       round(close, 2),
            "shares":      pos.shares,
            "value":       round(amount, 2),
            "fee":         round(fee + tax, 2),
            "pnl":         round(pnl, 2),
            "pnl_pct":     round(pnl_pct, 2),
            "reason":      "回測結束平倉",
            "entry_price": pos.entry_price,
            "entry_date":  pos.entry_date,
        })
        symbol_pnl.setdefault(sym, []).append(pnl_pct)

    # ── 8. 統計 ──────────────────────────────────────────────────────────
    final_capital    = round(cash, 2)
    total_pnl        = round(final_capital - initial_capital, 2)
    total_return_pct = round(total_pnl / initial_capital * 100, 2)

    sell_trades  = [t for t in trades if t["action"] == "SELL"]
    win_trades   = [t for t in sell_trades if (t.get("pnl") or 0) > 0]
    loss_trades  = [t for t in sell_trades if (t.get("pnl") or 0) <= 0]
    win_rate     = round(len(win_trades) / len(sell_trades) * 100, 1) if sell_trades else 0.0

    total_profit  = sum(t["pnl"] for t in win_trades  if t.get("pnl"))
    total_loss    = abs(sum(t["pnl"] for t in loss_trades if t.get("pnl")))
    profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else 999.9

    peak   = equity_curve[0]["equity"] if equity_curve else initial_capital
    max_dd = 0.0
    for pt in equity_curve:
        eq = pt["equity"]
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd
    max_dd = round(max_dd, 2)

    bench_final_pct = 0.0
    if len(equity_curve) >= 2:
        b_start = equity_curve[0]["benchmark"]
        b_end   = equity_curve[-1]["benchmark"]
        if b_start > 0:
            bench_final_pct = round((b_end - b_start) / b_start * 100, 2)

    symbol_stats = []
    for sym, pnls in symbol_pnl.items():
        wins = sum(1 for p in pnls if p > 0)
        symbol_stats.append({
            "symbol":        sym,
            "name":          stock_names.get(sym, sym),
            "trades":        len(pnls),
            "total_pnl_pct": round(sum(pnls), 2),
            "win_rate":      round(wins / len(pnls) * 100, 1),
        })
    symbol_stats.sort(key=lambda x: x["total_pnl_pct"], reverse=True)

    no_signal_reason = ""
    if not sell_trades:
        avg_scores = {
            sym: round(sum(scores) / len(scores), 1) if scores else 0
            for sym, scores in score_debug.items()
        }
        best = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)[:5]
        no_signal_reason = (
            f"全市場回測未產生任何交易。"
            f"已掃描 {len(stock_data)} 個標的，{len(trading_days)} 個交易日。"
            f"平均評分最高的標的：{best}。"
            f"建議降低買入門檻或延長回測天數。"
        )
        logger.warning(f"全市場回測: {no_signal_reason}")

    logger.info(
        f"全市場回測完成: {len(trading_days)} 日, "
        f"{len(stock_data)} 標的, {len(sell_trades)} 筆交易, "
        f"報酬 {total_return_pct:+.2f}%"
    )

    return PortfolioBacktestResult(
        initial_capital=initial_capital,
        final_capital=final_capital,
        total_return_pct=total_return_pct,
        total_pnl=total_pnl,
        benchmark_return_pct=bench_final_pct,
        total_trades=len(trades),
        closed_trades=len(sell_trades),
        win_trades=len(win_trades),
        loss_trades=len(loss_trades),
        win_rate=win_rate,
        max_drawdown_pct=max_dd,
        profit_factor=profit_factor,
        max_concurrent_positions=max_concurrent,
        symbols_loaded=len(stock_data),
        trading_days_count=len(trading_days),
        no_signal_reason=no_signal_reason,
        equity_curve=equity_curve,
        trades=trades,
        symbol_stats=symbol_stats,
    )
