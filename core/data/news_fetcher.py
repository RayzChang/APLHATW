"""
台股新聞抓取器 (NewsFetcher)

資料來源：Google News RSS、Yahoo 財經 RSS（免費，無需 API Key）
情緒分析：繁體中文關鍵字規則法（正面 / 負面 / 中立）
"""

import re
import time as time_mod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus

import feedparser
from loguru import logger


@dataclass
class NewsItem:
    title: str
    summary: str
    published: datetime
    url: str = ""
    sentiment: str = "neutral"   # "positive" | "negative" | "neutral"


# RSS 新聞來源（台股相關）
_RSS_FEEDS: list[str] = [
    "https://news.google.com/rss/search?q=台股+大盤&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=台灣股市+加權指數&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=台股+外資+投信&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
]

_POSITIVE_KEYWORDS = [
    "上漲", "漲停", "創高", "突破", "買進", "多頭", "利多",
    "獲利", "營收成長", "優於預期", "法說會正面", "回升", "反彈",
    "增持", "買超", "外資買", "投信買", "強勢", "創新高",
    "業績亮眼", "上修", "超出預期", "正向", "看好",
]

_NEGATIVE_KEYWORDS = [
    "下跌", "跌停", "創低", "破底", "賣出", "空頭", "利空",
    "虧損", "營收衰退", "低於預期", "下修", "回落", "修正",
    "減持", "賣超", "外資賣", "投信賣", "疲弱", "警示",
    "跌破", "縮手", "悲觀", "看壞", "衰退", "虧損擴大",
]


def _score_sentiment(text: str) -> str:
    pos = sum(1 for kw in _POSITIVE_KEYWORDS if kw in text)
    neg = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in text)
    if pos > neg:
        return "positive"
    elif neg > pos:
        return "negative"
    return "neutral"


def _parse_date(entry) -> datetime:
    """解析 feedparser entry 時間欄位，找不到時回傳當下時間。"""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime.fromtimestamp(time_mod.mktime(t))
            except Exception:
                pass
    return datetime.now()


def _strip_html(text: str) -> str:
    """移除 HTML tags 並清理多餘空白。"""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class NewsFetcher:
    """
    台股新聞抓取器。

    使用方式：
        fetcher = NewsFetcher()
        news = fetcher.fetch_latest_news(limit=10)
        for item in news:
            print(item.title, item.sentiment)
    """

    def __init__(self, extra_feeds: Optional[list[str]] = None):
        self._feeds = _RSS_FEEDS + (extra_feeds or [])

    def fetch_latest_news(self, limit: int = 10) -> list[NewsItem]:
        """
        抓取最新台股大盤相關新聞。

        Args:
            limit: 最多回傳幾則（依發布時間降冪）

        Returns:
            list[NewsItem]
        """
        items: list[NewsItem] = []
        seen: set[str] = set()

        for feed_url in self._feeds:
            if len(items) >= limit * 3:
                break
            try:
                parsed = feedparser.parse(feed_url)
                for entry in parsed.entries:
                    title = getattr(entry, "title", "").strip()
                    if not title or title in seen:
                        continue
                    seen.add(title)

                    summary = _strip_html(getattr(entry, "summary", title))
                    url = getattr(entry, "link", "")
                    published = _parse_date(entry)
                    sentiment = _score_sentiment(title + " " + summary)

                    items.append(NewsItem(
                        title=title,
                        summary=summary,
                        published=published,
                        url=url,
                        sentiment=sentiment,
                    ))
            except Exception as e:
                logger.warning(f"NewsFetcher: Failed to fetch {feed_url}: {e}")

        items.sort(key=lambda x: x.published, reverse=True)
        return items[:limit]

    def fetch_stock_news(
        self, symbol: str, name: str, limit: int = 5
    ) -> list[NewsItem]:
        """
        抓取特定股票的相關新聞。

        Args:
            symbol: 股票代碼，如 "2330"
            name:   股票名稱，如 "台積電"
            limit:  最多幾則

        Returns:
            list[NewsItem]
        """
        query = f"{name} {symbol} 台股"
        feed_url = (
            f"https://news.google.com/rss/search"
            f"?q={quote_plus(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        )
        items: list[NewsItem] = []
        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:limit * 2]:
                title = getattr(entry, "title", "").strip()
                if not title:
                    continue
                summary = _strip_html(getattr(entry, "summary", title))
                url = getattr(entry, "link", "")
                published = _parse_date(entry)
                sentiment = _score_sentiment(title + " " + summary)
                items.append(NewsItem(
                    title=title,
                    summary=summary,
                    published=published,
                    url=url,
                    sentiment=sentiment,
                ))
        except Exception as e:
            logger.warning(f"NewsFetcher.fetch_stock_news({symbol}): {e}")

        items.sort(key=lambda x: x.published, reverse=True)
        return items[:limit]
