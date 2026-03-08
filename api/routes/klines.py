"""K 線資料 API"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Query, Request

router = APIRouter()


@router.get("/{symbol}")
def get_klines(
    symbol: str,
    request: Request,
    days: int = Query(180, ge=30, le=365),
):
    fetcher = request.app.state.fetcher
    end = datetime.now()
    start = (end - timedelta(days=days)).strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    df = fetcher.fetch_klines(symbol, start, end_str)
    if df.empty:
        return {"symbol": symbol, "data": []}
    records = df.to_dict(orient="records")
    for r in records:
        for k, v in r.items():
            if hasattr(v, "item"):
                r[k] = v.item()
    return {"symbol": symbol, "data": records}
