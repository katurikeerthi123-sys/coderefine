import os
import re
from pathlib import Path
from typing import List, Dict, Any

from app.config import BASE_DIR
from app.retrieval.indexer import RepositoryIndexer, IGNORE_DIRS, IGNORE_EXTS

class CodeSearchEngine:
    """Executes lexical search and symbol matching across multi-file codebase."""

    def __init__(self, root_dir: Path = BASE_DIR):
        self.root_dir = root_dir.resolve()
        self.indexer = RepositoryIndexer(self.root_dir)

    def search_code(self, query: str, max_results: int = 15) -> List[Dict[str, Any]]:
        results = []
        pattern = re.compile(re.escape(query), re.IGNORECASE)

        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in IGNORE_EXTS:
                    continue

                full_path = Path(root) / file
                try:
                    rel_path = str(full_path.relative_to(self.root_dir)).replace("\\", "/")
                    content = full_path.read_text(encoding="utf-8", errors="ignore")
                    
                    for idx, line in enumerate(content.splitlines(), start=1):
                        if pattern.search(line):
                            results.append({
                                "file": rel_path,
                                "line_number": idx,
                                "line_content": line.strip()
                            })
                            if len(results) >= max_results:
                                return results
                except Exception:
                    continue

        return results

    def find_symbol(self, symbol_name: str) -> List[Dict[str, Any]]:
        index = self.indexer.build_index()
        symbols = index.get("symbols", [])
        return [s for s in symbols if s["name"].lower() == symbol_name.lower()]

    def assemble_context(self, file_paths: List[str], max_chars_per_file: int = 3000) -> str:
        context_blocks = []
        for rel_path in file_paths:
            full_path = self.root_dir / rel_path
            if full_path.exists() and full_path.is_file():
                try:
                    content = full_path.read_text(encoding="utf-8", errors="ignore")
                    snippet = content[:max_chars_per_file]
                    context_blocks.append(f"--- FILE: {rel_path} ---\n{snippet}")
                except Exception:
                    continue
        return "\n\n".join(context_blocks)
