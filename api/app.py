import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

"""
台股交易推手 — FastAPI 核心應用 (模組化路由版)
"""

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from config.settings import SIMULATION_UNIVERSE
from core.agents.orchestrator import TradingOrchestrator
from core.analysis.analysis_context_builder import AnalysisContextBuilder
from core.analysis.analysis_pipeline import AnalysisPipeline
from core.data.tw_data_fetcher import TWDataFetcher
from core.data_services.market_data_service import MarketDataService
from core.data_services.news_service import NewsService
from core.data_services.symbol_lookup_service import SymbolLookupService
from core.decision.decision_engine import DecisionEngine
from core.execution.simulator import TradeSimulator
from core.screening.candidate_screening_service import CandidateScreeningService
from core.strategy.screener import StockScreener

_GLOBAL_APP_STATE = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _GLOBAL_APP_STATE
    _GLOBAL_APP_STATE = app.state

    app.state.simulator = TradeSimulator()
    app.state.fetcher = TWDataFetcher()
    app.state.market_data_service = MarketDataService(app.state.fetcher)
    app.state.news_service = NewsService()
    app.state.symbol_lookup_service = SymbolLookupService(app.state.fetcher)
    app.state.analysis_context_builder = AnalysisContextBuilder(
        fetcher=app.state.fetcher,
        market_data_service=app.state.market_data_service,
        news_service=app.state.news_service,
        symbol_lookup_service=app.state.symbol_lookup_service,
    )
    app.state.decision_engine = DecisionEngine()
    app.state.analysis_pipeline = AnalysisPipeline(
        app.state.analysis_context_builder,
        decision_engine=app.state.decision_engine,
    )
    app.state.candidate_screening_service = CandidateScreeningService(app.state.fetcher)
    app.state.orchestrator = TradingOrchestrator(fetcher=app.state.fetcher)
    app.state.screener = StockScreener(data_fetcher=app.state.fetcher)
    app.state.watchlist = list(SIMULATION_UNIVERSE)

    from core.scheduler import continuous_market_scan_loop, init_scheduler, shutdown_scheduler

    init_scheduler()
    app.state.scan_loop_task = asyncio.create_task(continuous_market_scan_loop())
    logger.info("Continuous market scan loop task started.")

    yield

    logger.info("Shutting down API Lifespan...")
    scan_loop_task = getattr(app.state, "scan_loop_task", None)
    if scan_loop_task:
        scan_loop_task.cancel()
        try:
            await scan_loop_task
        except asyncio.CancelledError:
            logger.info("Continuous market scan loop stopped.")
    shutdown_scheduler()
    app.state.simulator.save_state()


app = FastAPI(
    title="台股交易推手 API",
    description="模組化架構 — 市場、模擬、AI 選股",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000", "http://localhost:8890"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import traceback


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"====== GLOBAL EXCEPTION ======\n{traceback.format_exc()}")
    return JSONResponse(status_code=500, content={"message": str(exc)})


from api.routes.analyze import router as analyze_router
from api.routes.analysis import router as analysis_router
from api.routes.backtest import router as backtest_router
from api.routes.klines import router as klines_router
from api.routes.market import router as market_router
from api.routes.portfolio import router as portfolio_router
from api.routes.screener import router as screener_router
from api.routes.settings import router as settings_router
from api.routes.simulation import router as sim_router
from api.routes.stock import router as stock_router
from api.routes.trading import router as trading_router
from api.routes.watchlist import router as watchlist_router

app.include_router(market_router, prefix="/api/market", tags=["Market"])
app.include_router(sim_router, prefix="/api/simulation", tags=["Simulation"])
app.include_router(stock_router, prefix="/api/stock", tags=["Stock"])
app.include_router(analyze_router, prefix="/api/analyze", tags=["Analyze"])
app.include_router(analysis_router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(trading_router, prefix="/api/trading", tags=["Trading"])
app.include_router(screener_router, prefix="/api/screener", tags=["Screener"])
app.include_router(backtest_router, prefix="/api/backtest", tags=["Backtest"])
app.include_router(klines_router, prefix="/api/klines", tags=["Klines"])
app.include_router(watchlist_router, prefix="/api/watchlist", tags=["Watchlist"])
app.include_router(portfolio_router, prefix="/api/portfolio", tags=["Portfolio"])
app.include_router(settings_router, prefix="/api/settings", tags=["Settings"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "台股交易推手 V2"}


_frontend_dist = ROOT / "frontend" / "dist"
if _frontend_dist.exists() and (_frontend_dist / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")

    @app.get("/vite.svg")
    def get_vite_svg():
        return FileResponse(str(_frontend_dist / "vite.svg"))

    @app.get("/")
    def serve_index():
        return FileResponse(str(_frontend_dist / "index.html"))

    @app.exception_handler(404)
    async def custom_404_handler(request, exc):
        if not request.url.path.startswith("/api/"):
            return FileResponse(str(_frontend_dist / "index.html"))
        return {"detail": "Not Found"}
