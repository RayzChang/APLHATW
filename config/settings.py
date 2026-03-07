"""
台股交易推手 — 全局配置

支援：上市、上櫃、台指期
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# === FinMind API ===
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")

# === AI API ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# === Notifications ===
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN", "")

# === 模擬交易 ===
SIMULATION_INITIAL_BALANCE = float(os.getenv("SIMULATION_INITIAL_BALANCE", "1000000"))

# === Web Dashboard ===
DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "changeme")
API_HOST = "0.0.0.0"
API_PORT = int(os.getenv("API_PORT", "8890"))

# === Database ===
DB_PATH = BASE_DIR / "data" / "tw_trading.db"
KLINE_DATA_DIR = BASE_DIR / "data" / "klines"

# === 市場類型 ===
MARKET_TYPES = {
    "listed": "上市",   # 證交所
    "otc": "上櫃",     # 櫃買中心
    "futures": "期貨",  # 台指期
}

# === AI 模擬交易可交易標的（上市 + 上櫃）===
# 預設選股清單不含台指期，避免日頻資料與當日漲跌方向混淆（台指期可手動加入）
SIMULATION_UNIVERSE = [
    # 上市：權值股
    "2330", "2317", "2454", "2412", "2303",
    # 上櫃：熱門
    "5274", "6415", "8046", "5269", "6237",
]

# 向後相容（選股器預設清單 = 同上，不含 TX）
DEFAULT_WATCHLIST = SIMULATION_UNIVERSE

# === 台指期商品代碼 ===
FUTURES_SYMBOLS = ["TX", "MTX", "TXF", "MXF"]  # 大台、小台、近月代碼

# === 技術指標選股策略 ===
SCREENER_STRATEGIES = [
    {"id": "list_all", "name": "全部列出", "type": "filter", "condition": "顯示所有標的與建議"},
    {"id": "buy_score", "name": "適合買進", "type": "buy", "condition": "綜合評分 ≥ 1"},
    {"id": "sell_score", "name": "考慮賣出", "type": "sell", "condition": "綜合評分 ≤ -1"},
    {"id": "volume_surge", "name": "量能異動", "type": "filter", "condition": "量比 ≥ 1.5x"},
    {"id": "oversold", "name": "超跌反彈", "type": "buy", "condition": "RSI < 30 或布林破下軌"},
    {"id": "kd_golden", "name": "KD 黃金交叉", "type": "buy", "condition": "K 線上穿 D 線"},
    {"id": "kd_death", "name": "KD 死亡交叉", "type": "sell", "condition": "K 線下穿 D 線"},
    {"id": "rsi_oversold", "name": "RSI < 30", "type": "buy", "condition": "超賣區"},
    {"id": "rsi_overbought", "name": "RSI > 70", "type": "sell", "condition": "超買區"},
    {"id": "macd_bull", "name": "MACD 翻多", "type": "buy", "condition": "柱狀由負轉正"},
    {"id": "macd_bear", "name": "MACD 翻空", "type": "sell", "condition": "柱狀由正轉負"},
    {"id": "ma20_above", "name": "站上 MA20", "type": "buy", "condition": "價格在 20 日均線上方"},
    {"id": "ma20_below", "name": "跌破 MA20", "type": "sell", "condition": "價格在 20 日均線下方"},
    {"id": "bb_upper", "name": "布林突破上軌", "type": "buy", "condition": "%B > 1.0"},
    {"id": "bb_lower", "name": "布林跌破下軌", "type": "buy", "condition": "%B < 0.0"},
]
