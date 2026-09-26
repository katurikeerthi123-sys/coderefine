import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from app.config import BASE_DIR
from app.agents.tools.filesystem import _resolve_safe_path

ALLOWLIST_COMMANDS = {"pytest", "python", "flake8", "npm"}

def run_syntax_check(filepath: str) -> Dict[str, Any]:
    """Runs a Python syntax compilation check on a target file."""
    try:
        path = _resolve_safe_path(filepath)
        if not path.exists() or not path.is_file():
            return {"success": False, "error": f"File '{filepath}' not found."}
            
        if not filepath.endswith(".py"):
            return {"success": True, "message": "Syntax check skipped for non-python file."}

        cmd = [sys.executable, "-m", "py_compile", str(path)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if res.returncode == 0:
            return {"success": True, "clean": True, "message": "Syntax check passed cleanly."}
        else:
            return {
                "success": True,
                "clean": False,
                "error": res.stderr.strip() or res.stdout.strip()
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

def run_tests(test_target: Optional[str] = None) -> Dict[str, Any]:
    """Executes pytest or unittest on specified target or tests/ directory."""
    try:
        cmd = [sys.executable, "-m", "unittest"]
        if test_target:
            path = _resolve_safe_path(test_target)
            cmd.append(str(path))
        else:
            cmd.extend(["discover", "-s", "tests", "-p", "test_*.py"])
            
        res = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True, timeout=15)
        
        passed = (res.returncode == 0)
        output = res.stderr.strip() or res.stdout.strip()
        
        return {
            "success": True,
            "tests_passed": passed,
            "returncode": res.returncode,
            "output": output[:3000]  # Cap output size
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Test execution timed out (15s limit)."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def save_generated_test(test_filename: str, test_code: str) -> Dict[str, Any]:
    """Saves generated test suite into the tests/ directory."""
    try:
        if not test_filename.startswith("test_"):
            test_filename = f"test_{test_filename}"
        if not test_filename.endswith(".py"):
            test_filename = f"{test_filename}.py"
            
        rel_path = f"tests/{test_filename}"
        path = _resolve_safe_path(rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(test_code, encoding="utf-8")
        
        return {"success": True, "test_file": rel_path, "bytes": len(test_code)}
    except Exception as e:
        return {"success": False, "error": str(e)}
