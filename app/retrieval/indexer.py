import os
import re
import ast
from pathlib import Path
from typing import List, Dict, Any

from app.config import BASE_DIR

IGNORE_DIRS = {".git", "__pycache__", "venv", ".venv", "node_modules", ".idea", ".vscode", "dist", "build"}
IGNORE_EXTS = {".db", ".pyc", ".png", ".jpg", ".jpeg", ".ico", ".svg", ".zip", ".tar", ".gz"}

class RepositoryIndexer:
    """Scans repository files and extracts structural symbol metadata."""

    def __init__(self, root_dir: Path = BASE_DIR):
        self.root_dir = root_dir.resolve()

    def build_index((self) -> Dict[str, Any]:
        file_tree = []
        symbols = []

        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in IGNORE_EXTS:
                    continue

                full_path = Path(root) / file
                try:
                    rel_path = str(full_path.relative_to(self.root_dir)).replace("\\", "/")
                except ValueError:
                    continue

                file_info = {
                    "rel_path": rel_path,
                    "file_name": file,
                    "ext": ext,
                    "size": full_path.stat().st_size
                }
                file_tree.append(file_info)

                # Extract Python AST symbols if .py file
                if ext == ".py":
                    try:
                        content = full_path.read_text(encoding="utf-8", errors="ignore")
                        tree = ast.parse(content, filename=rel_path)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef):
                                symbols.append({
                                    "name": node.name,
                                    "kind": "function",
                                    "file": rel_path,
                                    "line": node.lineno
                                })
                            elif isinstance(node, ast.ClassDef):
                                symbols.append({
                                    "name": node.name,
                                    "kind": "class",
                                    "file": rel_path,
                                    "line": node.lineno
                                })
                    except Exception:
                        pass

        return {
            "root": str(self.root_dir),
            "total_files": len(file_tree),
            "file_tree": file_tree,
            "symbols": symbols
        }
