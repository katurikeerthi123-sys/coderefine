import subprocess
from typing import Dict, Any

from app.config import BASE_DIR

def inspect_git_diff() -> Dict[str, Any]:
    """Inspects git status or modified diff in the workspace."""
    try:
        cmd = ["git", "diff"]
        res = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True, timeout=10)
        
        diff_output = res.stdout.strip()
        if not diff_output:
            diff_output = "No uncommitted git changes detected."
            
        return {
            "success": True,
            "has_changes": bool(res.stdout.strip()),
            "diff": diff_output[:5000]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
