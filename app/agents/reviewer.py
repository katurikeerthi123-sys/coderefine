from typing import Dict, Any, Optional

from app.services.llm_provider import LLMProvider
from app.agents.state import AgentTaskState
from app.agents.tools.testing import run_syntax_check, run_tests, save_generated_test
from app.agents.tools.filesystem import apply_patch
from app.agents.prompts import REVIEWER_SELF_CORRECT_PROMPT, TEST_GENERATOR_PROMPT

class AutonomousReviewer:
    """Manages test generation, verification, and autonomous self-correction loops."""

    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    def generate_tests_for_file(self, filepath: str, file_content: str) -> Dict[str, Any]:
        """Generates a pytest/unittest suite for a target codebase file."""
        default_name = filepath.replace("/", "_").replace("\\", "_").replace(".py", "")
        prompt = TEST_GENERATOR_PROMPT.format(
            filepath=filepath,
            file_content=file_content[:3000],
            default_name=default_name
        )
        schema_desc = """
        {
          "test_filename": "test_example.py",
          "test_code": "import unittest\\n..."
        }
        """
        try:
            res = self.llm.generate_structured_output(prompt=prompt, schema_desc=schema_desc)
            filename = res.get("test_filename", f"test_{default_name}.py")
            code = res.get("test_code", "")
            if code:
                save_res = save_generated_test(filename, code)
                return save_res
            return {"success": False, "error": "LLM returned empty test code."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def verify_and_self_correct(
        self, 
        state: AgentTaskState, 
        target_file: str, 
        new_content: str
    ) -> Dict[str, Any]:
        """
        Applies proposed content, runs syntax check & tests, and self-corrects up to 3 times.
        """
        current_content = new_content
        attempt = 0
        max_attempts = state.max_retries

        while attempt < max_attempts:
            attempt += 1
            state.add_step(
                action_type="verification_attempt", 
                thought=f"Verification attempt {attempt}/{max_attempts} for '{target_file}'."
            )

            # 1. Apply patch temporarily to workspace
            apply_res = apply_patch(target_file, current_content)
            if not apply_res.get("success"):
                return {"success": False, "error": f"Failed to apply patch: {apply_res.get('error')}"}

            # 2. Run Python Syntax compilation check
            syntax_res = run_syntax_check(target_file)
            if not syntax_res.get("clean", True):
                error_log = syntax_res.get("error", "Syntax Compilation Error")
                state.add_step(action_type="syntax_failure", thought=f"Syntax check failed: {error_log}")
                
                # Request LLM self-correction
                current_content = self._request_self_correction(target_file, error_log, current_content)
                continue

            # 3. Run automated tests
            test_res = run_tests()
            if test_res.get("tests_passed", True):
                state.add_step(
                    action_type="verification_success", 
                    thought=f"Verification PASSED on attempt {attempt}!"
                )
                return {
                    "success": True,
                    "attempts": attempt,
                    "final_content": current_content,
                    "test_output": test_res.get("output", "Clean execution")
                }
            else:
                error_log = test_res.get("output", "Test suite execution failed.")
                state.add_step(action_type="test_failure", thought=f"Test failure detected: {error_log[:200]}")
                
                # Request LLM self-correction
                current_content = self._request_self_correction(target_file, error_log, current_content)

        return {
            "success": False,
            "error": f"Failed to self-correct after {max_attempts} verification attempts.",
            "last_content": current_content
        }

    def _request_self_correction(self, target_file: str, error_log: str, current_content: str) -> str:
        prompt = REVIEWER_SELF_CORRECT_PROMPT.format(
            target_file=target_file,
            error_output=error_log[:2000]
        )
        schema_desc = """
        {
          "diagnosis": "Syntax/Logic error explanation",
          "corrected_code": "# Corrected file content..."
        }
        """
        try:
            res = self.llm.generate_structured_output(prompt=prompt, schema_desc=schema_desc)
            corrected = res.get("corrected_code", "").strip()
            if corrected:
                return corrected
        except Exception:
            pass
        return current_content
