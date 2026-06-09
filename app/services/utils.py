import re
import urllib.parse
from typing import Dict

def extract_code_block(text: str, default_lang: str = "") -> str:
    """
    Extracts code from standard markdown code blocks if present.
    If no code block is present, returns the text trimmed.
    """
    pattern = r"```(?:\w+)?\n([\s\S]*?)\n```"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return text.strip()

def generate_educational_links(error_topic: str) -> Dict[str, str]:
    """
    Generates YouTube and GeeksforGeeks search links for a given error topic.
    """
    encoded_topic = urllib.parse.quote(error_topic)
    return {
        "youtube": f"https://www.youtube.com/results?search_query={encoded_topic}",
        "geeksforgeeks": f"https://www.geeksforgeeks.org/search/?q={encoded_topic}"
    }
