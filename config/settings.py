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
SIMULATION_UNIVERSE = [
    # 上市：權值股
    "2330", "2317", "2454", "2412", "2303",
    # 上櫃：熱門
    "5274", "6415", "8046", "5269", "6237",
]

# 向後相容（選股器預設清單 = 同上，不含 TX）
DEFAULT_WATCHLIST = SIMULATION_UNIVERSE

# === 回測專用股票池（更廣泛，涵蓋各產業龍頭，約 50 支）===
# 來源：台灣上市公司市值前 50 + 熱門上櫃 + 各產業代表股
BACKTEST_UNIVERSE = [
    # ─ 半導體 ─
    "2330",  # 台積電
    "2303",  # 聯電
    "2308",  # 台達電
    "2454",  # 聯發科
    "3711",  # 日月光投控
    "2379",  # 瑞昱
    "3034",  # 聯詠
    "6239",  # 力成
    "8046",  # 南電
    # ─ 電子/資訊 ─
    "2317",  # 鴻海
    "2382",  # 廣達
    "2357",  # 華碩
    "2353",  # 宏碁
    "2395",  # 研華
    "3008",  # 大立光
    "2327",  # 國巨
    "2409",  # 友達
    "3481",  # 奇美電
    "2408",  # 南亞科
    # ─ 電信/軟體 ─
    "2412",  # 中華電
    "4904",  # 遠傳
    "3045",  # 台灣大
    # ─ 金融 ─
    "2882",  # 國泰金
    "2886",  # 兆豐金
    "2884",  # 玉山金
    "2891",  # 中信金
    "2892",  # 第一金
    "2883",  # 開發金
    # ─ 傳產/工業 ─
    "1301",  # 台塑
    "1303",  # 南亞
    "1326",  # 台化
    "6505",  # 台塑化
    "2207",  # 和泰車
    "2105",  # 正新
    # ─ 生技/醫療 ─
    "4938",  # 和碩
    "6456",  # GIS KY
    "1476",  # 儒鴻
    # ─ 上櫃熱門 ─
    "5274",  # 信驊
    "6415",  # 矽力-KY
    "5269",  # 祥碩
    "6237",  # 驊訊
    "3533",  # 嘉澤
    "5347",  # 世界
    # ─ ETF（作為對比用）─
    "0050",  # 台灣 50
    "0056",  # 高股息
]

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
    # K 線型態策略
    {"id": "double_bottom",         "name": "雙底（看多）",   "type": "buy",  "condition": "偵測到雙底型態"},
    {"id": "double_top",            "name": "雙頂（看空）",   "type": "sell", "condition": "偵測到雙頂型態"},
    {"id": "head_shoulders_bottom", "name": "頭肩底（看多）", "type": "buy",  "condition": "偵測到頭肩底型態"},
    {"id": "head_shoulders_top",    "name": "頭肩頂（看空）", "type": "sell", "condition": "偵測到頭肩頂型態"},
    {"id": "triangle_bull",         "name": "上升三角收斂",   "type": "buy",  "condition": "上升三角型態"},
    {"id": "breakout_up",           "name": "向上突破",       "type": "buy",  "condition": "突破近 20 日高點"},
    {"id": "breakdown",             "name": "向下跌破",       "type": "sell", "condition": "跌破近 20 日低點"},
    {"id": "fib_support",           "name": "費波納契支撐",   "type": "buy",  "condition": "現價在 Fib 38.2%~61.8% 支撐位附近"},
]

# === Agent Model Settings ===
AGENT_MODELS = {
    "technical":  "gemini-2.0-flash",   # 原 lite 版不再提供
    "sentiment":  "gemini-2.5-flash", 
    "risk":       "gemini-2.0-flash",   # 原 lite 版不再提供
    "chief":      "gemini-2.5-flash", 
}

AGENT_TEMPERATURES = {
    "technical":  0.1,
    "sentiment":  0.3,
    "risk":       0.1,
    "chief":      0.1,
}
