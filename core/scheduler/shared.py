from __future__ import annotations

from core.analysis.analysis_context_builder import AnalysisContextBuilder
from core.analysis.analysis_pipeline import AnalysisPipeline
from core.data.news_fetcher import NewsFetcher
from core.data.tw_data_fetcher import TWDataFetcher
from core.data_services.market_data_service import MarketDataService
from core.data_services.news_service import NewsService
from core.data_services.symbol_lookup_service import SymbolLookupService
from core.decision.decision_engine import DecisionEngine
from core.screening.candidate_screening_service import CandidateScreeningService


def get_runtime_services():
    try:
        from api.app import _GLOBAL_APP_STATE

        fetcher = _GLOBAL_APP_STATE.fetcher
        simulator = _GLOBAL_APP_STATE.simulator
        analysis_pipeline = getattr(_GLOBAL_APP_STATE, "analysis_pipeline", None)
        screening_service = getattr(_GLOBAL_APP_STATE, "candidate_screening_service", None)
    except Exception:
        fetcher = TWDataFetcher()
        from core.execution.simulator import TradeSimulator

        simulator = TradeSimulator()
        analysis_pipeline = None
        screening_service = None

    if screening_service is None:
        screening_service = CandidateScreeningService(fetcher)

    if analysis_pipeline is None:
        analysis_pipeline = AnalysisPipeline(
            AnalysisContextBuilder(
                fetcher=fetcher,
                market_data_service=MarketDataService(fetcher),
                news_service=NewsService(),
                symbol_lookup_service=SymbolLookupService(fetcher),
            ),
            decision_engine=DecisionEngine(),
        )

    return fetcher, simulator, analysis_pipeline, screening_service


def job_fetch_news():
    from loguru import logger

    logger.info("Scheduler: Fetching latest news...")
    try:
        fetcher = NewsFetcher()
        news_items = fetcher.fetch_latest_news(limit=10)
        for item in news_items:
            logger.debug(f"News [{item.sentiment}]: {item.title}")
    except Exception as e:
        logger.error(f"Scheduler job_fetch_news failed: {e}")

