import json
from loguru import logger
from core.agents.base_agent import BaseAgent
from config.settings import AGENT_MODELS, AGENT_TEMPERATURES

class TechnicalAnalystAgent(BaseAgent):
    """
    技術分析領域的專家。負責解讀 K 線、均線與所有技術指標。
    """
    
    SYSTEM_INSTRUCTION = """
    你是一位擁有 20 年經驗的華爾街頂級首席技術分析師。
    你的專長是圖表模式辨識、動能指標分析與尋找最佳買賣點。
    你即將收到一份關於特定股票的技術面數據。請你提供一份簡潔有力、充滿洞見的技術分析報告，不要廢話。
    你的報告必須包含：
    1. 趨勢判斷 (短多/短空/盤整)
    2. 關鍵指標解讀 (挑選出最關鍵的 2 個指標，如 RSI 超買、MACD 背離等)
    3. 結論與建議支撐/壓力位
    """

    def __init__(self, temperature: float = None, enable_search: bool = False):
        model = AGENT_MODELS["technical"]
        temp = temperature if temperature is not None else AGENT_TEMPERATURES["technical"]
        super().__init__(
            model_name=model,
            system_instruction=self.SYSTEM_INSTRUCTION,
            temperature=temp,
            enable_search=enable_search
        )

    def analyze(self, symbol: str, name: str, current_price: float, technical_data: Dict[str, Any]) -> str:
        """
        傳入技術面資料，請 Agent 進行分析
        """
        prompt = f"""
        標的：{name} ({symbol})
        目前股價：{current_price}
        
        近期技術面數據：
        {json.dumps(technical_data, indent=2, ensure_ascii=False)}
        
        請立刻給出你的專業技術分析報告。
        """
        logger.debug(f"TechnicalAnalyst analyzing {symbol}...")
        return super().generate_response(prompt)
