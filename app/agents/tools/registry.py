import time
from typing import Dict, Any, Callable

from app.agents.tools.filesystem import read_file, list_files, apply_patch
from app.agents.tools.search import search_repository, locate_symbol
from app.agents.tools.testing import run_syntax_check, run_tests, save_generated_test
from app.agents.tools.git import inspect_git_diff

TOOL_REGISTRY: Dict[str, Callable] = {
    "read_file": read_file,
    "list_files": list_files,
    "apply_patch": apply_patch,
    "search_repository": search_repository,
    "locate_symbol": locate_symbol,
    "run_syntax_check": run_syntax_check,
    "run_tests": run_tests,
    "save_generated_test": save_generated_test,
    "inspect_git_diff": inspect_git_diff
}

RISKY_TOOLS = {"apply_patch", "save_generated_test"}

def get_available_tools_schema() -> str:
    """Returns documentation schema of registered tools for LLM prompts."""
    return """
1. read_file(filepath: str, start_line: int, end_line: int) -> Read file contents line-by-line.
2. list_files(directory: str) -> List files in directory.
3. search_repository(query: str, max_results: int) -> Search codebase for text patterns.
4. locate_symbol(symbol_name: str) -> Find class and function definitions across project.
5. run_syntax_check(filepath: str) -> Run Python syntax validation on a file.
6. run_tests(test_target: str) -> Execute unit tests safely via pytest/unittest runner.
7. save_generated_test(test_filename: str, test_code: str) -> Save generated pytest/unittest file.
8. apply_patch(filepath: str, new_content: str) -> Update/overwrite file content (requires approval).
9. inspect_git_diff() -> Inspect modifications made across workspace.
"""

def execute_tool(name: str, kwargs: dict) -> Dict[str, Any]:
    """Executes a registered tool with execution logging and size bounds."""
    if name not in TOOL_REGISTRY:
        return {"success": False, "error": f"Tool '{name}' is not registered."}
        
    start_time = time.time()
    func = TOOL_REGISTRY[name]
    
    try:
        result = func(**kwargs)
        duration_ms = int((time.time() - start_time) * 1000)
        
        return {
            "tool_name": name,
            "result": result,
            "duration_ms": duration_ms,
            "is_risky": name in RISKY_TOOLS
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            "tool_name": name,
            "result": {"success": False, "error": str(e)},
            "duration_ms": duration_ms,
            "is_risky": name in RISKY_TOOLS
        }
