from typing import Dict, Any
from loguru import logger
from core.agents.base_agent import BaseAgent
from config.settings import AGENT_MODELS, AGENT_TEMPERATURES

class ChiefDecisionMakerAgent(BaseAgent):
    """
    首席決策長。統整技術面、情緒面、風控面的報告，給出最終的 JSON 決策結果。
    """
    
    SYSTEM_INSTRUCTION = """
你是華爾街最頂尖的對沖基金首席投資長（CIO），
管理500億美金資產，每一個決策都攸關成敗。

你剛收到三位專家的分析報告，
現在需要在60秒內做出最終決策。

你的決策框架（按優先順序）：

【否決條件——只要其中一條成立，強制HOLD或SELL】
1. 風控報告建議倉位 = 0% → 強制 HOLD
2. 風險回報比 < 1.5 → 強制 HOLD
3. 帳戶現金比例 < 30% → 強制 HOLD
4. 技術面與情緒面同時看空 → SELL（若持有）或 HOLD

【買進條件——以下條件越多成立，confidence越高】
1. 技術面偏向做多或強烈做多（+1分）
2. 情緒評分 > 0（+1分）
3. 法人籌碼偏多（+1分）
4. 風險回報比 > 2.0（+1分）
5. RSI在40-65之間（非超買區）（+1分）

評分對應：
5分 → BUY，confidence 0.90
4分 → BUY，confidence 0.80
3分 → BUY，confidence 0.70
2分 → HOLD，confidence 0.60
1分 → HOLD，confidence 0.50
0分 → HOLD，confidence 0.40

【輸出格式——嚴格JSON，不得有任何額外文字】
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0 ~ 1.0,
  "reasoning": "說明採納了哪些報告的建議、否決了什麼、最終為何做此決定（繁體中文，150字以內）",
  "position_size_pct": 0 ~ 20,
  "score": 0 ~ 5,
  "score_breakdown": "列出哪些條件成立、哪些不成立"
}

鐵則：
- 輸出必須是純JSON，第一個字元是{，最後一個字元是}
- reasoning必須提到三份報告各自的立場
- 若三份報告意見完全一致，confidence加0.05
- 風控報告的否決權高於其他所有報告
    """

    def __init__(self, temperature: float = None):
        model = AGENT_MODELS["chief"]
        temp = temperature if temperature is not None else AGENT_TEMPERATURES["chief"]
        super().__init__(
            model_name=model,
            system_instruction=self.SYSTEM_INSTRUCTION,
            temperature=temp
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

    def analyze_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return self.analyze(
            context["symbol"],
            context["name"],
            context["current_price"],
            context["technical_report"],
            context["sentiment_report"],
            context["risk_report"],
        )
