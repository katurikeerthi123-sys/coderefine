import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

from app.config import GROQ_API_KEY, DEFAULT_GROQ_TEXT_MODEL
from app.services.llm_provider import LLMProvider

class GroqProvider(LLMProvider):
    """Groq API implementation of LLMProvider interface."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = (api_key and api_key.strip()) or GROQ_API_KEY
        self.model = model or DEFAULT_GROQ_TEXT_MODEL
        
    def _call_groq(self, payload: dict) -> str:
        if not self.api_key:
            raise ValueError("Groq API Key is not configured.")
            
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "CodeRefine-Agentic/1.0"
        }
        
        req_body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
        
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = response.read().decode("utf-8")
            res_json = json.loads(res_data)
            choices = res_json.get("choices", [])
            if not choices:
                raise RuntimeError("Groq API returned no choices.")
            return choices[0].get("message", {}).get("content", "")

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages
        }
        return self._call_groq(payload)

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
            f"Respond with a valid JSON object matching this schema."
        )
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": full_prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"}
        }
        raw_text = self._call_groq(payload)
        return self.parse_json_safely(raw_text)
