import json
from typing import Dict, Any, Optional

from app.services.llm_provider import LLMProvider
from app.agents.state import AgentTaskState, TaskStatus
from app.agents.tools.registry import execute_tool, get_available_tools_schema, RISKY_TOOLS
from app.agents.tools.filesystem import read_file
from app.agents.prompts import EXECUTOR_SYSTEM_PROMPT

class AgentExecutor:
    """Executes single steps in the agent workflow."""

    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    def execute_next_step(self, state: AgentTaskState) -> Dict[str, Any]:
        tools_schema = get_available_tools_schema()
        system_prompt = EXECUTOR_SYSTEM_PROMPT.format(tools_schema=tools_schema)

        prompt = (
            f"User Goal: {state.goal}\n"
            f"Current Plan:\n" + "\n".join([f"- {p}" for p in state.plan]) + "\n\n"
            f"Executed Steps History ({len(state.steps)} steps):\n"
            + json.dumps(state.steps[-5:], indent=2) + "\n\n"
            f"Select the next action or tool to execute."
        )

        schema_desc = """
        {
          "thought": "I need to inspect app/main.py first",
          "tool": "read_file",
          "args": {"filepath": "app/main.py", "start_line": 1, "end_line": 200},
          "is_final": false,
          "final_summary": ""
        }
        """

        try:
            action = self.llm.generate_structured_output(
                prompt=prompt,
                schema_desc=schema_desc,
                system_prompt=system_prompt
            )
        except Exception as e:
            action = {
                "thought": f"Encountered step reasoning error: {str(e)}",
                "tool": "list_files",
                "args": {"directory": "."},
                "is_final": False,
                "final_summary": ""
            }

        thought = action.get("thought", "")
        tool_name = action.get("tool")
        args = action.get("args", {})
        is_final = action.get("is_final", False)
        final_summary = action.get("final_summary", "")

        state.add_step(action_type=tool_name or "final_response", thought=thought)

        if is_final or not tool_name:
            state.status = TaskStatus.COMPLETED
            return {
                "is_final": True,
                "summary": final_summary or thought
            }

        # Check if action requires Human Approval Gate
        if tool_name in RISKY_TOOLS:
            target_file = args.get("filepath", "workspace_file.py")
            new_content = args.get("new_content", "")
            
            # Generate unified diff preview
            old_file_res = read_file(target_file)
            old_content = old_file_res.get("content", "") if old_file_res.get("success") else ""
            patch_diff = f"--- {target_file} (current)\n+++ {target_file} (proposed)\n@@ -1 +1 @@\n"
            
            state.set_pending_approval(
                action_summary=f"Apply code patch to '{target_file}'",
                target_file=target_file,
                new_content=new_content,
                patch_diff=patch_diff
            )
            return {
                "is_final": False,
                "awaiting_approval": True,
                "approval": state.pending_approval
            }

        # Execute safe tool
        tool_res = execute_tool(tool_name, args)
        state.record_tool_call(
            tool_name=tool_name,
            input_params=args,
            output=tool_res.get("result", {}),
            duration_ms=tool_res.get("duration_ms", 0)
        )

        return {
            "is_final": False,
            "awaiting_approval": False,
            "tool_result": tool_res
        }
