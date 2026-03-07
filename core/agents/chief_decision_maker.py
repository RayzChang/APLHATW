from typing import Dict, Any
from core.agents.base_agent import BaseAgent
from loguru import logger

class ChiefDecisionMakerAgent(BaseAgent):
    """
    首席決策長。統整技術面、情緒面、風控面的報告，給出最終的 JSON 決策結果。
    """
    
    SYSTEM_INSTRUCTION = """
    你是一位掌管百億美金對沖基金的首席投資長 (CIO)。
    你的下屬 (技術分析師、市場情緒分析師、風控長) 剛剛遞交了他們針對同一標的的分析報告。
    你的任務是：
    1. 綜合審視這三份報告，找出潛在的盲點與共識。
    2. 做最終的拍板決策。
    
    你必須嚴格輸出以下 JSON 格式 (切勿加入任何其他 markdown 文字)：
    {
      "action": "BUY" | "SELL" | "HOLD",
      "confidence": 0.0 ~ 1.0,
      "reasoning": "簡介你的核心決策邏輯 (繁體中文)",
      "take_profit_price": 數字或 null,
      "stop_loss_price": 數字或 null,
      "position_size_pct": 0 ~ 100 (建議投入資金百分比)
    }
    """

    def __init__(self, temperature: float = 0.1):
        # 為了確保 JSON 格式穩定，temperature 盡量低
        super().__init__(
            system_instruction=self.SYSTEM_INSTRUCTION,
            temperature=temperature
        )

    def analyze(self, symbol: str, name: str, current_price: float, tech_report: str, sent_report: str, risk_report: str) -> Dict[str, Any]:
        """
        傳入三份報告，產出最終決定 (JSON)
        """
        prompt = f"""
        標的：{name} ({symbol})
        目前股價：{current_price}
        
        【技術分析報告】
        {tech_report}
        
        【市場情緒報告】
        {sent_report}
        
        【風險控管報告】
        {risk_report}
        
        請立刻給出決策結果 (必須為 JSON)。
        """
        logger.debug(f"ChiefDecisionMaker generating final JSON for {symbol}...")
        return super().generate_json(prompt)
