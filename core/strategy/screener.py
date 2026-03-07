import time
import pandas as pd
from loguru import logger
from datetime import datetime, timedelta
from core.data.tw_data_fetcher import TWDataFetcher

class StockScreener:
    """
    股票篩選器，利用技術指標快速初步篩選標的。
    """
    MAX_CANDIDATES = 20

    def __init__(self, data_fetcher: TWDataFetcher):
        self.fetcher = data_fetcher

    def _calculate_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        """計算 RSI 指標"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        
        # 使用簡單移動平均 (SMA) 作為初步實現
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def screen_universe(self, stock_ids: list[str]) -> list[str]:
        """
        [DEPRECATED] 這是單執行緒版本，建議使用 screen_batch。
        """
        return self.screen_batch(stock_ids)

    def screen_batch(self, stock_ids: list[str], batch_size: int = 20) -> list[str]:
        """
        分批篩選股票。
        """
        logger.info(f"Starting batch screening for {len(stock_ids)} stocks...")
        candidates = []
        
        for i in range(0, len(stock_ids), batch_size):
            batch = stock_ids[i:i + batch_size]
            logger.info(f"Screening batch {i//batch_size + 1}: {batch}")
            
            # Step 1-3: 使用即時報價進行初步過濾 (Volume, Price, ChangePct)
            quotes = self.fetcher.fetch_realtime_batch(batch)
            
            for sid, quote in quotes.items():
                try:
                    price = quote.get("price", 0)
                    volume = quote.get("volume", 0)
                    change_pct = quote.get("change_pct", 0)
                    
                    # 1. 成交量過濾 (> 500張)
                    if volume <= 500:
                        continue
                    
                    # 2. 價格過濾 (10 ~ 3000 元)
                    if not (10 <= price <= 3000):
                        continue
                    
                    # 3. 漲跌幅過濾 (|change_pct| < 9.5)
                    if abs(change_pct) >= 9.5:
                        continue
                        
                    # Step 4-5: 技術指標過濾 (RSI, MA20)
                    # 抓取近 60 天資料以確保 MA20 與 RSI14 計算穩定
                    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
                    df = self.fetcher.fetch_klines(sid, start_date=start_date)
                    
                    if len(df) < 20: # 資料不足 MA20
                        continue
                    
                    # 計算 MA20
                    ma20 = df['close'].rolling(window=20).mean().iloc[-1]
                    
                    # 5. 均線過濾 (當日收盤價 > MA20)
                    if price <= ma20:
                        continue
                    
                    # 計算 RSI
                    rsi_series = self._calculate_rsi(df['close'], period=14)
                    rsi = rsi_series.iloc[-1]
                    
                    # 4. RSI過濾 (25 < RSI < 75)
                    if not (25 < rsi < 75):
                        continue
                    
                    # 通過所有條件
                    candidates.append({
                        "stock_id": sid,
                        "change_pct_abs": abs(change_pct),
                        "price": price,
                        "rsi": rsi,
                        "ma20": ma20
                    })
                    logger.success(f"Stock {sid} passed screening.")
                    
                except Exception as e:
                    logger.warning(f"Error screening {sid}: {e}")
            
            # 每批之間延遲避免頻繁請求
            if i + batch_size < len(stock_ids):
                time.sleep(0.5)
        
        # 最終排序與截斷
        # 依 change_pct 絕對值由小到大排序 (使用者要求)
        candidates.sort(key=lambda x: x["change_pct_abs"])
        
        final_list = [c["stock_id"] for c in candidates[:self.MAX_CANDIDATES]]
        logger.info(f"Screening complete. Found {len(final_list)} candidates: {final_list}")
        
        return final_list
