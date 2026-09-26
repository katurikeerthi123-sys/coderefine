import abc
import json
import re
from typing import Dict, Any, Optional, List

class LLMProvider(abc.ABC):
    """
    Abstract Base Class for unified LLM provider implementations.
    Decouples Agent Orchestration from specific model drivers.
    """
    
    @abc.abstractmethod
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generates plain text completion."""
        pass
        
    @abc.abstractmethod
    def generate_structured_output(
        self, 
        prompt: str, 
        schema_desc: str, 
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generates structured JSON object matching schema description."""
        pass

    def parse_json_safely(self, text: str) -> Dict[str, Any]:
        """Utility to safely extract JSON object from markdown wrapped text."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = text[start_idx:end_idx + 1]
                return json.loads(json_str)
            raise

def get_llm_provider(
    user_groq_key: Optional[str] = None, 
    user_gemini_key: Optional[str] = None, 
    provider_name: Optional[str] = None
) -> LLMProvider:
    """Factory helper to obtain an active LLMProvider instance."""
    from app.services.groq_provider import GroqProvider
    from app.services.gemini_provider import GeminiProvider
    
    if provider_name == "gemini" or (user_gemini_key and not user_groq_key):
        return GeminiProvider(api_key=user_gemini_key)
    return GroqProvider(api_key=user_groq_key)

