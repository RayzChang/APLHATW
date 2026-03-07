import pandas as pd
import numpy as np

class SLTPCalculator:
    """
    止損 (Stop Loss) 與 止盈 (Take Profit) 計算工具類別。
    提供基於 ATR、費波納契、保本及追蹤止損的計算方法。
    """

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """
        輸入包含 high/low/close 欄位的 DataFrame（日K線），計算 ATR（Average True Range）。
        
        Args:
            df: 包含 'high', 'low', 'close' 欄位的 pandas DataFrame。
            period: 計算週期，預設為 14。
            
        Returns:
            最新一根 K 線的 ATR 值 (float)。若資料不足則回傳 0.0。
        """
        if len(df) < period:
            return 0.0
            
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr_all = [high - low, 
                  (high - close).abs(), 
                  (low - close).abs()]
        tr = pd.concat(tr_all, axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return float(atr.iloc[-1])

    @staticmethod
    def calculate_atr_stop_loss(price: float, atr: float, multiplier: float = 2.0) -> float:
        """
        計算基於 ATR 的做多止損價。
        
        Args:
            price: 當前價格或成交價。
            atr: 當前 ATR 值。
            multiplier: ATR 倍數，預設為 2.0。
            
        Returns:
            止損價（四捨五入到小數點後 2 位）。
        """
        sl_price = price - (atr * multiplier)
        
        if sl_price >= price:
            sl_price = price * 0.95
            
        return round(sl_price, 2)

    @staticmethod
    def calculate_fibonacci_tp(current_price: float, swing_low: float, swing_high: float, atr: float, level: float = 0.618) -> float:
        """
        計算費波納契止盈價。
        - 均值回歸止盈：swing_low + (swing_high - swing_low) * level
        - 趨勢突破止盈：current_price + (swing_high - swing_low) * 1.618（當 level=1.618 時）
        
        Args:
            current_price: 當前市價。
            swing_low: 波段低點。
            swing_high: 波段高點。
            atr: 當前 ATR 值。
            level: 費波納契比率（如 0.618, 1.272, 1.618）。
            
        Returns:
            止盈點位價格。
        """
        if level > 1.0:
            # 趨勢擴展/突破止盈
            tp_price = current_price + (swing_high - swing_low) * level
        else:
            # 波段內回檔/均值回歸止盈
            tp_price = swing_low + (swing_high - swing_low) * level
            
        if tp_price <= current_price:
            # Fibonacci算出的TP低於現價，代表股價已突破區間
            # 改用趨勢延伸模式：以ATR為基礎計算上方目標
            tp_price = current_price + (atr * 3.0)
            
        return round(tp_price, 2)

    @staticmethod
    def calculate_breakeven_stop(entry_price: float, commission_rate: float = 0.001425) -> float:
        """
        台股保本止損價計算（考慮手續費）。
        台股手續費單邊 0.1425%，來回共 0.285%。
        
        Args:
            entry_price: 進場成交價。
            commission_rate: 單邊手續費率，預設為 0.001425 (0.1425%)。
            
        Returns:
            保本價格（損益平衡點）。
        """
        be_price = entry_price * (1 + commission_rate * 2)
        return round(be_price, 2)

    @staticmethod
    def calculate_trailing_stop(current_price: float, highest_price: float, trail_pct: float = 0.015) -> float:
        """
        計算動態追蹤止損價。
        
        Args:
            current_price: 當前市價。
            highest_price: 持倉期間達到的最高價。
            trail_pct: 追蹤比例，預設為 0.015 (1.5%)。
            
        Returns:
            追蹤止損觸發價。
        """
        ts_price = highest_price * (1 - trail_pct)
        return round(ts_price, 2)

    @staticmethod
    def get_swing_points(df: pd.DataFrame, lookback: int = 20) -> tuple[float, float]:
        """
        從最近 lookback 根 K 線中找出波段高點與低點。
        
        Args:
            df: 包含 'high', 'low' 欄位的 DataFrame。
            lookback: 回看 K 線根數。
            
        Returns:
            (swing_low, swing_high) 的元組。
        """
        recent_df = df.tail(lookback)
        swing_high = float(recent_df['high'].max())
        swing_low = float(recent_df['low'].min())
        return swing_low, swing_high
