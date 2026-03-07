"""
台股技術指標 — KD、RSI、MACD、布林、MA20、量比

選股器與回測用
"""

import pandas as pd
import ta
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, SMAIndicator
from ta.volatility import BollingerBands
from loguru import logger


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """計算所有選股器所需指標"""
    if df.empty or len(df) < 30:
        return df
    df = df.copy()
    df = add_rsi(df)
    df = add_kd(df)
    df = add_macd(df)
    df = add_bollinger(df)
    df = add_ma20(df)
    df = add_volume_ratio(df)
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """RSI"""
    rsi = RSIIndicator(close=df["close"], window=period)
    df["rsi"] = rsi.rsi()
    return df


def add_kd(df: pd.DataFrame, k_period: int = 9, d_period: int = 3) -> pd.DataFrame:
    """KD 指標（Stochastic Oscillator）"""
    stoch = StochasticOscillator(
        high=df["high"], low=df["low"], close=df["close"],
        window=k_period, smooth_window=d_period,
    )
    df["kd_k"] = stoch.stoch()
    df["kd_d"] = stoch.stoch_signal()
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD"""
    macd = MACD(close=df["close"], window_fast=fast, window_slow=slow, window_sign=signal)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()
    return df


def add_bollinger(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.DataFrame:
    """布林通道 — 計算 %B (bb_pct)"""
    bb = BollingerBands(close=df["close"], window=period, window_dev=std)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_middle"] = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_pct"] = (df["close"] - df["bb_lower"]) / (df["bb_middle"] - df["bb_lower"] + 1e-10)
    return df


def add_ma20(df: pd.DataFrame) -> pd.DataFrame:
    """20 日均線"""
    sma = SMAIndicator(close=df["close"], window=20)
    df["ma20"] = sma.sma_indicator()
    return df


def add_volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """量比 = 今日量 / 20 日均量"""
    df["vol_ma20"] = df["volume"].rolling(period).mean()
    df["vol_ratio"] = df["volume"] / (df["vol_ma20"] + 1e-10)
    return df


def calc_buy_sell_score(row: pd.Series) -> int:
    """
    綜合評分：買入 +1，賣出 -1，加總
    ≥2 偏買，≤-2 偏賣
    """
    score = 0
    if pd.notna(row.get("rsi")):
        if row["rsi"] < 30:
            score += 1
        elif row["rsi"] > 70:
            score -= 1
    if pd.notna(row.get("kd_k")) and pd.notna(row.get("kd_d")):
        if row["kd_k"] > row["kd_d"] and row["kd_k"] < 30:
            score += 1
        elif row["kd_k"] < row["kd_d"] and row["kd_k"] > 70:
            score -= 1
    if pd.notna(row.get("macd_hist")):
        if row["macd_hist"] > 0:
            score += 1
        else:
            score -= 1
    if pd.notna(row.get("ma20")):
        if row["close"] > row["ma20"]:
            score += 1
        else:
            score -= 1
    if pd.notna(row.get("bb_pct")):
        if row["bb_pct"] < 0:
            score += 1
        elif row["bb_pct"] > 1:
            score -= 1
    return score
