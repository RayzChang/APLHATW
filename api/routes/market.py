"""
市場數據 API — 大盤指數與開休市狀態
"""

import requests
import time
from fastapi import APIRouter, Request
from datetime import datetime, timedelta, timezone

router = APIRouter()

@router.get("/index")
def get_market_index(request: Request):
    """
    取得大盤指數 (加權指數 ^TWII)
    """
    from loguru import logger
    fetcher = request.app.state.fetcher
    
    # 方案 A: 嘗試使用常規 fetcher (支援 ^TWII 或 tx)
    try:
        # 特別針對大盤，直接嘗試 tse_t00.tw
        res = fetcher.fetch_realtime_quote("t00") 
        if res and res.get("price"):
            return {
                "index": res["price"],
                "change": round(res["price"] * (res["change_pct"]/100), 2) if res.get("change_pct") else 0.0,
                "change_pct": res.get("change_pct", 0.0),
                "timestamp": res.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            }
    except Exception as e:
        logger.debug(f"Fetcher A failed for index: {e}")

    # 方案 B: 直接備援 MIS API
    try:
        url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://mis.twse.com.tw/stock/index.jsp"
        }
        r = requests.get(url, headers=headers, timeout=5)
        if r.ok:
            data = r.json()
            msg_array = data.get("msgArray", [])
            if msg_array:
                row = msg_array[0]
                z_val = row.get("z", "-")
                prev_close = float(row.get("y", 0))
                # 沒成交(休市)就用昨收
                price = float(z_val) if z_val != "-" else prev_close
                change = price - prev_close
                change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0
                return {
                    "index": price,
                    "change": round(change, 2),
                    "change_pct": change_pct,
                    "timestamp": f"{row.get('d', '')} {row.get('t', '')}"
                }
    except Exception as e:
        logger.error(f"Fetcher B fallback failed for index: {e}")
        
    return {
        "index": 0.0,
        "change": 0.0,
        "change_pct": 0.0,
        "timestamp": "",
        "error": "無法取得大盤資料"
    }

@router.get("/status")
def get_market_status():
    """
    判斷台股當前是否為交易時間 (週一~五 09:00~13:30 台灣時間)
    """
    # 台灣時區 UTC+8
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)
    
    is_open = False
    message = "市場休市中"
    
    # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri
    if 0 <= now.weekday() <= 4:
        # 判斷時間範圍
        current_time = now.time()
        start_time = datetime.strptime("09:00", "%H:%M").time()
        end_time = datetime.strptime("13:30", "%H:%M").time()
        
        if start_time <= current_time <= end_time:
            is_open = True
            message = "市場開盤中"
            
    return {
        "is_open": is_open,
        "message": message
    }
