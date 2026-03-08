import json
from typing import List
from loguru import logger
from core.agents.base_agent import BaseAgent
from core.data.news_fetcher import NewsItem
from config.settings import AGENT_MODELS, AGENT_TEMPERATURES

class SentimentAnalystAgent(BaseAgent):
    """
    市場情緒領域的專家。負責評估巨觀新聞、個股新聞對投資人情緒的影響。
    """
    
    SYSTEM_INSTRUCTION = """
你是全球頂尖對沖基金的市場情緒獵人，
專門從新聞、社群媒體、法人動向中
嗅出市場的恐懼與貪婪。

你擁有 Google Search 工具，
這是你最重要的武器，你必須主動使用它。

【分析流程，必須照順序執行】

Step 1：立刻搜尋以下三組關鍵字
搜尋1："{股票名稱} {股票代碼} 新聞 2026"
搜尋2："{股票名稱} 外資 投信 籌碼 買超 賣超"
搜尋3："{股票名稱} 營收 EPS 法說會 獲利"

Step 2：整理搜尋結果，輸出以下報告

【第一章：重大新聞事件】
列出近期3~5則最重要新聞，每則包含：
- 標題
- 發布時間
- 對股價影響：正面/負面/中性
- 影響程度：高/中/低

【第二章：法人籌碼動向】
- 外資：連續買超X天 或 連續賣超X天，累計X張
- 投信：買超/賣超，累計X張
- 自營商：買超/賣超
- 籌碼面綜合判斷：偏多/偏空/中立

【第三章：基本面快照】
- 最新月營收年增率：+X% 或 -X%
- 最新EPS或本益比（若查得到）
- 近期是否有重大利多或利空事件

【第四章：市場情緒判定】
- 整體情緒：極度貪婪/貪婪/中立/恐慌/極度恐慌
- 情緒評分：-10（極度悲觀）~ +10（極度樂觀）
- 評分依據：說明為何給這個分數

【第五章：情緒面結論】
- 情緒面偏向：強烈看多/看多/中立/看空/強烈看空
- 最大潛在風險事件：一句話描述
- 最大潛在催化劑：一句話描述

【鐵則】
- 必須執行搜尋，不得跳過
- 搜尋到資料才能分析，但禁止說「缺乏數據」
- 若真的搜尋不到，說明搜尋了什麼、結果如何，
  然後基於技術面和產業背景做合理推斷
- 禁止輸出免責聲明
- 報告長度：400~600字
    """

    def __init__(self, temperature: float = None, enable_search: bool = False):
        model = AGENT_MODELS["sentiment"]
        temp = temperature if temperature is not None else AGENT_TEMPERATURES["sentiment"]
        super().__init__(
            model_name=model,
            system_instruction=self.SYSTEM_INSTRUCTION,
            temperature=temp,
            enable_search=enable_search
        )

    def analyze(self, symbol: str, name: str, news_items: List[NewsItem]) -> str:
        """
        傳入近期新聞，請 Agent 進行分析
        """
        # 整理新聞資料讓 prompt 更簡潔
        formatted_news = []
        for n in news_items:
            formatted_news.append({
                "title": n.title,
                "summary": n.summary[:200] + "...",  # 擷取前200字即可
                "date": n.published.strftime("%Y-%m-%d %H:%M:%S") if hasattr(n.published, 'strftime') else str(n.published),
                "basic_sentiment": n.sentiment
            })

        prompt = f"""
        標的：{name} ({symbol})
        
        近期相關新聞與系統初步情緒評分：
        {json.dumps(formatted_news, indent=2, ensure_ascii=False)}
        
        請立刻給出你的專業情緒分析報告。
        """
        logger.debug(f"SentimentAnalyst analyzing news for {symbol}...")
        return super().generate_response(prompt)
