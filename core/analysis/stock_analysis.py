"""
智慧選股 — 資訊面、技術面、籌碼面

使用者有興趣的幾家公司，AI 撈取完整資料供使用者衡量是否可買。
決策由使用者自己做，系統只提供資訊。
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from core.data.tw_data_fetcher import TWDataFetcher
from core.analysis.indicators import add_all_indicators, calc_buy_sell_score


@dataclass
class StockAnalysisResult:
    symbol: str
    name: str
    close: float
    change_pct: float
    recommendation: str  # 建議買入 | 建議賣出 | 觀望（技術面）
    suggested_buy: list[float]
    suggested_sell: list[float]
    explanation: list[str]
    technical: dict  # 技術面
    fundamental: dict  # 資訊面：本益比、營收
    chip: dict  # 籌碼面：三大法人、融資融券


def analyze_stock(
    symbol: str,
    fetcher: Optional[TWDataFetcher] = None,
    days: int = 60,
) -> Optional[StockAnalysisResult]:
    """
    分析單一標的：近期狀況、建議、掛單位置、解釋
    """
    fetcher = fetcher or TWDataFetcher()
    end = datetime.now()
    start = (end - timedelta(days=days)).strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    df = fetcher.fetch_klines(symbol, start, end_str)
    if df.empty or len(df) < 30:
        return None

    df = add_all_indicators(df)
    row = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else row
    change_pct = ((row["close"] - prev["close"]) / prev["close"] * 100) if prev["close"] else 0
    name = fetcher.get_symbol_name(symbol)
    close = float(row["close"])

    # 指標
    rsi = row.get("rsi")
    kd_k = row.get("kd_k")
    kd_d = row.get("kd_d")
    macd_hist = row.get("macd_hist")
    ma20 = row.get("ma20")
    bb_upper = row.get("bb_upper")
    bb_lower = row.get("bb_lower")
    vol_ratio = row.get("vol_ratio")

    score = calc_buy_sell_score(row)
    technical = {
        "rsi": round(float(rsi), 1) if pd.notna(rsi) else None,
        "kd_k": round(float(kd_k), 1) if pd.notna(kd_k) else None,
        "kd_d": round(float(kd_d), 1) if pd.notna(kd_d) else None,
        "ma20": round(float(ma20), 2) if pd.notna(ma20) else None,
        "bb_upper": round(float(bb_upper), 2) if pd.notna(bb_upper) else None,
        "bb_lower": round(float(bb_lower), 2) if pd.notna(bb_lower) else None,
    }

    # 籌碼面
    chip: dict = {}
    if symbol not in ("TX", "MTX"):
        try:
            inst_df = fetcher.fetch_institutional_buy_sell(symbol, start, end_str)
            if not inst_df.empty and "date" in inst_df.columns:
                buy_col = "buy" if "buy" in inst_df.columns else "Buy"
                sell_col = "sell" if "sell" in inst_df.columns else "Sell"
                if buy_col in inst_df.columns and sell_col in inst_df.columns:
                    by_date = inst_df.groupby("date").agg({buy_col: "sum", sell_col: "sum"})
                    if not by_date.empty:
                        last = by_date.iloc[-1]
                        chip["inst_buy"] = round(float(last[buy_col]), 0)
                        chip["inst_sell"] = round(float(last[sell_col]), 0)
            margin_df = fetcher.fetch_margin_short(symbol, start, end_str)
            if not margin_df.empty:
                m = margin_df.iloc[-1]
                for k in ["MarginPurchaseTodayBalance", "TodayBalance"]:
                    if k in margin_df.columns:
                        v = m.get(k, m[k])
                        if pd.notna(v):
                            chip["margin_balance"] = int(float(v))
                        break
                for k in ["ShortSaleTodayBalance"]:
                    if k in margin_df.columns:
                        v = m.get(k, m[k])
                        if pd.notna(v):
                            chip["short_balance"] = int(float(v))
                        break
        except Exception:
            pass

    # 資訊面
    fundamental: dict = {}
    if symbol not in ("TX", "MTX"):
        try:
            per_pbr = fetcher.fetch_per_pbr(symbol)
            if per_pbr:
                fundamental["pe_ratio"] = per_pbr.get("pe_ratio")
                fundamental["pb_ratio"] = per_pbr.get("pb_ratio")
            rev_df = fetcher.fetch_month_revenue(symbol, (end - timedelta(days=365)).strftime("%Y-%m-%d"), end_str)
            if not rev_df.empty:
                rev_df = rev_df.sort_values("date", ascending=False)
                r0 = rev_df.iloc[0]
                fundamental["recent_revenue"] = r0.get("revenue") or r0.get("Revenue") or r0.get("value")
        except Exception:
            pass

    # 建議掛單價位
    suggested_buy: list[float] = []
    suggested_sell: list[float] = []
    explanation: list[str] = []

    if pd.notna(bb_lower) and bb_lower > 0:
        suggested_buy.append(round(float(bb_lower) * 0.99, 2))
    if pd.notna(ma20) and ma20 > 0:
        suggested_buy.append(round(float(ma20), 2))
    suggested_buy = sorted(set(suggested_buy))[:3]

    if pd.notna(bb_upper) and bb_upper > 0:
        suggested_sell.append(round(float(bb_upper) * 1.01, 2))
    if pd.notna(ma20) and ma20 > 0:
        suggested_sell.append(round(float(ma20), 2))
    suggested_sell = sorted(set(suggested_sell), reverse=True)[:3]

    # 白話解釋
    if pd.notna(rsi):
        if rsi < 30:
            explanation.append(f"RSI {rsi:.0f} 處於超賣區，短線可能反彈。")
        elif rsi > 70:
            explanation.append(f"RSI {rsi:.0f} 處於超買區，需留意回檔。")
        else:
            explanation.append(f"RSI {rsi:.0f} 中性區間。")

    if pd.notna(kd_k) and pd.notna(kd_d):
        if kd_k > kd_d:
            explanation.append("KD 黃金交叉，短線偏多。")
        else:
            explanation.append("KD 死亡交叉，短線偏空。")

    if pd.notna(macd_hist):
        if macd_hist > 0:
            explanation.append("MACD 柱狀翻正，動能轉多。")
        else:
            explanation.append("MACD 柱狀為負，動能偏空。")

    if pd.notna(ma20):
        if close > ma20:
            explanation.append(f"收盤站上 20 日均線 {ma20:.2f} 元，趨勢偏多。")
        else:
            explanation.append(f"收盤跌破 20 日均線 {ma20:.2f} 元，趨勢偏空。")

    if suggested_buy:
        explanation.append(f"可考慮在 {suggested_buy[0]:.2f}～{suggested_buy[-1]:.2f} 元區間掛單買入。")
    if suggested_sell:
        explanation.append(f"可考慮在 {suggested_sell[-1]:.2f}～{suggested_sell[0]:.2f} 元區間掛單賣出。")

    # 技術面結論（供參考，使用者自行衡量）
    if score >= 2:
        recommendation = "建議買入"
        explanation.insert(0, "綜合技術指標偏多，可考慮逢低布局。")
    elif score <= -2:
        recommendation = "建議賣出"
        explanation.insert(0, "綜合技術指標偏空，可考慮逢高減碼。")
    else:
        recommendation = "觀望"
        explanation.insert(0, "指標多空交雜，建議等待更明確訊號。")

    explanation.append("以上為系統分析，供您參考，請自行衡量是否可買。")

    return StockAnalysisResult(
        symbol=symbol,
        name=name,
        close=close,
        change_pct=round(change_pct, 2),
        recommendation=recommendation,
        suggested_buy=suggested_buy,
        suggested_sell=suggested_sell,
        explanation=explanation,
        technical=technical,
        fundamental=fundamental,
        chip=chip,
    )
