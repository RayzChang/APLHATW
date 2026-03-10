"""
基底 Agent 類別
負責與 Google Gemini LLM 溝通、管理系統提示詞 (System Prompt) 及歷史對話。
"""

import json
import importlib
from abc import ABC, abstractmethod
from typing import Any, Dict

from loguru import logger

from config.settings import GEMINI_API_KEY

try:
    from google import genai as genai_sdk
    from google.genai import types as genai_types
    HAS_NEW_GENAI = True
except Exception:
    genai_sdk = None
    genai_types = None
    HAS_NEW_GENAI = False

legacy_genai = None
legacy_protos = None
LegacyGenerationConfig = None
HAS_LEGACY_GENAI = False


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
        
        self.model_name = model_name
        self.temperature = temperature
        self.system_instruction = system_instruction
        self.enable_search = enable_search
        self._backend = None
        self._tools = []
        
        if enable_search:
            # 檢查模型版本是否支援 Search Grounding (gemini-2.0-flash 以上)
            is_supported = "2.5" in model_name or "2.0-flash" in model_name
            if is_supported:
                self._tools = ["google_search"]
            else:
                logger.warning(f"模型 {model_name} 可能不支援 Google Search Grounding。推薦使用 gemini-2.0-flash 以上版本。")

        if HAS_NEW_GENAI and GEMINI_API_KEY:
            self._backend = "new"
            self.client = genai_sdk.Client(api_key=GEMINI_API_KEY)
            logger.debug("BaseAgent using google.genai backend.")
        else:
            self._load_legacy_sdk_if_available()

        if self._backend is None and HAS_LEGACY_GENAI:
            self._backend = "legacy"
            legacy_genai.configure(api_key=GEMINI_API_KEY)
            legacy_tools = []
            if self._tools and legacy_protos:
                legacy_tools = [legacy_protos.Tool(google_search=legacy_protos.Tool.GoogleSearch())]
            self.model = legacy_genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.system_instruction,
                tools=legacy_tools if legacy_tools else None,
                generation_config=LegacyGenerationConfig(
                    temperature=self.temperature,
                )
            )
            logger.debug("BaseAgent using google.generativeai backend.")
        elif self._backend is None:
            self._backend = None
            logger.error("No compatible Gemini SDK installed. Install google-genai or google-generativeai.")

    @staticmethod
    def _load_legacy_sdk_if_available() -> None:
        global legacy_genai, legacy_protos, LegacyGenerationConfig, HAS_LEGACY_GENAI
        if HAS_LEGACY_GENAI:
            return
        try:
            legacy_genai = importlib.import_module("google.generativeai")
            legacy_types = importlib.import_module("google.generativeai.types")
            legacy_protos = importlib.import_module("google.generativeai").protos
            LegacyGenerationConfig = legacy_types.GenerationConfig
            HAS_LEGACY_GENAI = True
        except Exception:
            HAS_LEGACY_GENAI = False

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
        if not self._backend:
            return "Error: Gemini SDK is not available."

        try:
            if self._backend == "new":
                config_kwargs = {
                    "temperature": self.temperature,
                    "system_instruction": self.system_instruction,
                }
                if require_json:
                    config_kwargs["response_mime_type"] = "application/json"
                if self._tools:
                    config_kwargs["tools"] = [genai_types.Tool(google_search=genai_types.GoogleSearch())]
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(**config_kwargs),
                )
                res_text = getattr(response, "text", "") or ""
            else:
                config = LegacyGenerationConfig(temperature=self.temperature)
                if require_json:
                    config.response_mime_type = "application/json"
                response = self.model.generate_content(prompt, generation_config=config)
                res_text = response.text or ""

                # legacy SDK 若有搜尋來源 (Grounding Metadata)，附加到文末
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
