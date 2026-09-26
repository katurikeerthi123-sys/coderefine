import json
import uuid
import time
from typing import Dict, Any, Optional, List

from app.database import get_db
from app.services.llm_provider import get_llm_provider, LLMProvider
from app.agents.state import AgentTaskState, TaskStatus
from app.agents.planner import AgentPlanner
from app.agents.executor import AgentExecutor
from app.agents.reviewer import AutonomousReviewer

ACTIVE_TASKS: Dict[str, AgentTaskState] = {}

class AgenticEngine:
    """Master orchestrator for Agentic AI Software Engineering Tasks."""

    def __init__(self, user_groq_key: Optional[str] = None, user_gemini_key: Optional[str] = None):
        self.llm: LLMProvider = get_llm_provider(user_groq_key=user_groq_key, user_gemini_key=user_gemini_key)
        self.planner = AgentPlanner(self.llm)
        self.executor = AgentExecutor(self.llm)
        self.reviewer = AutonomousReviewer(self.llm)

    def create_task(self, goal: str, user_id: Optional[int] = None) -> AgentTaskState:
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        state = AgentTaskState(task_id=task_id, goal=goal, user_id=user_id)
        
        # Formulate initial execution plan
        plan_res = self.planner.create_plan(goal)
        state.plan = plan_res.get("plan", [f"Execute user goal: {goal}"])
        
        ACTIVE_TASKS[task_id] = state
        self._persist_task(state)
        return state

    def run_task_steps(self, task_id: str, max_steps: int = 10) -> AgentTaskState:
        state = ACTIVE_TASKS.get(task_id)
        if not state:
            raise KeyError(f"Task '{task_id}' not found in active session.")

        if state.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.AWAITING_APPROVAL, TaskStatus.CANCELLED}:
            return state

        state.status = TaskStatus.EXECUTING
        steps_executed = 0

        while steps_executed < max_steps and state.status == TaskStatus.EXECUTING:
            steps_executed += 1
            step_res = self.executor.execute_next_step(state)
            
            if step_res.get("awaiting_approval"):
                break
                
            if step_res.get("is_final"):
                state.status = TaskStatus.COMPLETED
                break

        self._persist_task(state)
        return state

    def approve_and_resume(self, task_id: str) -> AgentTaskState:
        state = ACTIVE_TASKS.get(task_id)
        if not state:
            raise KeyError(f"Task '{task_id}' not found.")

        if state.status != TaskStatus.AWAITING_APPROVAL or not state.pending_approval:
            raise ValueError(f"Task '{task_id}' is not currently awaiting approval.")

        approval_data = state.pending_approval
        target_file = approval_data["target_file"]
        new_content = approval_data["new_content"]

        # Run Verification & Self-Correction Loop
        state.status = TaskStatus.TESTING
        state.clear_pending_approval()
        
        verify_res = self.reviewer.verify_and_self_correct(state, target_file, new_content)
        
        if verify_res.get("success"):
            state.status = TaskStatus.COMPLETED
            state.add_step(
                action_type="task_completed", 
                thought=f"Patch applied successfully to '{target_file}'. Self-correction verification passed cleanly!"
            )
        else:
            state.status = TaskStatus.FAILED
            state.add_step(
                action_type="task_failed", 
                thought=f"Verification failed after max retries: {verify_res.get('error')}"
            )

        self._persist_task(state)
        return state

    def cancel_task(self, task_id: str) -> AgentTaskState:
        state = ACTIVE_TASKS.get(task_id)
        if not state:
            raise KeyError(f"Task '{task_id}' not found.")

        state.status = TaskStatus.CANCELLED
        state.clear_pending_approval()
        state.add_step(action_type="task_cancelled", thought="Task cancelled by user.")
        self._persist_task(state)
        return state

    def _persist_task(self, state: AgentTaskState):
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO agent_tasks (id, user_id, goal, status, plan_json, summary_text)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    plan_json = excluded.plan_json,
                    summary_text = excluded.summary_text,
                    updated_at = CURRENT_TIMESTAMP;
                """, (
                    state.task_id,
                    state.user_id,
                    state.goal,
                    state.status.value,
                    json.dumps(state.plan),
                    json.dumps(state.steps)
                ))
        except Exception as e:
            print(f"Warning: Failed to persist agent task to DB: {str(e)}")
