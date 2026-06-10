import os
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List

from app.config import DEFAULT_GROQ_TEXT_MODEL, DEFAULT_GROQ_VISION_MODEL, GROQ_API_KEY

def _call_groq_rest(user_api_key: Optional[str], payload: dict) -> str:
    """
    Makes a raw REST API call to the Groq API endpoint.
    If the shared server key fails due to rate/quota limits, missing key, invalid key,
    or disabled key, it raises a user-friendly error suggesting they use a personal key.
    If a personal key is used and fails, it returns the raw API error details.
    """
    is_personal_key = bool(user_api_key and user_api_key.strip())
    key = user_api_key.strip() if is_personal_key else GROQ_API_KEY
    
    if not key:
        if not is_personal_key:
            raise RuntimeError(
                "The shared server AI service is currently unavailable. Please add your personal Groq API key in Settings to continue."
            )
        else:
            raise ValueError("Groq API Key is not configured. Please save a key in Settings.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req_body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = response.read().decode("utf-8")
            res_json = json.loads(res_data)
            
            choices = res_json.get("choices", [])
            if not choices:
                raise RuntimeError("Groq returned no choices. The request may have failed.")
            
            message = choices[0].get("message", {})
            content = message.get("content", "")
            return content
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        print(f"DEBUG: urllib.error.HTTPError status={e.code} body={err_msg}")
        try:
            err_json = json.loads(err_msg)
            message = err_json.get("error", {}).get("message", err_msg)
        except Exception:
            message = err_msg
            
        if not is_personal_key:
            # Fallback user friendly message
            raise RuntimeError(
                "The shared server AI service is currently unavailable. Please add your personal Groq API key in Settings to continue."
            )
        else:
            raise RuntimeError(f"Groq API Error: {message}")
    except Exception as e:
        import traceback
        print("DEBUG: Exception in _call_groq_rest:")
        traceback.print_exc()
        if not is_personal_key:
            raise RuntimeError(
                "The shared server AI service is currently unavailable. Please add your personal Groq API key in Settings to continue."
            )
        else:
            raise RuntimeError(f"Groq Request Failed: {str(e)}")

def parse_groq_json(text: str) -> Dict[str, Any]:
    """
    Cleans and extracts standard JSON objects from the text returned by Groq.
    Bypasses markdown wrapping markers (e.g. ```json ... ```) or prefix text.
    """
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
        # Fallback to search outermost bounds of JSON block
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(f"Failed to parse Groq JSON output: {e.msg}", e.doc, e.pos)
        raise

def review_code(code: str, language: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Performs code review by calling the Groq API.
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
        "model": DEFAULT_GROQ_TEXT_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    
    response_text = _call_groq_rest(api_key, payload)
    return parse_groq_json(response_text)

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
    4. Provide a highly detailed step-by-step mathematical traceout showing a real dry run execution trace instead of a summary.
       Do not limit the output to exactly 3 hardcoded main points. Instead, dynamically generate as many numbered main points (1, 2, 3, ..., M) as needed based on the code's complexity to fully document each logical phase of the algorithm:
       
       - Main Point: Sample Input (Define a concrete, simple sample input).
       - Main Point(s) for Code Blocks: Create separate main points for each major logical phase of the code (e.g., Variable Initialization, Pre-conditional Checks, Loop/Recursion Execution, Inner Loop Verification, State/Flag Updates).
       - Main Point: Step-by-Step Dry Run Trace (List each step of the execution on separate fresh lines, tracking loop iterations, comparisons, and variable changes).
       - Main Point: Derivation of Bounds (Mathematically show how the count of iterations, comparisons, or recursive depth generalizes to N, and derive the Best, Worst, and Average-case complexities from the actual trace steps).
       
    5. Provide an explanation of the complexity bounds.
    
    Formatting Constraints:
    - You MUST use raw newline characters ('\\n') to place each sub-section, loop iteration, dry run step, and comparison on a separate line.
    - DO NOT write a single wrapped paragraph. Each main point (1, 2, 3, ..., M), each dry run step, and every comparison statement must begin on its own fresh line with appropriate indentation to display the complete execution flow.
    
    {eli5_instruction}
    
    Provide your response as a JSON object matching this exact schema:
    {{
      "best_case": "O(...)",
      "worst_case": "O(...)",
      "average_case": "O(...)",
      "traceout": "Detailed dry run step trace and mathematical derivation structured exactly as instructed above with newlines",
      "explanation": "Simple summary explanation of the complexities"
    }}
    """
    
    payload = {
        "model": DEFAULT_GROQ_TEXT_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    
    response_text = _call_groq_rest(api_key, payload)
    return parse_groq_json(response_text)

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
        "model": DEFAULT_GROQ_TEXT_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    
    response_text = _call_groq_rest(api_key, payload)
    return parse_groq_json(response_text)

def chat_about_code(code: str, message: str, history: List[Dict[str, str]], api_key: Optional[str] = None) -> str:
    """
    Simulates a chat about a specific code snippet with Groq.
    """
    if code.strip():
        system_instruction = f"""
        You are a professional software engineering chatbot.
        Your sole focus is to help the user modify, update, improve, debug, and explain this code:
        
        ```
        {code}
        ```
        
        Guidelines:
        1. Only answer questions directly related to this code or software engineering queries about it.
        2. If the user asks general or unrelated questions, politely refuse and remind them that you can only discuss this specific code block.
        3. Keep explanations clear, and return code modifications directly inside markdown blocks.
        """
    else:
        system_instruction = """
        You are a professional software engineering chatbot and assistant.
        You help the user write, debug, explain, and optimize software engineering concepts, algorithms, and code.
        Keep explanations clear, and return code snippets directly inside markdown blocks.
        """
    
    messages = [
        {"role": "system", "content": system_instruction}
    ]
    
    # Add history
    for item in history:
        role = "user" if item.get("role") == "user" else "assistant"
        messages.append({
            "role": role,
            "content": item.get("text", "")
        })
        
    # Add current user message
    messages.append({
        "role": "user",
        "content": message
    })
    
    payload = {
        "model": DEFAULT_GROQ_TEXT_MODEL,
        "messages": messages
    }
    
    return _call_groq_rest(api_key, payload)

def analyze_screen_capture(image_bytes: bytes, mime_type: str = "image/png", api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Uses Groq multimodal vision via REST API to process a captured base64 image frame.
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
    {{
      "language": "programming language",
      "detected_error": "Description of the error spotted in the image",
      "original_code_snippet": "The broken code snippet extracted from the image",
      "explanation": "Clear explanation of what is wrong and how to fix it",
      "fixed_code_snippet": "The fixed/corrected code block"
    }}
    """
    
    # Encode binary image bytes to base64 string
    import base64
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    
    # Construct REST API payload for multimodal input
    payload = {
        "model": DEFAULT_GROQ_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                ]
            }
        ],
        "response_format": {"type": "json_object"}
    }
    
    response_text = _call_groq_rest(api_key, payload)
    return parse_groq_json(response_text)
