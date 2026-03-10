from __future__ import annotations

from core.data.news_fetcher import NewsFetcher, NewsItem


class NewsService:
    """Wrapper around NewsFetcher to keep V2 plumbing consistent."""

    def __init__(self, fetcher: NewsFetcher | None = None):
        self.fetcher = fetcher or NewsFetcher()

    def get_latest_market_news(self, limit: int = 10) -> list[NewsItem]:
        return self.fetcher.fetch_latest_news(limit=limit)

    def get_stock_news(self, symbol: str, name: str, limit: int = 5) -> list[NewsItem]:
        return self.fetcher.fetch_stock_news(symbol, name, limit=limit)

