import time
from enum import Enum
from typing import Dict, Any, List, Optional

class TaskStatus(str, Enum):
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AgentTaskState:
    """In-memory and persisted state container for an active Agent task."""

    def __init__(self, task_id: str, goal: str, user_id: Optional[int] = None):
        self.task_id = task_id
        self.user_id = user_id
        self.goal = goal
        self.status = TaskStatus.PLANNING
        self.plan: List[str] = []
        self.steps: List[Dict[str, Any]] = []
        self.tool_calls: List[Dict[str, Any]] = []
        self.pending_approval: Optional[Dict[str, Any]] = None
        self.patches: List[Dict[str, Any]] = []
        self.retry_count: int = 0
        self.max_retries: int = 3
        self.max_steps: int = 15
        self.start_time: float = time.time()

    def add_step(self, action_type: str, thought: str):
        step_index = len(self.steps) + 1
        step_data = {
            "step_index": step_index,
            "action_type": action_type,
            "thought": thought,
            "timestamp": time.time()
        }
        self.steps.append(step_data)
        return step_data

    def record_tool_call(self, tool_name: str, input_params: dict, output: dict, duration_ms: int):
        self.tool_calls.append({
            "step_index": len(self.steps),
            "tool_name": tool_name,
            "input": input_params,
            "output": output,
            "duration_ms": duration_ms
        })

    def set_pending_approval(self, action_summary: str, target_file: str, new_content: str, patch_diff: str):
        self.status = TaskStatus.AWAITING_APPROVAL
        self.pending_approval = {
            "task_id": self.task_id,
            "action_summary": action_summary,
            "target_file": target_file,
            "new_content": new_content,
            "patch_diff": patch_diff
        }

    def clear_pending_approval(self):
        self.pending_approval = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "goal": self.goal,
            "status": self.status.value,
            "plan": self.plan,
            "steps_count": len(self.steps),
            "steps": self.steps,
            "tool_calls": self.tool_calls,
            "pending_approval": self.pending_approval,
            "retry_count": self.retry_count,
            "duration_seconds": round(time.time() - self.start_time, 2)
        }
