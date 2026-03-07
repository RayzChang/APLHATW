import json
from loguru import logger
from core.agents.base_agent import BaseAgent
from core.data.news_fetcher import NewsItem
from config.settings import AGENT_MODELS, AGENT_TEMPERATURES

class SentimentAnalystAgent(BaseAgent):
    """
    市場情緒領域的專家。負責評估巨觀新聞、個股新聞對投資人情緒的影響。
    """
    
    SYSTEM_INSTRUCTION = """
    你是一位華爾街資深對沖基金的市場情緒與總體經濟分析師。
    你非常擅長從凌亂的新聞頭條中捕捉市場的「貪婪與恐懼」。
    你即將收到特定標的近期的相關新聞標題與摘要（可能包含大盤新聞）。
    請給出一份市場情緒分析報告，內容包含：
    1. 總體情緒判定 (極度樂觀 / 樂觀 / 中立 / 悲觀 / 極度恐懼)
    2. 驅動情緒的主要新聞事件摘要
    3. 潛在的新聞風險提示 (如果有)
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
