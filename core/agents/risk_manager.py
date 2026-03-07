from typing import Dict, Any
from core.agents.base_agent import BaseAgent
import json
from loguru import logger

class RiskManagerAgent(BaseAgent):
    """
    風險控管專家。負責評估當前部位、資金水位，給出風控建議。
    """
    
    SYSTEM_INSTRUCTION = """
    你是華爾街頂尖量化基金的首席風險控管長 (Chief Risk Officer)。
    你的最高原則是「永遠不要爆倉，保住本金」。
    你即將收到目前的帳戶資金水位、以及打算要交易的標的現況。
    請分析目前的曝險狀態，並給出你的風控報告，內容包含：
    1. 帳戶健康度評估
    2. 該筆潛在交易的風險評級 (低風險 / 中風險 / 高風險 / 極端風險)
    3. 最大建議倉位限制 (例如：建議不超過總資金的 5%)
    """

    def __init__(self, temperature: float = 0.0):
        # 風控需要非常嚴謹，temperature 設為 0.0
        super().__init__(
            system_instruction=self.SYSTEM_INSTRUCTION,
            temperature=temperature
        )

    def analyze(self, symbol: str, name: str, current_price: float, portfolio: Dict[str, Any]) -> str:
        """
        傳入帳戶資訊，請 Agent 進行風險評估
        """
        prompt = f"""
        即將評估標的：{name} ({symbol}) ，目前股價：{current_price}
        
        當前模擬帳戶與持倉狀態：
        總資產：{portfolio.get('total_assets', 0)}
        可用現金：{portfolio.get('available_cash', 0)}
        預期總資金投入比例上限：20% (如果現金太少，應該阻止交易)
        已持有該標的部位數量：{portfolio.get('current_position_size', 0)}
        
        請立刻給出你的風險控管報告。
        """
        logger.debug(f"RiskManager analyzing exposure for {symbol}...")
        return super().generate_response(prompt)
