"""
基底 Agent 類別
負責與 Google Gemini LLM 溝通、管理系統提示詞 (System Prompt) 及歷史對話。
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
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
        system_instruction: str = ""
    ):
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY is not set. Agents will not be able to call the API.")
            
        genai.configure(api_key=GEMINI_API_KEY)
        
        self.model_name = model_name
        self.temperature = temperature
        self.system_instruction = system_instruction
        
        # 建立附帶 System Instruction 的 Model 實例
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_instruction,
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
            
            if response.text:
                return response.text
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
