"""
市場數據 API — 大盤指數與開休市狀態

快取策略：
  盤中（週一~五 09:00~13:30）→ 10 秒快取（TWSE MIS 即時）
  休市 / 盤後              → 3600 秒快取（1 小時，資料不變）
  週末                     → 86400 秒快取（24 小時）
"""

import requests
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Request
from datetime import datetime, timedelta, timezone

_executor = ThreadPoolExecutor(max_workers=4)

router = APIRouter()

# ── 簡易記憶體快取 ────────────────────────────────────────────────
_index_cache: dict = {"data": None, "expires_at": 0.0}


def _is_market_open_now() -> bool:
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)
    if now.weekday() > 4:
        return False
    t = now.time()
    return datetime.strptime("09:00", "%H:%M").time() <= t <= datetime.strptime("13:30", "%H:%M").time()


def _cache_ttl() -> int:
    """依市場狀態回傳快取秒數"""
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)
    if now.weekday() > 4:
        return 86400   # 週末：1 天
    if _is_market_open_now():
        return 10      # 盤中：10 秒
    return 3600        # 盤後：1 小時


@router.get("/index")
async def get_market_index(request: Request):
    """
    取得大盤加權指數。
    優先走 TWSE MIS 即時 API；休市時走 TWSE 昨收價；
    均失敗才呼叫 FinMind 歷史資料（並加快取，避免每 5 秒打一次）。
    """
    from loguru import logger

    # ── 命中快取直接回傳 ───────────────────────────────────────────
    if _index_cache["data"] and time.time() < _index_cache["expires_at"]:
        return {**_index_cache["data"], "cached": True}

    loop = asyncio.get_event_loop()
    
    def _fetch_blocking():
        result = None

        # ── 方案 A：TWSE MIS 直接取（盤中即時 / 盤後昨收）───────────
        try:
            # 修正 URL：直接存取 msgArray
            url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw&json=1&delay=0"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://mis.twse.com.tw/",
            }
            r = requests.get(url, headers=headers, timeout=5)
            if r.ok:
                data = r.json()
                row_list = data.get("msgArray", [])
                if row_list:
                    row = row_list[0]
                    # z: 當前成交價, y: 昨收
                    z_val = row.get("z", "-")
                    y_val = row.get("y", "0")
                    prev_close = float(y_val or 0)
                    price = float(z_val) if z_val not in ("-", "", None) else prev_close
                    
                    if price > 0:
                        change = round(price - prev_close, 2)
                        change_pct = round(change / prev_close * 100, 2) if prev_close else 0.0
                        result = {
                            "index": price,
                            "change": change,
                            "change_pct": change_pct,
                            "timestamp": f"{row.get('d', '')} {row.get('t', '')}".strip(),
                            "source": "twse",
                        }
        except Exception as e:
            logger.debug(f"market/index TWSE failed: {e}")

        # ── 方案 B：歷史加權指數 fallback（盤後/休市用）──────────────
        if not result:
            try:
                fetcher = request.app.state.fetcher
                end = datetime.now().strftime("%Y-%m-%d")
                start = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
                df = fetcher.fetch_klines("TAIEX", start, end)
                if df is not None and not df.empty:
                    latest = df.iloc[-1]
                    prev = df.iloc[-2] if len(df) >= 2 else latest
                    price = float(latest["close"])
                    prev_close = float(prev["close"])
                    change = round(price - prev_close, 2)
                    change_pct = round(change / prev_close * 100, 2)
                    result = {
                        "index": price,
                        "change": change,
                        "change_pct": change_pct,
                        "timestamp": str(latest["date"]),
                        "source": "history_fallback",
                    }
            except Exception as e:
                logger.error(f"market/index history fallback failed: {e}")

        if not result:
            result = {
                "index": None,
                "change": None,
                "change_pct": None,
                "timestamp": "",
                "source": "unavailable",
            }
        return result

    result = await loop.run_in_executor(_executor, _fetch_blocking)

    # ── 寫入快取 (只針對成功取得數值的結果) ──────────────────────
    if result.get("index"):
        ttl = _cache_ttl()
        _index_cache["data"] = result
        _index_cache["expires_at"] = time.time() + ttl

    return result


@router.get("/status")
async def get_market_status():
    """
    判斷台股當前是否為交易時間 (週一~五 09:00~13:30 台灣時間)
    """
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)

    is_open = False
    message = "市場休市中"

    if 0 <= now.weekday() <= 4:
        current_time = now.time()
        start_time = datetime.strptime("09:00", "%H:%M").time()
        end_time   = datetime.strptime("13:30", "%H:%M").time()

        if start_time <= current_time <= end_time:
            is_open = True
            message = "市場開盤中"

    return {"is_open": is_open, "message": message}
