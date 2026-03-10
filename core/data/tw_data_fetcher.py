"""
台股資料抓取器 (TWDataFetcher)

資料來源：
  - 即時報價：TWSE / TPEX MIS Open API（免費，無需 Token）
  - 歷史 K 線 / 三大法人 / 融資融券 / 本益比 / 月營收：FinMind API
"""

from datetime import datetime, timedelta
from typing import Optional

import requests
import json
import pandas as pd
from loguru import logger

from FinMind.data import DataLoader

from config.settings import FINMIND_TOKEN

FUTURES_SYMBOLS = {"TX", "MTX", "TXF", "MXF"}

_STOCK_NAME_CACHE: dict[str, str] = {}
_STOCK_TYPE_CACHE: dict[str, str] = {}   # "tse" | "otc"
_CACHE_LOADED = False


class TWDataFetcher:
    """
    統一的台股資料抓取介面。
    所有對外 API 呼叫都集中在這裡，方便日後替換資料源。
    """

    def __init__(self):
        self._dl = DataLoader()
        if FINMIND_TOKEN:
            try:
                self._dl.login_by_token(api_token=FINMIND_TOKEN)
                logger.info("TWDataFetcher: FinMind logged in with token.")
            except Exception as e:
                logger.warning(f"TWDataFetcher: FinMind token login failed: {e}")
        else:
            logger.warning("TWDataFetcher: FINMIND_TOKEN not set, rate limit may apply.")
        # self._refresh_stock_info()  # Lazy loading: 改為需要時才呼叫

    # ------------------------------------------------------------------ #
    #   公開方法
    # ------------------------------------------------------------------ #

    def fetch_realtime_quote(self, stock_id: str) -> dict:
        """
        抓取單一標的即時報價。
        盤中：TWSE / TPEX MIS API 即時價。
        休市（週末、假日）：fallback 到 FinMind 最後一筆收盤價。
        回傳：{"price": float, "name": str, "open": float, "high": float,
                "low": float, "volume": int, "change": float, "change_pct": float,
                "is_realtime": bool}
        """
        if stock_id in FUTURES_SYMBOLS:
            return self._fetch_futures_quote(stock_id)

        market = _STOCK_TYPE_CACHE.get(stock_id, "tse")
        result = self._fetch_twse_quote(stock_id, market)
        if not result:
            other = "otc" if market == "tse" else "tse"
            result = self._fetch_twse_quote(stock_id, other)
            if result:
                _STOCK_TYPE_CACHE[stock_id] = other

        if result:
            result["is_realtime"] = True
            return result

        # TWSE MIS 無資料（休市）→ fallback 到 FinMind 最近 10 個交易日
        try:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
            df = self.fetch_klines(stock_id, start_date, end_date)
            if df is not None and not df.empty:
                last = df.iloc[-1]
                prev = df.iloc[-2] if len(df) >= 2 else last
                price = float(last["close"])
                prev_close = float(prev["close"])
                change = round(price - prev_close, 2)
                change_pct = round(change / prev_close * 100, 2) if prev_close else 0.0
                return {
                    "price": price,
                    "name": _STOCK_NAME_CACHE.get(stock_id, stock_id),
                    "open": float(last.get("open", price)),
                    "high": float(last.get("high", price)),
                    "low": float(last.get("low", price)),
                    "volume": int(last.get("volume", 0)),
                    "change": change,
                    "change_pct": change_pct,
                    "yesterday_close": prev_close,
                    "is_realtime": False,
                    "note": "休市中，顯示最後收盤價",
                }
        except Exception as e:
            logger.debug(f"fetch_realtime_quote fallback failed for {stock_id}: {e}")

        return {}

    def fetch_stock_daily(self, stock_id: str, start_date: str) -> pd.DataFrame:
        """
        抓取日K線（從 start_date 到今日）。
        回傳欄位：date, open, high, low, close, volume
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        return self.fetch_klines(stock_id, start_date, end_date)

    def fetch_klines(self, symbol: str, start: str = None, end: str = None, **kwargs) -> pd.DataFrame:
        """
        抓取歷史日K線。
        """
        start = start or kwargs.get("start_date")
        if not start:
            start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        if not end:
            end = datetime.now().strftime("%Y-%m-%d")
        if symbol in FUTURES_SYMBOLS:
            return self._fetch_futures_klines(symbol, start, end)
        try:
            df = self._dl.taiwan_stock_daily(
                stock_id=symbol, start_date=start, end_date=end
            )
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.rename(columns={"max": "high", "min": "low", "Trading_Volume": "volume"})
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            keep = [c for c in ["date", "open", "high", "low", "close", "volume"] if c in df.columns]
            return df[keep]
        except Exception as e:
            logger.error(f"fetch_klines({symbol}): {e}")
            return pd.DataFrame()

    def get_symbol_name(self, symbol: str) -> str:
        """回傳股票中文名稱，找不到時回傳代碼本身。"""
        self._refresh_stock_info()
        return _STOCK_NAME_CACHE.get(symbol, symbol)

    def get_stock_list(self, market_type: str = "all") -> pd.DataFrame:
        """
        取得股票清單。
        market_type: "all" | "listed" | "otc" | "futures"
        回傳欄位：stock_id, name, type
        """
        if market_type == "futures":
            return pd.DataFrame([
                {"stock_id": "TX",  "name": "台指期大台", "type": "futures"},
                {"stock_id": "MTX", "name": "台指期小台", "type": "futures"},
            ])
        try:
            df = self._dl.taiwan_stock_info()
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.rename(columns={"stock_name": "name"})
            if market_type == "listed":
                df = df[df["type"].str.contains("上市|TSE", na=False, case=False)]
            elif market_type == "otc":
                df = df[df["type"].str.contains("上櫃|OTC", na=False, case=False)]
            keep = [c for c in ["stock_id", "name", "type"] if c in df.columns]
            return df[keep].reset_index(drop=True)
        except Exception as e:
            logger.error(f"get_stock_list: {e}")
            return pd.DataFrame()

    def get_all_stock_ids_with_market(self) -> dict[str, str]:
        """
        回傳全部台股代碼 → 市場類型的映射。
        市場類型：'twse'（上市）| 'tpex'（上櫃）
        結果來自 FinMind taiwan_stock_info（單次 API 呼叫），
        並快取在模組層級變數中，後續呼叫直接返回快取。
        """
        self._refresh_stock_info()
        # _STOCK_TYPE_CACHE 可能只有部分資料，直接呼叫一次完整清單
        try:
            df = self._dl.taiwan_stock_info()
            if df is None or df.empty:
                return {}
            # 只保留 twse / tpex，排除 emerging（興櫃）
            df = df[df["type"].isin(["twse", "tpex"])]
            result: dict[str, str] = {}
            for _, row in df.iterrows():
                sid = str(row["stock_id"]).strip()
                mtype = str(row["type"]).strip()   # 'twse' | 'tpex'
                if sid:
                    result[sid] = mtype
            logger.info(f"get_all_stock_ids_with_market: {len(result)} stocks (TWSE+TPEX)")
            return result
        except Exception as e:
            logger.error(f"get_all_stock_ids_with_market: {e}")
            return {}

    def fetch_institutional_buy_sell(
        self, symbol: str, start: str, end: str
    ) -> pd.DataFrame:
        """
        三大法人買賣超。
        回傳欄位：date, name（機構名）, buy, sell
        """
        try:
            df = self._dl.taiwan_stock_institutional_investors(
                stock_id=symbol, start_date=start, end_date=end
            )
            if df is None or df.empty:
                return pd.DataFrame()
            df["date"] = pd.to_datetime(df["date"])
            for col in ["buy", "sell"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            return df
        except Exception as e:
            logger.error(f"fetch_institutional_buy_sell({symbol}): {e}")
            return pd.DataFrame()

    def fetch_margin_short(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """
        融資融券餘額。
        回傳欄位包含：date, MarginPurchaseTodayBalance, ShortSaleTodayBalance
        """
        try:
            df = self._dl.taiwan_stock_margin_purchase_short_sale(
                stock_id=symbol, start_date=start, end_date=end
            )
            if df is None or df.empty:
                return pd.DataFrame()
            df["date"] = pd.to_datetime(df["date"])
            return df
        except Exception as e:
            logger.error(f"fetch_margin_short({symbol}): {e}")
            return pd.DataFrame()

    def fetch_per_pbr(self, symbol: str) -> Optional[dict]:
        """
        本益比 / 股價淨值比（取最近一筆）。
        回傳：{"pe_ratio": float, "pb_ratio": float}
        """
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
            df = self._dl.taiwan_stock_per_pbr(
                stock_id=symbol, start_date=start, end_date=end
            )
            if df is None or df.empty:
                return None
            df = df.sort_values("date", ascending=False)
            row = df.iloc[0]
            return {
                "pe_ratio": float(row.get("PER") or 0),
                "pb_ratio": float(row.get("PBR") or 0),
            }
        except Exception as e:
            logger.error(f"fetch_per_pbr({symbol}): {e}")
            return None

    def fetch_month_revenue(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """
        月營收。
        回傳欄位：date, revenue
        """
        try:
            df = self._dl.taiwan_stock_month_revenue(
                stock_id=symbol, start_date=start, end_date=end
            )
            if df is None or df.empty:
                return pd.DataFrame()
            df["date"] = pd.to_datetime(df["date"])
            # 統一欄位名稱
            for raw, normalized in [("Revenue", "revenue"), ("value", "revenue")]:
                if raw in df.columns and "revenue" not in df.columns:
                    df = df.rename(columns={raw: "revenue"})
            return df
        except Exception as e:
            logger.error(f"fetch_month_revenue({symbol}): {e}")
            return pd.DataFrame()

    # ------------------------------------------------------------------ #
    #   內部輔助方法
    # ------------------------------------------------------------------ #

    def _refresh_stock_info(self):
        """初始化時抓取全股票清單，建立 name & market type 快取。"""
        global _CACHE_LOADED
        if _CACHE_LOADED:
            return
        try:
            df = self._dl.taiwan_stock_info()
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    sid = str(row.get("stock_id", ""))
                    name = str(row.get("stock_name", sid))
                    t = str(row.get("type", ""))
                    _STOCK_NAME_CACHE[sid] = name
                    _STOCK_TYPE_CACHE[sid] = (
                        "otc" if ("OTC" in t.upper() or "上櫃" in t) else "tse"
                    )
                _CACHE_LOADED = True
                logger.info(f"TWDataFetcher: Loaded {len(_STOCK_NAME_CACHE)} stock names.")
        except Exception as e:
            logger.warning(f"TWDataFetcher: Failed to load stock info: {e}")

    def _fetch_twse_quote(self, stock_id: str, market: str = "tse") -> Optional[dict]:
        """呼叫 TWSE MIS API 取得即時報價。"""
        ex_ch = f"{market}_{stock_id}.tw"
        url = (
            f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
            f"?ex_ch={ex_ch}&json=1&delay=0"
        )
        try:
            import requests
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("msgArray", [])
            if not items:
                return None
            item = items[0]
            # z = 最新成交價；若盤前/盤後無成交則用 y (昨收)
            price_str = item.get("z", "")
            close_str = item.get("y", "0")
            price = self._safe_float(price_str if price_str not in ("-", "") else close_str)
            yesterday_close = self._safe_float(close_str)

            name = item.get("n", stock_id)
            _STOCK_NAME_CACHE[stock_id] = name

            change = round(price - yesterday_close, 2)
            change_pct = round(change / yesterday_close * 100, 2) if yesterday_close else 0.0

            vol_raw = item.get("v", "0") or "0"
            volume = int(float(vol_raw.replace(",", "")) * 1000)  # 單位：張 → 股

            return {
                "price": price,
                "name": name,
                "open": self._safe_float(item.get("o")),
                "high": self._safe_float(item.get("h")),
                "low": self._safe_float(item.get("l")),
                "volume": volume,
                "change": change,
                "change_pct": change_pct,
                "yesterday_close": yesterday_close,
            }
        except Exception as e:
            logger.debug(f"_fetch_twse_quote({stock_id}, {market}): {e}")
            return None

    def fetch_realtime_batch(self, stock_ids: list[str]) -> dict[str, dict]:
        """
        批量抓取即時報價 (TWSE MIS API)。
        限制每次建議不超過 50 支以確保穩定。
        """
        # 分組處理，MIS API 對過長的 URL 可能會拒絕
        results: dict[str, dict] = {}
        batch_size = 50
        for i in range(0, len(stock_ids), batch_size):
            chunk = stock_ids[i:i + batch_size]
            ex_chs = []
            for sid in chunk:
                market = _STOCK_TYPE_CACHE.get(sid, "tse")
                ex_chs.append(f"{market}_{sid}.tw")
            
            ex_ch_param = "|".join(ex_chs)
            url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch_param}&json=1&delay=0"
            
            try:
                import requests
                resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                data = {}
                if resp.status_code == 200:
                    data = resp.json()
                for item in data.get("msgArray", []):
                            sid = item.get("c")
                            if not sid: continue
                            
                            price_str = item.get("z", "")
                            close_str = item.get("y", "0")
                            price = self._safe_float(price_str if price_str not in ("-", "") else close_str)
                            yesterday_close = self._safe_float(close_str)
                            
                            change = round(price - yesterday_close, 2)
                            change_pct = round(change / yesterday_close * 100, 2) if yesterday_close else 0.0
                            
                            vol_raw = item.get("v", "0") or "0"
                            volume = int(float(vol_raw.replace(",", "")) * 1000)
                            
                            results[sid] = {
                                "price": price,
                                "name": item.get("n", sid),
                                "open": self._safe_float(item.get("o")),
                                "high": self._safe_float(item.get("h")),
                                "low": self._safe_float(item.get("l")),
                                "volume": volume,
                                "change": change,
                                "change_pct": change_pct,
                                "yesterday_close": yesterday_close,
                            }
            except Exception as e:
                logger.error(f"fetch_realtime_batch chunk error: {e}")
                
        return results

    def _fetch_futures_quote(self, symbol: str) -> dict:
        """台指期大台 / 小台即時行情。"""
        symbol_map = {"TX": "TXFZH", "MTX": "MTXZH", "TXF": "TXFZH", "MXF": "MTXZH"}
        code = symbol_map.get(symbol, symbol)
        url = (
            f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
            f"?ex_ch=future_{code}.tw&json=1&delay=0"
        )
        try:
            import requests
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("msgArray", [])
            if not items:
                return {"price": 0.0, "name": symbol}
            item = items[0]
            price_str = item.get("z", "")
            price = self._safe_float(price_str if price_str not in ("-", "") else item.get("y", "0"))
            return {
                "price": price,
                "name": item.get("n", symbol),
                "open": self._safe_float(item.get("o")),
                "high": self._safe_float(item.get("h")),
                "low": self._safe_float(item.get("l")),
                "volume": 0,
                "change": 0.0,
                "change_pct": 0.0,
            }
        except Exception as e:
            logger.warning(f"_fetch_futures_quote({symbol}): {e}")
            return {"price": 0.0, "name": symbol}

    def _fetch_futures_klines(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """台指期歷史日K線（透過 FinMind）。"""
        contract_map = {"TX": "TX", "MTX": "MTX", "TXF": "TX", "MXF": "MTX"}
        code = contract_map.get(symbol, symbol)
        try:
            df = self._dl.taiwan_futures_daily(
                futures_id=code, start_date=start, end_date=end
            )
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.rename(columns={"max": "high", "min": "low"})
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            keep = [c for c in ["date", "open", "high", "low", "close", "volume"] if c in df.columns]
            return df[keep]
        except Exception as e:
            logger.error(f"_fetch_futures_klines({symbol}): {e}")
            return pd.DataFrame()

    @staticmethod
    def _safe_float(val) -> float:
        try:
            if val in (None, "", "-"):
                return 0.0
            return float(str(val).replace(",", ""))
        except (ValueError, TypeError):
            return 0.0
