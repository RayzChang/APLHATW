"""
台股交易推手 — 主程式入口

啟動 FastAPI 後端，提供選股、回測、模擬交易 API
"""

import uvicorn
from config.settings import API_HOST, API_PORT

if __name__ == "__main__":
    uvicorn.run(
        "api.app:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
    )
