"""
全市場列表 API — 每檔標的後附強力買入/強力賣出等建議
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Query

from core.data.tw_data_fetcher import TWDataFetcher
from core.analysis.indicators import add_all_indicators, calc_buy_sell_score
from datetime import datetime, timedelta

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=10)


def _score_to_signal(score: int) -> str:
    """評分轉建議：強力買入、買入、觀望、賣出、強力賣出"""
    if score >= 3:
        return "強力買入"
    if score >= 2:
        return "買入"
    if score >= -1:
        return "觀望"
    if score >= -2:
        return "賣出"
    return "強力賣出"


def _analyze_one(fetcher: TWDataFetcher, symbol: str, start: str, end_str: str) -> dict | None:
    """單一標的分析（供並行呼叫）"""
    try:
        sdf = fetcher.fetch_klines(str(symbol), start, end_str)
        if sdf.empty or len(sdf) < 30:
            return None
        sdf = add_all_indicators(sdf)
        row = sdf.iloc[-1]
        score = calc_buy_sell_score(row)
        prev = sdf.iloc[-2] if len(sdf) >= 2 else row
        change_pct = ((row["close"] - prev["close"]) / prev["close"] * 100) if prev["close"] else 0
        name = fetcher.get_symbol_name(str(symbol))
        return {
            "symbol": str(symbol),
            "name": name,
            "close": round(float(row["close"]), 2),
            "change_pct": round(change_pct, 2),
            "signal": _score_to_signal(score),
            "score": score,
        }
    except Exception:
        return None


@router.get("/list")
def get_market_list(
    market: str = Query("all", description="listed=上市 | otc=上櫃 | all=全部"),
    limit: int = Query(50, ge=10, le=200, description="最多回傳筆數"),
):
    """
    取得台股市場列表，每檔附建議。使用並行請求加速（約 10–30 秒）。
    """
    fetcher = TWDataFetcher()
    df = fetcher.get_stock_list(market)
    if df.empty:
        return {"count": 0, "results": []}
    
    stock_id_col = "stock_id" if "stock_id" in df.columns else "symbol"
    symbols = df[stock_id_col].dropna().unique().tolist()[:limit]
    
    end = datetime.now()
    start = (end - timedelta(days=60)).strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    
    results = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_analyze_one, fetcher, str(s), start, end_str): s for s in symbols}
        for future in as_completed(futures):
            r = future.result()
            if r:
                results.append(r)
    
    order = {"強力買入": 0, "買入": 1, "觀望": 2, "賣出": 3, "強力賣出": 4}
    results.sort(key=lambda x: (order.get(x["signal"], 2), -x["score"]))
    
    return {"count": len(results), "results": results}


@router.get("/list/simple")
def get_market_list_simple(
    market: str = Query("all", description="listed | otc | all"),
):
    """僅取得股票清單（代碼、名稱），不含分析。用於下拉選單等。"""
    fetcher = TWDataFetcher()
    df = fetcher.get_stock_list(market)
    if df.empty:
        return {"count": 0, "results": []}
    stock_id_col = "stock_id" if "stock_id" in df.columns else "symbol"
    name_col = "stock_name" if "stock_name" in df.columns else "name"
    results = [{"symbol": str(r[stock_id_col]), "name": str(r.get(name_col, r[stock_id_col]))} for _, r in df.iterrows()]
    return {"count": len(results), "results": results}
