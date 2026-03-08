"""
市場數據 API — 大盤指數與開休市狀態

快取策略：
  盤中（週一~五 09:00~13:30）→ 10 秒快取（TWSE MIS 即時）
  休市 / 盤後              → 3600 秒快取（1 小時，資料不變）
  週末                     → 86400 秒快取（24 小時）
"""

import requests
import time
from fastapi import APIRouter, Request
from datetime import datetime, timedelta, timezone

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
def get_market_index(request: Request):
    """
    取得大盤加權指數。
    優先走 TWSE MIS 即時 API；休市時走 TWSE 昨收價；
    均失敗才呼叫 FinMind（並加快取，避免每 5 秒打一次）。
    """
    from loguru import logger

    # ── 命中快取直接回傳 ───────────────────────────────────────────
    if _index_cache["data"] and time.time() < _index_cache["expires_at"]:
        return {**_index_cache["data"], "cached": True}

    fetcher = request.app.state.fetcher
    result = None

    # ── 方案 A：TWSE MIS 直接取（盤中即時 / 盤後昨收）───────────
    try:
        url = (
            "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
            "?ex_ch=tse_t00.tw&json=1&delay=0"
        )
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://mis.twse.com.tw/",
        }
        r = requests.get(url, headers=headers, timeout=5)
        if r.ok:
            row_list = r.json().get("msgArray", [])
            if row_list:
                row = row_list[0]
                z_val = row.get("z", "-")
                prev_close = float(row.get("y", 0) or 0)
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

    # ── 方案 B：FinMind klines fallback（只在 TWSE 完全失敗時走）──
    if not result:
        try:
            quote = fetcher.fetch_realtime_quote("t00")
            if quote and quote.get("price"):
                result = {
                    "index": quote["price"],
                    "change": quote.get("change", 0.0),
                    "change_pct": quote.get("change_pct", 0.0),
                    "timestamp": quote.get("note", ""),
                    "source": "finmind_fallback",
                }
        except Exception as e:
            logger.error(f"market/index FinMind fallback failed: {e}")

    if not result:
        result = {
            "index": 0.0,
            "change": 0.0,
            "change_pct": 0.0,
            "timestamp": "",
            "source": "error",
        }

    # ── 寫入快取 ──────────────────────────────────────────────────
    ttl = _cache_ttl()
    _index_cache["data"] = result
    _index_cache["expires_at"] = time.time() + ttl

    return result


@router.get("/status")
def get_market_status():
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
