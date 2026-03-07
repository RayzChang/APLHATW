"""台股交易推手 — FastAPI 應用"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

from config.settings import (
    API_PORT,
    DASHBOARD_USERNAME,
    DASHBOARD_PASSWORD,
    DEFAULT_WATCHLIST,
    SCREENER_STRATEGIES,
)
from api.routes import screener, backtest, simulation, klines, analyze, watchlist, market

app = FastAPI(
    title="台股交易推手 API",
    description="上市·上櫃·台指期 — 選股、回測、模擬交易",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic()


def verify_credentials() -> str:
    # 根據使用者要求，直接寫死登入帳號，完全不檢查任何 Authorization header
    return DASHBOARD_USERNAME


app.include_router(screener.router, prefix="/api/screener", tags=["screener"], dependencies=[Depends(verify_credentials)])
app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"], dependencies=[Depends(verify_credentials)])
app.include_router(simulation.router, prefix="/api/simulation", tags=["simulation"], dependencies=[Depends(verify_credentials)])
app.include_router(klines.router, prefix="/api/klines", tags=["klines"], dependencies=[Depends(verify_credentials)])
app.include_router(analyze.router, prefix="/api/analyze", tags=["analyze"], dependencies=[Depends(verify_credentials)])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"], dependencies=[Depends(verify_credentials)])
app.include_router(market.router, prefix="/api/market", tags=["market"], dependencies=[Depends(verify_credentials)])

from api.routes import portfolio
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"], dependencies=[Depends(verify_credentials)])


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    from core.scheduler import init_scheduler, shutdown_scheduler
    from core.db.database import engine, Base, SessionLocal
    from core.db.models import Portfolio
    from config.settings import SIMULATION_INITIAL_BALANCE
    
    # 建立資料表
    Base.metadata.create_all(bind=engine)
    
    # 初始化資金簿
    db = SessionLocal()
    try:
        portfolio = db.query(Portfolio).first()
        if not portfolio:
            portfolio = Portfolio(
                total_assets=SIMULATION_INITIAL_BALANCE,
                available_cash=SIMULATION_INITIAL_BALANCE
            )
            db.add(portfolio)
            db.commit()
    finally:
        db.close()

    init_scheduler()
    yield
    shutdown_scheduler()

app.router.lifespan_context = lifespan

@app.get("/api/health")
def health():
    return {"status": "ok", "app": "台股交易推手"}


@app.get("/api/auth/check", dependencies=[Depends(verify_credentials)])
def auth_check():
    """供前端「登入」按鈕驗證帳密"""
    return {"ok": True}

from pydantic import BaseModel
class SettingsRequest(BaseModel):
    gemini_key: str | None = None

@app.post("/api/settings", dependencies=[Depends(verify_credentials)])
def update_backend_settings(req: SettingsRequest):
    import config.settings
    import os
    if req.gemini_key:
        config.settings.GEMINI_API_KEY = req.gemini_key
        os.environ["GEMINI_API_KEY"] = req.gemini_key
    return {"ok": True}


@app.get("/api/index")
def get_index():
    """加權指數（發行量加權股價指數）供 header 顯示"""
    import requests
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/^TWII?interval=1m&range=1d"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5)
        if r.ok:
            data = r.json()
            meta = data['chart']['result'][0]['meta']
            current = float(meta['regularMarketPrice'])
            prev_close = float(meta['chartPreviousClose'])
            change_pct = round(((current - prev_close) / prev_close) * 100, 2)
            return {"index": round(current, 2), "change": change_pct, "label": "加權指數"}
    except Exception as e:
        print(f"Yahoo API failed: {e}")
        
    return {"index": None, "change": None, "hint": "Yahoo Finance API 無回應"}


@app.get("/api/strategies")
def get_strategies():
    from config.settings import SIMULATION_UNIVERSE
    return {"strategies": SCREENER_STRATEGIES, "simulation_universe": SIMULATION_UNIVERSE}


# 靜態前端 (React Vite Build)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_frontend_dist = ROOT / "frontend" / "dist"
if _frontend_dist.exists() and (_frontend_dist / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")
    
    @app.get("/vite.svg")
    def get_vite_svg():
        return FileResponse(str(_frontend_dist / "vite.svg"))

    @app.get("/")
    def index():
        return FileResponse(str(_frontend_dist / "index.html"))
    
    # Fallback default route to React for client-side routing
    @app.exception_handler(404)
    async def custom_404_handler(request, exc):
        if not request.url.path.startswith("/api/"):
            return FileResponse(str(_frontend_dist / "index.html"))
        return {"detail": "Not Found"}
