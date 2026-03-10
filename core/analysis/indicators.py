"""
台股技術指標 — KD、RSI、MACD、布林、MA、ATR、量比

相容舊版 ta 庫（參數名稱為 n= 而非 window=）
"""

import pandas as pd
from loguru import logger

try:
    from ta.momentum import RSIIndicator, StochasticOscillator
    from ta.trend import MACD, SMAIndicator, EMAIndicator
    from ta.volatility import BollingerBands, AverageTrueRange
    import inspect

    # 自動偵測 ta 版本：新版用 window=，舊版用 n=
    _RSI_USE_WINDOW = "window" in inspect.signature(RSIIndicator.__init__).parameters
except ImportError:
    logger.error("ta library not installed, indicators will be empty")
    _RSI_USE_WINDOW = False


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """計算所有選股器所需指標"""
    if df.empty or len(df) < 30:
        return df
    df = df.copy()
    df = add_rsi(df)
    df = add_kd(df)
    df = add_macd(df)
    df = add_bollinger(df)
    df = add_ma(df)
    df = add_atr(df)
    df = add_volume_ratio(df)
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """RSI（相容新舊版 ta）"""
    try:
        if _RSI_USE_WINDOW:
            rsi = RSIIndicator(close=df["close"], window=period)
        else:
            rsi = RSIIndicator(close=df["close"], n=period)
        df["rsi"] = rsi.rsi()
    except Exception as e:
        logger.warning(f"add_rsi error: {e}")
        df["rsi"] = float("nan")
    return df


def add_kd(df: pd.DataFrame, k_period: int = 9, d_period: int = 3) -> pd.DataFrame:
    """KD 指標（Stochastic Oscillator，相容新舊版 ta）"""
    try:
        if _RSI_USE_WINDOW:
            stoch = StochasticOscillator(
                high=df["high"], low=df["low"], close=df["close"],
                window=k_period, smooth_window=d_period,
            )
            df["kd_k"] = stoch.stoch()
            df["kd_d"] = stoch.stoch_signal()
        else:
            stoch = StochasticOscillator(
                high=df["high"], low=df["low"], close=df["close"],
                n=k_period, d_n=d_period,
            )
            df["kd_k"] = stoch.stoch()
            df["kd_d"] = stoch.stoch_signal()
    except Exception as e:
        logger.warning(f"add_kd error: {e}")
        df["kd_k"] = float("nan")
        df["kd_d"] = float("nan")
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD（相容新舊版 ta）"""
    try:
        if _RSI_USE_WINDOW:
            macd = MACD(close=df["close"], window_fast=fast, window_slow=slow, window_sign=signal)
        else:
            macd = MACD(close=df["close"], n_fast=fast, n_slow=slow, n_sign=signal)
        df["macd"]        = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["macd_hist"]   = macd.macd_diff()
    except Exception as e:
        logger.warning(f"add_macd error: {e}")
        df["macd"] = df["macd_signal"] = df["macd_hist"] = float("nan")
    return df


def add_bollinger(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.DataFrame:
    """布林通道（相容新舊版 ta）"""
    try:
        if _RSI_USE_WINDOW:
            bb = BollingerBands(close=df["close"], window=period, window_dev=std)
        else:
            bb = BollingerBands(close=df["close"], n=period, ndev=int(std))
        df["bb_upper"]  = bb.bollinger_hband()
        df["bb_middle"] = bb.bollinger_mavg()
        df["bb_lower"]  = bb.bollinger_lband()
        df["bb_pct"] = (
            (df["close"] - df["bb_lower"])
            / (df["bb_upper"] - df["bb_lower"] + 1e-10)
        )
    except Exception as e:
        logger.warning(f"add_bollinger error: {e}")
        df["bb_upper"] = df["bb_middle"] = df["bb_lower"] = df["bb_pct"] = float("nan")
    return df


def add_ma(df: pd.DataFrame) -> pd.DataFrame:
    """MA5 / MA20 / MA60 均線（相容新舊版 ta）"""
    try:
        if _RSI_USE_WINDOW:
            df["ma5"]  = SMAIndicator(close=df["close"], window=5).sma_indicator()
            df["ma20"] = SMAIndicator(close=df["close"], window=20).sma_indicator()
            df["ma60"] = SMAIndicator(close=df["close"], window=60).sma_indicator()
        else:
            df["ma5"]  = SMAIndicator(close=df["close"], n=5).sma_indicator()
            df["ma20"] = SMAIndicator(close=df["close"], n=20).sma_indicator()
            df["ma60"] = SMAIndicator(close=df["close"], n=60).sma_indicator()
    except Exception as e:
        logger.warning(f"add_ma error: {e}")
        # Fallback: pure pandas rolling mean
        df["ma5"]  = df["close"].rolling(5).mean()
        df["ma20"] = df["close"].rolling(20).mean()
        df["ma60"] = df["close"].rolling(60).mean()
    return df


# 向後相容
def add_ma20(df: pd.DataFrame) -> pd.DataFrame:
    return add_ma(df)


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """ATR（相容新舊版 ta）"""
    try:
        if _RSI_USE_WINDOW:
            atr = AverageTrueRange(
                high=df["high"], low=df["low"], close=df["close"], window=period
            )
        else:
            atr = AverageTrueRange(
                high=df["high"], low=df["low"], close=df["close"], n=period
            )
        df["atr"] = atr.average_true_range()
    except Exception as e:
        logger.warning(f"add_atr error: {e}")
        # Fallback: 14-day average of high-low range
        df["atr"] = (df["high"] - df["low"]).rolling(period).mean()
    return df


def add_volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """量比 = 今日量 / 20 日均量"""
    df["vol_ma20"]  = df["volume"].rolling(period).mean()
    df["vol_ratio"] = df["volume"] / (df["vol_ma20"] + 1e-10)
    return df


def calc_buy_sell_score(row: pd.Series) -> int:
    """
    綜合技術評分（滿分 +8）。
    每個指標在合理條件下 +1（偏多）或 -1（偏空），
    設計上 score >= 3 為「多項指標共振確認」的高品質進場訊號。

    指標：RSI、KD、MACD、價格>MA20、MA5>MA20（趨勢）、布林、量能
    """
    score = 0
    close = row.get("close", 0)

    # 1. RSI：放寬區間，不只看極端超賣
    rsi = row.get("rsi")
    if pd.notna(rsi):
        if rsi < 30:
            score += 2
        elif rsi < 45:
            score += 1
        elif rsi > 70:
            score -= 1

    # 2. KD 黃金交叉：放寬到 K < 50（下半區交叉比上半區有意義）
    k, d = row.get("kd_k"), row.get("kd_d")
    if pd.notna(k) and pd.notna(d):
        if k > d and k < 50:
            score += 1
        elif k < d and k > 50:
            score -= 1

    # 3. MACD 柱狀圖方向
    macd_hist = row.get("macd_hist")
    if pd.notna(macd_hist):
        if macd_hist > 0:
            score += 1
        else:
            score -= 1

    # 4. 收盤價 vs MA20
    ma20 = row.get("ma20")
    if pd.notna(ma20) and close > 0:
        if close > ma20:
            score += 1
        else:
            score -= 1

    # 5. 短期趨勢確認：MA5 > MA20
    ma5 = row.get("ma5")
    if pd.notna(ma5) and pd.notna(ma20):
        if ma5 > ma20:
            score += 1
        else:
            score -= 1

    # 6. 布林通道位置（標準 %B）
    bb_pct = row.get("bb_pct")
    if pd.notna(bb_pct):
        if bb_pct < 0.2:
            score += 1
        elif bb_pct > 0.8:
            score -= 1

    # 7. 量能確認：日成交量 > 20 日均量 1.2 倍
    vol_ratio = row.get("vol_ratio")
    if pd.notna(vol_ratio):
        if vol_ratio >= 1.2:
            score += 1

    return score


def build_indicator_snapshot(row: pd.Series) -> dict:
    """Return a normalized indicator snapshot for screening / analysis layers."""
    return {
        "rsi": float(row.get("rsi", 0) or 0),
        "kd_k": float(row.get("kd_k", 0) or 0),
        "kd_d": float(row.get("kd_d", 0) or 0),
        "macd": float(row.get("macd", 0) or 0),
        "macd_signal": float(row.get("macd_signal", 0) or 0),
        "macd_hist": float(row.get("macd_hist", 0) or 0),
        "ma5": float(row.get("ma5", 0) or 0),
        "ma20": float(row.get("ma20", 0) or 0),
        "ma60": float(row.get("ma60", 0) or 0),
        "bb_upper": float(row.get("bb_upper", 0) or 0),
        "bb_lower": float(row.get("bb_lower", 0) or 0),
        "bb_pct": float(row.get("bb_pct", 0) or 0),
        "atr": float(row.get("atr", 0) or 0),
        "vol_ratio": float(row.get("vol_ratio", 0) or 0),
        "volume": float(row.get("volume", 0) or 0),
        "close": float(row.get("close", 0) or 0),
        "high": float(row.get("high", 0) or 0),
        "low": float(row.get("low", 0) or 0),
    }
