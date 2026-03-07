"""
台股交易推手 — FastAPI 核心應用 (模組化路由版)
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# 核心組件導入
from core.data.tw_data_fetcher import TWDataFetcher
from core.agents.orchestrator import TradingOrchestrator
from core.execution.simulator import TradeSimulator
from core.strategy.screener import StockScreener
from core.scheduler import init_scheduler, shutdown_scheduler

# 初始化單一全域實例
fetcher = TWDataFetcher()
orchestrator = TradingOrchestrator()
simulator = TradeSimulator()
screener = StockScreener(data_fetcher=fetcher)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 將實例掛載到 app.state，讓路由可以存取
    app.state.fetcher = fetcher
    app.state.orchestrator = orchestrator
    app.state.simulator = simulator
    app.state.screener = screener
    
    # 啟動時作業
    logger.info("Initializing API Lifespan...")
    simulator.load_state()  # 載入模擬交易狀態
    init_scheduler()        # 啟動排程任務
    
    yield
    
    # 關閉時作業
    logger.info("Shutting down API Lifespan...")
    simulator.save_state()  # 確保狀態已儲存
    shutdown_scheduler()

app = FastAPI(
    title="台股交易推手 API",
    description="模組化架構 — 市場、模擬、AI 選股",
    version="2.0.0",
    lifespan=lifespan
)

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊路由
from api.routes.market import router as market_router
from api.routes.simulation import router as sim_router
from api.routes.stock import router as stock_router

app.include_router(market_router, prefix="/api/market", tags=["Market"])
app.include_router(sim_router, prefix="/api/simulation", tags=["Simulation"])
app.include_router(stock_router, prefix="/api/stock", tags=["Stock"])

# 健康檢查
@app.get("/api/health")
def health():
    return {"status": "ok", "app": "台股交易推手 V2"}

# --- 舊有功能的導向或保留 (如 Settings/Auth) ---
# 這裡根據需求，若前端仍需要舊有的 API 路徑，可以繼續導向，
# 或是直接更新前端為新路徑。

# 靜態前端處理
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_frontend_dist = ROOT / "frontend" / "dist"
if _frontend_dist.exists() and (_frontend_dist / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")
    
    @app.get("/vite.svg")
    def get_vite_svg():
        return FileResponse(str(_frontend_dist / "vite.svg"))

    @app.get("/")
    def serve_index():
        return FileResponse(str(_frontend_dist / "index.html"))
    
    # Fallback default route to React for client-side routing
    @app.exception_handler(404)
    async def custom_404_handler(request, exc):
        if not request.url.path.startswith("/api/"):
            return FileResponse(str(_frontend_dist / "index.html"))
        return {"detail": "Not Found"}
