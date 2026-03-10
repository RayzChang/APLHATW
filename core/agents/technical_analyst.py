import json
from typing import Dict, Any
from loguru import logger
from core.agents.base_agent import BaseAgent
from config.settings import AGENT_MODELS, AGENT_TEMPERATURES

class TechnicalAnalystAgent(BaseAgent):
    """
    技術分析領域的專家。負責解讀 K 線、均線與所有技術指標。
    """
    
    SYSTEM_INSTRUCTION = """
你是一位擁有20年經驗的華爾街頂級技術分析師，
曾任職高盛、摩根士丹利，精通價格行為學。
你只相信圖表和數字，新聞對你毫無意義。

你收到的數據包含：股票代碼、現價、ATR、
RSI、MACD、均線(MA5/MA20/MA60)、
成交量、近期高低點。

你的分析報告必須包含以下五個章節，
每章節都要有具體數字支撐，不能說廢話：

【第一章：趨勢研判】
- 短線趨勢（5日）：多頭/空頭/盤整
- 中線趨勢（20日）：多頭/空頭/盤整
- 均線排列：多頭排列/空頭排列/糾結
- 股價與MA20距離百分比：+X% 或 -X%

【第二章：動能分析】
- RSI數值 + 判斷（超買>70/超賣<30/中性）
- MACD：金叉/死叉/零軸上下/柱狀體擴大縮小
- 成交量：放量/縮量/量價背離

【第三章：關鍵價位】
- 上方壓力1：價格 + 依據（前高/均線/整數關卡）
- 上方壓力2：價格 + 依據
- 下方支撐1：價格 + 依據
- 下方支撐2：價格 + 依據

【第四章：K線型態】
從以下型態中識別當前最符合的一個：
頭肩頂、頭肩底、雙頂、雙底、
三角收斂、旗形整理、箱型整理、
突破、跌破、島狀反轉、無明顯型態
說明型態成立的條件與目前完成度百分比。

【第五章：技術面結論】
- 技術面偏向：強烈做多/做多/中性/做空/強烈做空
- 最佳進場條件：描述何種情況下值得進場
- 最大風險：描述何種情況代表判斷錯誤需止損

報告長度：300~500字，必須有數字，禁止模糊表述。
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
        serialized_data = self._to_json_safe(technical_data)
        prompt = f"""
        標的：{name} ({symbol})
        目前股價：{current_price}
        
        近期技術面數據：
        {json.dumps(serialized_data, indent=2, ensure_ascii=False)}
        
        請立刻給出你的專業技術分析報告。
        """
        logger.debug(f"TechnicalAnalyst analyzing {symbol}...")
        return super().generate_response(prompt)

    def analyze_context(self, context: Dict[str, Any]) -> str:
        return self.analyze(
            context["symbol"],
            context["name"],
            context["current_price"],
            context["technical_data"],
        )

    def _to_json_safe(self, value: Any):
        if isinstance(value, dict):
            return {str(k): self._to_json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._to_json_safe(v) for v in value]
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                return str(value)
        return value
