import os
from pathlib import Path
from typing import Dict, Any, Optional

from app.config import BASE_DIR

def _resolve_safe_path(rel_path: str) -> Path:
    full_path = (BASE_DIR / rel_path).resolve()
    if not str(full_path).startswith(str(BASE_DIR.resolve())):
        raise PermissionError(f"Access denied: Path '{rel_path}' escapes workspace boundary.")
    return full_path

def read_file(filepath: str, start_line: int = 1, end_line: int = 500) -> Dict[str, Any]:
    """Reads lines from a file safely within workspace bounds."""
    try:
        path = _resolve_safe_path(filepath)
        if not path.exists() or not path.is_file():
            return {"success": False, "error": f"File '{filepath}' not found."}
            
        content = path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        selected_lines = lines[start_idx:end_idx]
        
        formatted_content = "\n".join([f"{idx+start_idx+1}: {line}" for idx, line in enumerate(selected_lines)])
        return {
            "success": True,
            "filepath": filepath,
            "total_lines": len(lines),
            "showing_lines": f"{start_idx+1}-{end_idx}",
            "content": formatted_content
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def list_files(directory: str = ".") -> Dict[str, Any]:
    """Lists files and directories safely."""
    try:
        path = _resolve_safe_path(directory)
        if not path.exists() or not path.is_dir():
            return {"success": False, "error": f"Directory '{directory}' not found."}
            
        items = []
        for child in path.iterdir():
            if child.name.startswith(".") or child.name in {"__pycache__", "node_modules", "venv"}:
                continue
            items.append({
                "name": child.name,
                "is_dir": child.is_dir(),
                "size": child.stat().st_size if child.is_file() else 0
            })
            
        return {"success": True, "directory": directory, "items": items}
    except Exception as e:
        return {"success": False, "error": str(e)}

def apply_patch(filepath: str, new_content: str) -> Dict[str, Any]:
    """Applies updated content to a file inside workspace bounds."""
    try:
        path = _resolve_safe_path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_content, encoding="utf-8")
        return {
            "success": True,
            "filepath": filepath,
            "bytes_written": len(new_content)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
