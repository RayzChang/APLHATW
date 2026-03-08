"""
K 線型態識別器

支援型態：
  - 費波納契回撤位（Fibonacci Retracement）
  - 雙頂（Double Top）
  - 雙底（Double Bottom）
  - 頭肩頂（Head and Shoulders Top）
  - 頭肩底（Inverse Head and Shoulders）
  - 三角收斂（Triangle：對稱 / 上升 / 下降）
  - 突破 / 跌破（Breakout / Breakdown）

所有偵測函數接受 pandas DataFrame（至少含 open/high/low/close/volume 欄位）。
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger


# ------------------------------------------------------------------ #
#   資料結構
# ------------------------------------------------------------------ #

@dataclass
class PatternResult:
    """單一 K 線型態的識別結果"""
    name:         str            # 型態名稱（繁中）
    pattern_id:   str            # 型態 ID（英文，供程式判斷）
    signal:       str            # "bullish" | "bearish" | "neutral"
    completion:   float          # 完成度 0~100%
    description:  str            # 白話說明（含具體數字）
    entry_price:  Optional[float] = None
    stop_loss:    Optional[float] = None
    take_profit:  Optional[float] = None
    confidence:   float = 0.5


# ------------------------------------------------------------------ #
#   內部工具
# ------------------------------------------------------------------ #

def _find_peaks(series: pd.Series, order: int = 5) -> list[int]:
    """找出局部最高點的 index（高點比左右各 order 根都高）"""
    peaks = []
    vals = series.values
    for i in range(order, len(vals) - order):
        window_max = max(vals[i - order: i + order + 1])
        if abs(vals[i] - window_max) < 1e-9:
            peaks.append(i)
    return peaks


def _find_troughs(series: pd.Series, order: int = 5) -> list[int]:
    """找出局部最低點的 index（低點比左右各 order 根都低）"""
    troughs = []
    vals = series.values
    for i in range(order, len(vals) - order):
        window_min = min(vals[i - order: i + order + 1])
        if abs(vals[i] - window_min) < 1e-9:
            troughs.append(i)
    return troughs


def _pct_diff(a: float, b: float) -> float:
    """兩個價格的百分比差距"""
    base = max(abs(a), abs(b))
    return abs(a - b) / base if base > 0 else 0.0


# ------------------------------------------------------------------ #
#   費波納契回撤
# ------------------------------------------------------------------ #

def detect_fibonacci(df: pd.DataFrame, lookback: int = 60) -> dict:
    """
    計算費波納契回撤位（基於最近 lookback 根 K 線的高低點）。

    回傳：
    {
        "swing_high": float,
        "swing_low":  float,
        "trend":      "uptrend" | "downtrend",
        "levels": {"0.0": float, "0.236": float, ...},
        "current_near_level": str | None,    # 距離現價最近的 Fib 位標籤
        "near_support":       bool,          # 現價在支撐位附近（2% 內）
        "near_resistance":    bool,
        "nearest_dist_pct":   float,         # 距最近 Fib 位的百分比距離
    }
    """
    recent  = df.tail(lookback)
    sw_high = float(recent["high"].max())
    sw_low  = float(recent["low"].min())
    current = float(df["close"].iloc[-1])
    diff    = sw_high - sw_low

    if diff < 1e-9:
        return {}

    # 趨勢：比較前後半段均價
    mid   = len(recent) // 2
    trend = (
        "uptrend"
        if recent["close"].iloc[mid:].mean() > recent["close"].iloc[:mid].mean()
        else "downtrend"
    )

    # 費波納契比率（從高點回撤或從低點反彈）
    ratios = [0.0, 0.236, 0.382, 0.500, 0.618, 0.786, 1.0]
    if trend == "uptrend":
        levels = {str(r): round(sw_high - diff * r, 2) for r in ratios}
    else:
        levels = {str(r): round(sw_low + diff * r, 2) for r in ratios}

    # 找最近的 Fib 位
    nearest_label = "0.0"
    nearest_dist  = float("inf")
    for label, price in levels.items():
        d = abs(current - price) / current
        if d < nearest_dist:
            nearest_dist  = d
            nearest_label = label

    threshold = 0.02  # 2% 以內視為「靠近」
    near_support    = False
    near_resistance = False

    if nearest_dist < threshold:
        if trend == "uptrend":
            near_support    = nearest_label in ("0.618", "0.500", "0.382")
            near_resistance = nearest_label in ("0.236", "0.0")
        else:
            near_support    = nearest_label in ("0.382", "0.500", "0.618")
            near_resistance = nearest_label in ("0.786", "1.0")

    return {
        "swing_high":         sw_high,
        "swing_low":          sw_low,
        "trend":              trend,
        "levels":             levels,
        "current_near_level": nearest_label if nearest_dist < threshold else None,
        "near_support":       near_support,
        "near_resistance":    near_resistance,
        "nearest_dist_pct":   round(nearest_dist * 100, 2),
    }


# ------------------------------------------------------------------ #
#   雙頂
# ------------------------------------------------------------------ #

def detect_double_top(
    df: pd.DataFrame,
    lookback: int  = 60,
    tolerance: float = 0.03,
) -> Optional[PatternResult]:
    """
    雙頂偵測（看跌反轉）。
    條件：
      - 兩個相近的局部高點（高度差 < tolerance）
      - 中間有明顯低谷（距高點 > 3%）
      - 現價接近或已跌破頸線
    """
    recent = df.tail(lookback).reset_index(drop=True)
    peaks  = _find_peaks(recent["high"], order=4)
    if len(peaks) < 2:
        return None

    p1_idx, p2_idx = peaks[-2], peaks[-1]
    p1 = float(recent["high"].iloc[p1_idx])
    p2 = float(recent["high"].iloc[p2_idx])
    current = float(recent["close"].iloc[-1])

    if _pct_diff(p1, p2) > tolerance:
        return None

    valley = recent["low"].iloc[p1_idx:p2_idx + 1]
    if valley.empty:
        return None
    neckline  = float(valley.min())
    neck_drop = (max(p1, p2) - neckline) / max(p1, p2)
    if neck_drop < 0.03:
        return None

    target = round(neckline - (max(p1, p2) - neckline), 2)

    if current <= neckline:
        completion  = 100.0
        description = (
            f"雙頂確認！現價 {current:.2f} 跌破頸線 {neckline:.2f}，"
            f"兩頂 {p1:.2f}/{p2:.2f}，下跌目標 {target:.2f}"
        )
    else:
        pct        = (current - neckline) / max((max(p1, p2) - neckline), 1e-9)
        completion = round(50 + 50 * (1 - min(pct, 1)), 1)
        description = (
            f"雙頂形成中（{completion:.0f}%），頸線 {neckline:.2f}，"
            f"兩頂 {p1:.2f}/{p2:.2f}，跌破後目標 {target:.2f}"
        )

    return PatternResult(
        name        = "雙頂",
        pattern_id  = "double_top",
        signal      = "bearish",
        completion  = completion,
        description = description,
        entry_price = round(neckline * 0.995, 2),
        stop_loss   = round(max(p1, p2) * 1.01, 2),
        take_profit = target,
        confidence  = round(min(completion / 100, 0.88), 2),
    )


# ------------------------------------------------------------------ #
#   雙底
# ------------------------------------------------------------------ #

def detect_double_bottom(
    df: pd.DataFrame,
    lookback: int  = 60,
    tolerance: float = 0.03,
) -> Optional[PatternResult]:
    """
    雙底偵測（看多反轉）。
    條件：
      - 兩個相近的局部低點（差距 < tolerance）
      - 中間有明顯高點（距低點 > 3%）
      - 現價接近或已突破頸線
    """
    recent  = df.tail(lookback).reset_index(drop=True)
    troughs = _find_troughs(recent["low"], order=4)
    if len(troughs) < 2:
        return None

    t1_idx, t2_idx = troughs[-2], troughs[-1]
    t1 = float(recent["low"].iloc[t1_idx])
    t2 = float(recent["low"].iloc[t2_idx])
    current = float(recent["close"].iloc[-1])

    if _pct_diff(t1, t2) > tolerance:
        return None

    peak_slice = recent["high"].iloc[t1_idx:t2_idx + 1]
    if peak_slice.empty:
        return None
    neckline  = float(peak_slice.max())
    neck_rise = (neckline - min(t1, t2)) / min(t1, t2)
    if neck_rise < 0.03:
        return None

    target = round(neckline + (neckline - min(t1, t2)), 2)

    if current >= neckline:
        completion  = 100.0
        description = (
            f"雙底確認！現價 {current:.2f} 突破頸線 {neckline:.2f}，"
            f"兩底 {t1:.2f}/{t2:.2f}，上漲目標 {target:.2f}"
        )
    else:
        pct        = (neckline - current) / max((neckline - min(t1, t2)), 1e-9)
        completion = round(50 + 50 * (1 - min(pct, 1)), 1)
        description = (
            f"雙底形成中（{completion:.0f}%），頸線 {neckline:.2f}，"
            f"兩底 {t1:.2f}/{t2:.2f}，突破後目標 {target:.2f}"
        )

    return PatternResult(
        name        = "雙底",
        pattern_id  = "double_bottom",
        signal      = "bullish",
        completion  = completion,
        description = description,
        entry_price = round(neckline * 1.005, 2),
        stop_loss   = round(min(t1, t2) * 0.99, 2),
        take_profit = target,
        confidence  = round(min(completion / 100, 0.88), 2),
    )


# ------------------------------------------------------------------ #
#   頭肩頂
# ------------------------------------------------------------------ #

def detect_head_shoulders(
    df: pd.DataFrame,
    lookback: int  = 80,
    tolerance: float = 0.05,
) -> Optional[PatternResult]:
    """
    頭肩頂偵測（看跌反轉）。
    條件：左肩 < 頭 > 右肩，左右肩高度相近。
    """
    recent = df.tail(lookback).reset_index(drop=True)
    peaks  = _find_peaks(recent["high"], order=5)
    if len(peaks) < 3:
        return None

    ls_i, h_i, rs_i = peaks[-3], peaks[-2], peaks[-1]
    ls   = float(recent["high"].iloc[ls_i])
    head = float(recent["high"].iloc[h_i])
    rs   = float(recent["high"].iloc[rs_i])

    if not (head > ls and head > rs):
        return None
    if _pct_diff(ls, rs) > tolerance:
        return None

    try:
        left_neck  = float(recent["low"].iloc[ls_i:h_i].min())
        right_neck = float(recent["low"].iloc[h_i:rs_i].min())
        neckline   = (left_neck + right_neck) / 2
    except Exception:
        return None

    current       = float(recent["close"].iloc[-1])
    pattern_height = head - neckline
    target         = round(neckline - pattern_height, 2)

    if current <= neckline:
        completion  = 100.0
        description = (
            f"頭肩頂確認！跌破頸線 {neckline:.2f}，"
            f"頭部 {head:.2f}，下跌目標 {target:.2f}"
        )
    else:
        pct        = (current - neckline) / max(pattern_height, 1e-9)
        completion = round(70 + 30 * (1 - min(pct, 1)), 1)
        description = (
            f"頭肩頂形成中（{completion:.0f}%），頸線 {neckline:.2f}，"
            f"左肩 {ls:.2f} / 頭 {head:.2f} / 右肩 {rs:.2f}，目標 {target:.2f}"
        )

    return PatternResult(
        name        = "頭肩頂",
        pattern_id  = "head_shoulders_top",
        signal      = "bearish",
        completion  = completion,
        description = description,
        entry_price = round(neckline * 0.995, 2),
        stop_loss   = round(head * 1.01, 2),
        take_profit = target,
        confidence  = round(min(completion / 100 * 0.85, 0.85), 2),
    )


# ------------------------------------------------------------------ #
#   頭肩底
# ------------------------------------------------------------------ #

def detect_inverse_head_shoulders(
    df: pd.DataFrame,
    lookback: int  = 80,
    tolerance: float = 0.05,
) -> Optional[PatternResult]:
    """
    頭肩底偵測（看多反轉）。
    條件：左肩 > 頭 < 右肩，左右肩低點相近。
    """
    recent  = df.tail(lookback).reset_index(drop=True)
    troughs = _find_troughs(recent["low"], order=5)
    if len(troughs) < 3:
        return None

    ls_i, h_i, rs_i = troughs[-3], troughs[-2], troughs[-1]
    ls   = float(recent["low"].iloc[ls_i])
    head = float(recent["low"].iloc[h_i])
    rs   = float(recent["low"].iloc[rs_i])

    if not (head < ls and head < rs):
        return None
    if _pct_diff(ls, rs) > tolerance:
        return None

    try:
        left_neck  = float(recent["high"].iloc[ls_i:h_i].max())
        right_neck = float(recent["high"].iloc[h_i:rs_i].max())
        neckline   = (left_neck + right_neck) / 2
    except Exception:
        return None

    current        = float(recent["close"].iloc[-1])
    pattern_height = neckline - head
    target         = round(neckline + pattern_height, 2)

    if current >= neckline:
        completion  = 100.0
        description = (
            f"頭肩底確認！突破頸線 {neckline:.2f}，"
            f"頭部低點 {head:.2f}，上漲目標 {target:.2f}"
        )
    else:
        pct        = (neckline - current) / max(pattern_height, 1e-9)
        completion = round(70 + 30 * (1 - min(pct, 1)), 1)
        description = (
            f"頭肩底形成中（{completion:.0f}%），頸線 {neckline:.2f}，"
            f"左肩 {ls:.2f} / 頭部 {head:.2f} / 右肩 {rs:.2f}，目標 {target:.2f}"
        )

    return PatternResult(
        name        = "頭肩底",
        pattern_id  = "head_shoulders_bottom",
        signal      = "bullish",
        completion  = completion,
        description = description,
        entry_price = round(neckline * 1.005, 2),
        stop_loss   = round(head * 0.99, 2),
        take_profit = target,
        confidence  = round(min(completion / 100 * 0.85, 0.85), 2),
    )


# ------------------------------------------------------------------ #
#   三角收斂
# ------------------------------------------------------------------ #

def detect_triangle(
    df: pd.DataFrame,
    lookback: int = 60,
) -> Optional[PatternResult]:
    """
    三角收斂偵測（對稱 / 上升 / 下降）。
    使用最小二乘法計算高點趨勢線與低點趨勢線的斜率。
    """
    recent = df.tail(lookback).reset_index(drop=True)
    if len(recent) < 20:
        return None

    highs  = recent["high"].values.astype(float)
    lows   = recent["low"].values.astype(float)
    closes = recent["close"].values.astype(float)
    x      = np.arange(len(recent), dtype=float)

    high_slope = np.polyfit(x, highs, 1)[0]
    low_slope  = np.polyfit(x, lows,  1)[0]
    high_mean  = highs.mean()
    low_mean   = lows.mean()

    # 正規化斜率（消除絕對價格影響）
    hn = high_slope / high_mean if high_mean else 0
    ln = low_slope  / low_mean  if low_mean  else 0

    flat = 0.0003

    is_symmetric  = hn < -flat and ln > flat            # 對稱：高降低升
    is_ascending  = abs(hn) < flat and ln > flat * 2    # 上升：高平低升（偏多）
    is_descending = hn < -flat * 2 and abs(ln) < flat   # 下降：高降低平（偏空）

    if not (is_symmetric or is_ascending or is_descending):
        return None

    # 估計壓縮比（當前波幅 vs 起始波幅）
    curr_range = float(recent["high"].tail(10).max() - recent["low"].tail(10).min())
    init_range = float(recent["high"].head(10).max() - recent["low"].head(10).min())
    compression = 1 - (curr_range / init_range) if init_range > 1e-9 else 0
    completion  = round(min(max(compression * 100, 30), 95), 1)

    resistance = float(recent["high"].tail(10).mean())
    support    = float(recent["low"].tail(10).mean())
    current    = float(closes[-1])
    spread     = resistance - support

    if is_ascending:
        signal = "bullish"
        name   = "上升三角"
        desc   = (
            f"上升三角收斂（{completion:.0f}%），低點持續墊高，"
            f"等待突破壓力 {resistance:.2f}，目標 {resistance + spread:.2f}"
        )
        entry  = round(resistance * 1.005, 2)
        sl     = round(support * 0.98, 2)
        tp     = round(resistance + spread, 2)
    elif is_descending:
        signal = "bearish"
        name   = "下降三角"
        desc   = (
            f"下降三角收斂（{completion:.0f}%），高點持續下壓，"
            f"等待跌破支撐 {support:.2f}，目標 {support - spread:.2f}"
        )
        entry  = round(support * 0.995, 2)
        sl     = round(resistance * 1.02, 2)
        tp     = round(support - spread, 2)
    else:
        signal = "neutral"
        name   = "對稱三角"
        desc   = (
            f"對稱三角收斂（{completion:.0f}%），"
            f"壓力 {resistance:.2f} / 支撐 {support:.2f}，等待方向性突破"
        )
        entry  = round(resistance * 1.005, 2)
        sl     = round(support * 0.98, 2)
        tp     = round(resistance + spread, 2)

    return PatternResult(
        name        = name,
        pattern_id  = "triangle",
        signal      = signal,
        completion  = completion,
        description = desc,
        entry_price = entry,
        stop_loss   = sl,
        take_profit = tp,
        confidence  = round(min(completion / 100 * 0.75, 0.72), 2),
    )


# ------------------------------------------------------------------ #
#   突破 / 跌破
# ------------------------------------------------------------------ #

def detect_breakout(
    df: pd.DataFrame,
    lookback: int = 20,
) -> Optional[PatternResult]:
    """
    突破 / 跌破偵測。
    現收盤突破前 N 日最高 → 看多突破
    現收盤跌破前 N 日最低 → 看空跌破
    """
    if len(df) < lookback + 5:
        return None

    window     = df.tail(lookback + 1).head(lookback)   # 排除最新一根
    current    = float(df["close"].iloc[-1])
    prev_close = float(df["close"].iloc[-2])
    resistance = float(window["high"].max())
    support    = float(window["low"].min())
    atr_approx = float((window["high"] - window["low"]).mean())

    # 向上突破
    if current > resistance and prev_close <= resistance:
        return PatternResult(
            name        = "向上突破",
            pattern_id  = "breakout_up",
            signal      = "bullish",
            completion  = 100.0,
            description = (
                f"價格突破近 {lookback} 日高點 {resistance:.2f}，"
                f"突破幅度 {(current / resistance - 1) * 100:.1f}%"
            ),
            entry_price = round(current, 2),
            stop_loss   = round(resistance * 0.98, 2),
            take_profit = round(current + atr_approx * 2, 2),
            confidence  = 0.78,
        )

    # 向下跌破
    if current < support and prev_close >= support:
        return PatternResult(
            name        = "向下跌破",
            pattern_id  = "breakdown",
            signal      = "bearish",
            completion  = 100.0,
            description = (
                f"價格跌破近 {lookback} 日低點 {support:.2f}，"
                f"跌幅 {(1 - current / support) * 100:.1f}%"
            ),
            entry_price = round(current, 2),
            stop_loss   = round(support * 1.02, 2),
            take_profit = round(current - atr_approx * 2, 2),
            confidence  = 0.78,
        )

    return None


# ------------------------------------------------------------------ #
#   一鍵全偵測
# ------------------------------------------------------------------ #

def detect_all_patterns(df: pd.DataFrame) -> dict:
    """
    執行全部型態偵測。

    回傳：
    {
        "detected":  list[dict],       # 所有偵測到的型態（dict 格式）
        "primary":   dict | None,      # 最高信心度的型態
        "fibonacci": dict,             # 費波納契位資訊
        "summary":   str,              # 一句話摘要
    }
    """
    if df.empty or len(df) < 30:
        return {
            "detected":  [],
            "primary":   None,
            "fibonacci": {},
            "summary":   "資料不足，無法識別型態",
        }

    # 費波納契（獨立輸出）
    try:
        fib = detect_fibonacci(df)
    except Exception:
        fib = {}

    # 各型態偵測
    detectors = [
        lambda d: detect_double_bottom(d),
        lambda d: detect_double_top(d),
        lambda d: detect_inverse_head_shoulders(d),
        lambda d: detect_head_shoulders(d),
        lambda d: detect_triangle(d),
        lambda d: detect_breakout(d, lookback=20),
    ]

    detected: list[PatternResult] = []
    for fn in detectors:
        try:
            result = fn(df)
            if result:
                detected.append(result)
        except Exception as e:
            logger.debug(f"Pattern detection error: {e}")

    if not detected:
        primary = None
        summary = "無明顯 K 線型態，建議等待更清晰的訊號"
    else:
        # 按「完成度 × 信心度」排序，取最高者為主要型態
        detected.sort(key=lambda r: r.completion * r.confidence, reverse=True)
        primary = detected[0]
        summary = primary.description

    return {
        "detected":  [_to_dict(p) for p in detected],
        "primary":   _to_dict(primary) if primary else None,
        "fibonacci": fib,
        "summary":   summary,
    }


def _to_dict(p: PatternResult) -> dict:
    return {
        "name":         p.name,
        "pattern_id":   p.pattern_id,
        "signal":       p.signal,
        "completion":   p.completion,
        "description":  p.description,
        "entry_price":  p.entry_price,
        "stop_loss":    p.stop_loss,
        "take_profit":  p.take_profit,
        "confidence":   p.confidence,
    }
