from typing import Dict, Any, List
from app.services.llm_provider import LLMProvider
from app.retrieval.indexer import RepositoryIndexer
from app.retrieval.search import CodeSearchEngine
from app.agents.prompts import PLANNER_SYSTEM_PROMPT

class AgentPlanner:
    """Decomposes user goals into actionable step-by-step plans."""

    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider
        self.indexer = RepositoryIndexer()
        self.search = CodeSearchEngine()

    def create_plan(self, goal: str) -> Dict[str, Any]:
        # Index repository to provide high-level tree context
        index = self.indexer.build_index()
        file_tree_summary = [f["rel_path"] for f in index.get("file_tree", [])[:30]]
        
        # Search for key terms in goal
        relevant_matches = self.search.search_code(goal[:20], max_results=5)
        
        prompt = (
            f"User Goal: {goal}\n\n"
            f"Repository Files ({len(file_tree_summary)} available):\n"
            + "\n".join(file_tree_summary) + "\n\n"
            f"Relevant Code Matches:\n"
            + str(relevant_matches)
        )
        
        schema_desc = """
        {
          "plan": [
            "Step 1: Inspect target files and locate bug",
            "Step 2: Generate/run test suite",
            "Step 3: Create and apply patch",
            "Step 4: Verify test execution and self-correct if needed"
          ],
          "initial_file_to_inspect": "app/main.py"
        }
        """
        
        try:
            result = self.llm.generate_structured_output(
                prompt=prompt,
                schema_desc=schema_desc,
                system_prompt=PLANNER_SYSTEM_PROMPT
            )
            return result
        except Exception as e:
            # Clean fallback plan if model call fails
            return {
                "plan": [
                    f"1. Search codebase for context regarding: {goal}",
                    "2. Read target file and identify required changes",
                    "3. Generate unit tests and verify execution",
                    "4. Apply patch and verify self-correction loop"
                ],
                "initial_file_to_inspect": None
            }
