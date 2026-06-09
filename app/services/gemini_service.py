import os
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List

from app.config import DEFAULT_GEMINI_MODEL, GEMINI_API_KEY

def _call_gemini_rest_inner(api_key: Optional[str], payload: dict, model_name: str) -> str:
    """Helper to perform the actual HTTP request to the Gemini endpoint."""
    key = api_key or GEMINI_API_KEY
    if not key:
        raise ValueError(
            "Gemini API Key is not configured. Please save a key in Settings or set the GEMINI_API_KEY environment variable."
        )
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
    headers = {"Content-Type": "application/json"}
    req_body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
    
    with urllib.request.urlopen(req) as response:
        res_data = response.read().decode("utf-8")
        res_json = json.loads(res_data)
        
        candidates = res_json.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates. The request may have been blocked or filtered.")
        
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            raise RuntimeError("Gemini returned an empty candidate content parts.")
        
        return parts[0].get("text", "")

def _call_gemini_rest(api_key: Optional[str], payload: dict, model_name: str = DEFAULT_GEMINI_MODEL) -> str:
    """
    Makes a raw REST API call to the Gemini API endpoint. Automatically falls back
    to alternative models if the primary model is experiencing high demand or quota limits.
    """
    try:
        return _call_gemini_rest_inner(api_key, payload, model_name)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_msg)
            message = err_json.get("error", {}).get("message", err_msg)
        except Exception:
            message = err_msg
            
        # Try fallbacks for rate limits, high demand or quotas
        msg_lower = message.lower()
        if "high demand" in msg_lower or "quota" in msg_lower or "limit" in msg_lower or "rate" in msg_lower:
            fallbacks = ["gemini-2.0-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]
            for fallback in fallbacks:
                if fallback != model_name:
                    try:
                        return _call_gemini_rest_inner(api_key, payload, fallback)
                    except Exception:
                        continue
        
        raise RuntimeError(f"Gemini API Error: {message}")
    except Exception as e:
        # Check standard exception text for demand issues
        err_lower = str(e).lower()
        if "high demand" in err_lower or "quota" in err_lower or "limit" in err_lower:
            fallbacks = ["gemini-2.0-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]
            for fallback in fallbacks:
                if fallback != model_name:
                    try:
                        return _call_gemini_rest_inner(api_key, payload, fallback)
                    except Exception:
                        continue
        raise RuntimeError(f"Gemini Request Failed: {str(e)}")

def parse_gemini_json(text: str) -> Dict[str, Any]:
    """
    Cleans and extracts standard JSON objects from the text returned by Gemini.
    Bypasses markdown wrapping markers (e.g. ```json ... ```) or prefix text.
    """
    text = text.strip()
    
    # Strip markdown headers if they wrapper the JSON
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
        # Fallback to search outermost bounds of JSON block
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(f"Failed to parse Gemini JSON output: {e.msg}", e.doc, e.pos)
        raise

def review_code(code: str, language: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Performs code review by calling the Gemini API.
    """
    prompt = f"""
    You are an expert code reviewer and optimization engine.
    Analyze the following code written in {language}.
    
    Code:
    {code}
    
    Perform the following tasks:
    1. Propose a short, descriptive title for this optimization (e.g. "Optimized Fibonacci Loop").
    2. Detect bugs, logical flaws, syntax errors, or inefficiencies. Rate their severity as High, Medium, or Low.
    3. Generate custom security badges (e.g., "SQL Injection Vulnerability", "Safe", "Sensitive Data Exposure"). Label their status as "danger" (vulnerable/high risk), "warning" (moderate risk/bad practice), or "success" (safe/best practice).
    4. Outline key improvements you recommend.
    5. Provide the optimized code block. Make sure it is fully functional and adheres to best practices.

    Provide your response as a JSON object matching this exact schema:
    {{
      "title": "A short title",
      "bugs": [
        {{
          "severity": "High" | "Medium" | "Low",
          "description": "Explanation of the bug",
          "line_number": 12,
          "suggestion": "How to fix it"
        }}
      ],
      "security_badges": [
        {{
          "name": "Badge Name",
          "status": "success" | "warning" | "danger",
          "description": "Reason for badge"
        }}
      ],
      "improvements": [
        "First improvement suggestion",
        "Second improvement suggestion"
      ],
      "optimized_code": "The full optimized code output"
    }}
    """
    
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    response_text = _call_gemini_rest(api_key, payload)
    return parse_gemini_json(response_text)

def analyze_complexity(code: str, language: str, eli5: bool = False, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyzes algorithmic complexity and returns a structured complexity bounds report.
    """
    eli5_instruction = "Make the explanation simple, easy to understand, and suitable for a 5-year-old child (using analogies/metaphors)." if eli5 else "Provide a professional, clear explanation of the computational complexity."
    
    prompt = f"""
    You are an algorithmic complexity analyzer.
    Analyze the time and space complexity of the following {language} code.
    
    Code:
    {code}
    
    Tasks:
    1. Determine the Best-case time complexity (e.g. O(1), O(N)).
    2. Determine the Worst-case time complexity (e.g. O(N^2), O(log N)).
    3. Determine the Average-case time complexity.
    4. Provide a step-by-step traceout showing exactly how the loops, operations, or recursion lead to these bounds.
    5. Provide an explanation of the complexity bounds.
    
    {eli5_instruction}
    
    Provide your response as a JSON object matching this exact schema:
    {{
      "best_case": "O(...)",
      "worst_case": "O(...)",
      "average_case": "O(...)",
      "traceout": "Step-by-step mathematical complexity traceout...",
      "explanation": "Simple summary explanation of the complexities"
    }}
    """
    
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    response_text = _call_gemini_rest(api_key, payload)
    return parse_gemini_json(response_text)

def explain_error(code: str, error_logs: str, eli5: bool = False, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Explains compile or runtime errors and suggests educational search queries.
    """
    eli5_instruction = "Make the explanation simple, clear, and easy to digest, using plain English suitable for a beginner (ELI5)." if eli5 else "Provide a detailed technical root-cause analysis of the crash or syntax error."
    
    prompt = f"""
    You are an AI debugging assistant.
    Analyze the following code and corresponding error logs to diagnose the issue.
    
    Code:
    {code}
    
    Error Logs / Console Output:
    {error_logs}
    
    Tasks:
    1. Identify the core error summary (e.g., "TypeError: cannot unpack non-iterable NoneType object").
    2. Explain the root cause of the error. {eli5_instruction}
    3. Provide the corrected/fixed version of the code snippet.
    4. Identify 2 or 3 specific educational search keywords/topics (not full sentences, e.g. "Python division by zero error handling" or "Javascript variable shadowing") that a developer should search for on YouTube or GeeksforGeeks to study this concept.
    
    Provide your response as a JSON object matching this exact schema:
    {{
      "error_summary": "Name or summary of the error",
      "explanation": "Explanation of the root cause and why it happened",
      "fixed_code": "The complete fixed code block",
      "search_topics": [
        "Search Topic 1",
        "Search Topic 2"
      ]
    }}
    """
    
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    response_text = _call_gemini_rest(api_key, payload)
    return parse_gemini_json(response_text)

def analyze_screen_capture(image_bytes: bytes, mime_type: str = "image/png", api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Uses Gemini multimodal vision via REST API to process a captured base64 image frame.
    """
    prompt_text = """
    You are an expert developer looking at a screenshot of a code editor, IDE, or terminal.
    
    Tasks:
    1. Inspect the image closely and identify the coding error (syntax error, red squiggly underlines, compile warning, console traceout, or logical bug).
    2. Identify the programming language.
    3. Extract the original code snippet around the error.
    4. Explain the issue clearly.
    5. Provide the corrected/fixed version of the code snippet.
    
    Provide your response as a JSON object matching this exact schema:
    {
      "language": "programming language",
      "detected_error": "Description of the error spotted in the image",
      "original_code_snippet": "The broken code snippet extracted from the image",
      "explanation": "Clear explanation of what is wrong and how to fix it",
      "fixed_code_snippet": "The fixed/corrected code block"
    }
    """
    
    # Encode binary image bytes to base64 string
    import base64
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    
    # Construct REST API payload for multimodal input
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64_image
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    response_text = _call_gemini_rest(api_key, payload)
    return parse_gemini_json(response_text)
