from __future__ import annotations

from dataclasses import dataclass

from core.data.tw_data_fetcher import TWDataFetcher


@dataclass
class SymbolMatch:
    symbol: str
    name: str
    score: int = 0


class SymbolLookupService:
    """Resolve a stock symbol by id or company name (best-effort)."""

    def __init__(self, fetcher: TWDataFetcher):
        self.fetcher = fetcher

    def resolve(self, query: str) -> SymbolMatch:
        q = (query or "").strip()
        if not q:
            raise ValueError("請輸入股票代號或公司名稱")

        stock_list = self.fetcher.get_stock_list("all")
        if stock_list is None or stock_list.empty:
            raise ValueError("無法取得股票清單")

        q_upper = q.upper()

        exact_symbol = stock_list[stock_list["stock_id"].astype(str).str.upper() == q_upper]
        if not exact_symbol.empty:
            row = exact_symbol.iloc[0]
            return SymbolMatch(symbol=str(row["stock_id"]), name=str(row["name"]), score=100)

        exact_name = stock_list[stock_list["name"].astype(str).str.upper() == q_upper]
        if not exact_name.empty:
            row = exact_name.iloc[0]
            return SymbolMatch(symbol=str(row["stock_id"]), name=str(row["name"]), score=95)

        contains = stock_list[
            stock_list["name"].astype(str).str.contains(q, case=False, na=False)
            | stock_list["stock_id"].astype(str).str.contains(q_upper, case=False, na=False)
        ]
        if not contains.empty:
            row = contains.iloc[0]
            return SymbolMatch(symbol=str(row["stock_id"]), name=str(row["name"]), score=80)

        raise ValueError(f"找不到與 {query} 對應的台股標的")

