from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from core.analysis.stock_analysis import StockAnalysisResult, analyze_stock
from core.data.news_fetcher import NewsItem
from core.data.tw_data_fetcher import TWDataFetcher
from core.data_services.market_data_service import MarketDataService
from core.data_services.news_service import NewsService
from core.data_services.symbol_lookup_service import SymbolLookupService
from core.risk.sl_tp_calculator import SLTPCalculator


@dataclass
class AnalysisContext:
    query: str
    symbol: str
    name: str
    timestamp: datetime
    market_context: dict[str, Any]
    quote: dict[str, Any]
    stock_analysis: StockAnalysisResult | None
    kline_df: pd.DataFrame
    news_items: list[NewsItem]
    risk_metrics: dict[str, Any]
    portfolio: dict[str, Any]


class AnalysisContextBuilder:
    """Collect raw inputs required by the unified analysis pipeline."""

    def __init__(
        self,
        fetcher: TWDataFetcher,
        market_data_service: MarketDataService | None = None,
        news_service: NewsService | None = None,
        symbol_lookup_service: SymbolLookupService | None = None,
        risk_calc: SLTPCalculator | None = None,
    ):
        self.fetcher = fetcher
        self.market_data_service = market_data_service or MarketDataService(fetcher)
        self.news_service = news_service or NewsService()
        self.symbol_lookup_service = symbol_lookup_service or SymbolLookupService(fetcher)
        self.risk_calc = risk_calc or SLTPCalculator()

    def build(self, query: str, portfolio: dict[str, Any] | None = None) -> AnalysisContext:
        resolved = self.symbol_lookup_service.resolve(query)
        symbol = resolved.symbol
        name = resolved.name
        timestamp = datetime.now()

        quote = self.market_data_service.get_quote(symbol) or {}
        stock_analysis = analyze_stock(symbol, fetcher=self.fetcher, days=90)

        if stock_analysis:
            name = stock_analysis.name or name
            if not quote:
                quote = {
                    "price": stock_analysis.close,
                    "name": stock_analysis.name,
                    "change_pct": stock_analysis.change_pct,
                    "open": stock_analysis.close,
                    "high": stock_analysis.close,
                    "low": stock_analysis.close,
                    "volume": 0,
                    "change": 0.0,
                    "is_realtime": False,
                }

        end_date = timestamp.strftime("%Y-%m-%d")
        start_date = (timestamp - timedelta(days=120)).strftime("%Y-%m-%d")
        kline_df = self.fetcher.fetch_klines(symbol, start_date, end_date)
        news_items = self.news_service.get_stock_news(symbol, name, limit=5)
        market_context = self.market_data_service.get_market_snapshot()
        risk_metrics = self._build_risk_metrics(quote, kline_df)

        return AnalysisContext(
            query=query,
            symbol=symbol,
            name=name,
            timestamp=timestamp,
            market_context=market_context,
            quote=quote,
            stock_analysis=stock_analysis,
            kline_df=kline_df,
            news_items=news_items,
            risk_metrics=risk_metrics,
            portfolio=portfolio or {},
        )

    def _build_risk_metrics(self, quote: dict[str, Any], kline_df: pd.DataFrame) -> dict[str, Any]:
        price = float(quote.get("price", 0.0) or 0.0)
        default_stop = round(price * 0.95, 2) if price else 0.0
        default_take_profit = round(price * 1.1, 2) if price else 0.0

        if kline_df is None or kline_df.empty or price <= 0:
            return {
                "atr": 0.0,
                "swing_low": 0.0,
                "swing_high": 0.0,
                "stop_loss_price": default_stop,
                "take_profit_price": default_take_profit,
                "breakeven_price": round(price, 2),
            }

        atr = float(self.risk_calc.calculate_atr(kline_df) or 0.0)
        swing_low, swing_high = self.risk_calc.get_swing_points(kline_df, lookback=20)
        stop_loss = self.risk_calc.calculate_atr_stop_loss(price, atr, multiplier=2.0) if atr else default_stop
        take_profit = self.risk_calc.calculate_fibonacci_tp(price, swing_low, swing_high, atr, level=0.618) if atr else default_take_profit
        breakeven = self.risk_calc.calculate_breakeven_stop(price)

        if take_profit <= price:
            take_profit = default_take_profit
        if stop_loss >= price:
            stop_loss = default_stop

        return {
            "atr": round(float(atr), 2),
            "swing_low": round(float(swing_low or 0.0), 2),
            "swing_high": round(float(swing_high or 0.0), 2),
            "stop_loss_price": round(float(stop_loss or 0.0), 2),
            "take_profit_price": round(float(take_profit or 0.0), 2),
            "breakeven_price": round(float(breakeven or price), 2),
        }
