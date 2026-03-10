from loguru import logger

from core.analysis.analysis_context_builder import AnalysisContextBuilder
from core.analysis.analysis_pipeline import AnalysisPipeline
from core.data.tw_data_fetcher import TWDataFetcher
from core.data_services.market_data_service import MarketDataService
from core.data_services.news_service import NewsService
from core.data_services.symbol_lookup_service import SymbolLookupService


class TradingOrchestrator:
    """
    Phase 2 adapter.
    Keep the old orchestrator entrypoint, but delegate the real work to AnalysisPipeline.
    """

    def __init__(self, fetcher: TWDataFetcher | None = None):
        logger.info("Initializing TradingOrchestrator...")
        self.fetcher = fetcher if fetcher is not None else TWDataFetcher()
        self.context_builder = AnalysisContextBuilder(
            fetcher=self.fetcher,
            market_data_service=MarketDataService(self.fetcher),
            news_service=NewsService(),
            symbol_lookup_service=SymbolLookupService(self.fetcher),
        )
        self.pipeline = AnalysisPipeline(context_builder=self.context_builder)

    def analyze_symbol(self, query: str, portfolio: dict | None = None):
        return self.pipeline.analyze_symbol(query, portfolio=portfolio)

    def build_trade_signal(self, analysis_result, source: str = "AUTO_SCAN"):
        return self.pipeline.build_trade_signal(analysis_result, source=source)

    def run_full_analysis(self, stock_id: str) -> dict:
        try:
            return self.analyze_symbol(stock_id).to_legacy_payload()
        except Exception as e:
            logger.error(f"Orchestrator Error analyzing {stock_id}: {e}")
            return {"error": str(e)}
