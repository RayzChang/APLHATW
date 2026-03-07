"""
基底 Agent 類別
負責與 Google Gemini LLM 溝通、管理系統提示詞 (System Prompt) 及歷史對話。
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.generativeai import protos
from loguru import logger

from config.settings import GEMINI_API_KEY


class BaseAgent(ABC):
    """
    所有特定 Agent (如技術分析師、風控大師等) 的基底類別。
    封裝了對 Gemini API 的呼叫邏輯。
    """
    
    def __init__(
        self, 
        model_name: str = "gemini-2.0-flash", 
        temperature: float = 0.2,
        system_instruction: str = "",
        enable_search: bool = False
    ):
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY is not set. Agents will not be able to call the API.")
            
        genai.configure(api_key=GEMINI_API_KEY)
        
        self.model_name = model_name
        self.temperature = temperature
        self.system_instruction = system_instruction
        
        tools = []
        if enable_search:
            # 檢查模型版本是否支援 Search Grounding (gemini-2.0-flash 以上)
            is_supported = "2.5" in model_name or "2.0-flash" in model_name
            if is_supported:
                # 使用 protos 方式定義 Google Search 以確保相容性
                tools = [protos.Tool(google_search=protos.Tool.GoogleSearch())]
            else:
                logger.warning(f"模型 {model_name} 可能不支援 Google Search Grounding。推薦使用 gemini-2.0-flash 以上版本。")

        # 建立附帶 System Instruction 與 Tools 的 Model 實例
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_instruction,
            tools=tools if tools else None,
            generation_config=GenerationConfig(
                temperature=self.temperature,
            )
        )

    @abstractmethod
    def analyze(self, *args, **kwargs) -> Any:
        """
        子類別必須實作此方法，負責收集自身專屬的資料並呼叫 generate_response
        """
        pass

    def generate_response(self, prompt: str, require_json: bool = False) -> str:
        """
        傳送 prompt 給 Gemini 並取得回覆。
        若 require_json=True，則在 generation_config 中強制輸出 JSON (某些 Gemini 模型支援)。
        """
        if not GEMINI_API_KEY:
            return "Error: GEMINI_API_KEY is not configured."

        try:
            config = GenerationConfig(temperature=self.temperature)
            if require_json:
                config.response_mime_type = "application/json"

            response = self.model.generate_content(prompt, generation_config=config)
            
            res_text = response.text or ""
            
            # 若有搜尋來源 (Grounding Metadata)，附加到文末
            try:
                if hasattr(response, 'candidates') and len(response.candidates) > 0:
                    metadata = getattr(response.candidates[0], 'grounding_metadata', None)
                    if metadata:
                        urls = []
                        chunks = getattr(metadata, 'grounding_chunks', [])
                        for chunk in chunks:
                            if hasattr(chunk, 'web') and chunk.web.uri:
                                urls.append(chunk.web.uri)
                        
                        if urls:
                            unique_urls = list(dict.fromkeys(urls))
                            res_text += f"\n\n[參考來源]: {', '.join(unique_urls)}"
            except Exception as ge:
                logger.debug(f"萃取 Grounding Metadata 失敗: {ge}")

            if res_text:
                return res_text
            else:
                logger.error(f"Empty response from Gemini: {response}")
                return ""
        except Exception as e:
            logger.error(f"Gemini API request failed: {e}")
            return f"Error: {str(e)}"

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        """
        強制模型回傳 JSON，並將其解析為 Python Dict。
        如果解析失敗，會擷取 markdown json 區塊。
        """
        text = self.generate_response(prompt, require_json=True)
        try:
            # 直接嘗試解析
            return json.loads(text)
        except json.JSONDecodeError:
            # 清理 Markdown 代碼區塊 (如 ```json ... ```)
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            try:
                return json.loads(text.strip())
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from Gemini response: {e}\nRaw Text: {text}")
                return {"error": "Failed to parse JSON", "raw": text}
