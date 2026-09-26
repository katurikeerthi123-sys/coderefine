from typing import Dict, Any, List
from app.retrieval.search import CodeSearchEngine

search_engine = CodeSearchEngine()

def search_repository(query: str, max_results: int = 15) -> Dict[str, Any]:
    """Performs lexical search across repository files."""
    try:
        results = search_engine.search_code(query, max_results=max_results)
        return {"success": True, "query": query, "matches_found": len(results), "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}

def locate_symbol(symbol_name: str) -> Dict[str, Any]:
    """Locates class and function definitions across codebase."""
    try:
        symbols = search_engine.find_symbol(symbol_name)
        return {"success": True, "symbol_name": symbol_name, "symbols": symbols}
    except Exception as e:
        return {"success": False, "error": str(e)}
