"""
歷史 K 線匯入腳本

將指定標的的歷史 K 線從 FinMind 下載並儲存至本地（Parquet/CSV），
供後續分析、回測使用，減少 API 呼叫。
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from loguru import logger

from config.settings import SIMULATION_UNIVERSE, KLINE_DATA_DIR
from core.data.tw_data_fetcher import TWDataFetcher


def import_klines(
    symbols: list[str] | None = None,
    days: int = 365,
    output_dir: Path | None = None,
) -> dict:
    """
    匯入歷史 K 線至本地
    
    Args:
        symbols: 標的列表，預設為 SIMULATION_UNIVERSE
        days: 回溯天數
        output_dir: 輸出目錄，預設 data/klines
    """
    symbols = symbols or SIMULATION_UNIVERSE
    output_dir = output_dir or KLINE_DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    
    fetcher = TWDataFetcher()
    end = datetime.now()
    start = (end - timedelta(days=days)).strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    
    imported = 0
    failed = []
    
    for symbol in symbols:
        try:
            df = fetcher.fetch_klines(symbol, start, end_str)
            if df.empty or len(df) < 10:
                failed.append((symbol, "資料不足"))
                continue
            out_path = output_dir / f"{symbol}.parquet"
            try:
                df.to_parquet(out_path, index=False)
            except Exception:
                out_path = output_dir / f"{symbol}.csv"
                df.to_csv(out_path, index=False, encoding="utf-8-sig")
            imported += 1
            logger.info(f"匯入 {symbol}: {len(df)} 筆 -> {out_path.name}")
        except Exception as e:
            failed.append((symbol, str(e)))
    
    return {"imported": imported, "failed": failed, "output_dir": str(output_dir)}


if __name__ == "__main__":
    logger.info("開始匯入歷史 K 線...")
    result = import_klines(days=365)
    logger.info(f"完成：成功 {result['imported']} 檔，失敗 {len(result['failed'])} 檔")
    if result["failed"]:
        for sym, err in result["failed"]:
            logger.warning(f"  {sym}: {err}")
    logger.info(f"輸出目錄: {result['output_dir']}")
