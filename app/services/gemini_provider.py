import json
import os
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

from app.services.llm_provider import LLMProvider

class GeminiProvider(LLMProvider):
    """Google Gemini API implementation of LLMProvider interface."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = (api_key and api_key.strip()) or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("DEFAULT_GEMINI_MODEL", "gemini-1.5-flash")
        
    def _call_gemini(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.api_key:
            raise ValueError("Gemini API Key is not configured.")
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Context: {system_prompt}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        
        payload = {"contents": contents}
        req_body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
        
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = response.read().decode("utf-8")
            res_json = json.loads(res_data)
            candidates = res_json.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini API returned no candidates.")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise RuntimeError("Gemini API returned empty parts.")
            return parts[0].get("text", "")

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return self._call_gemini(prompt, system_prompt)

    def generate_structured_output(
        self, 
        prompt: str, 
        schema_desc: str, 
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        full_prompt = (
            f"{prompt}\n\n"
            f"Expected JSON Schema / Output Format:\n"
            f"{schema_desc}\n\n"
            f"Respond strictly with a raw valid JSON object matching this schema."
        )
        raw_text = self._call_gemini(full_prompt, system_prompt)
        return self.parse_json_safely(raw_text)
