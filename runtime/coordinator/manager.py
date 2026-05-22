import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from api.memory_models import MemoryVariable, MemoryTask, MemoryObservation
from runtime.coordinator.models import WorkflowState, CoordinatorDecision
from runtime.coordinator.intent import analyze_intent
from runtime.coordinator.workflow import load_workflow_state, update_workflow, process_task_progression
from runtime.coordinator.suggestions import get_suggested_skills

logger = logging.getLogger("as-code.runtime.coordinator")

class RuntimeCoordinator:
    def __init__(self):
        pass

    def coordinate(
        self,
        db: Session,
        session_id: str,
        user_message: str,
        manual_skill: Optional[str] = None
    ) -> CoordinatorDecision:
        """
        Main coordination loop:
        1. Enforce hard memory limits to prevent bloat.
        2. Auto-progress tasks based on message content.
        3. Analyze user message intent.
        4. Resolve active skill using priority order: manual -> persistent workflow -> inferred.
        5. Update workflow state (transitions phases/focus).
        6. Get suggestions and persist them in variables.
        7. Format system prompt runtime context.
        """
        # 1. Enforce limits first
        self.enforce_memory_limits(db, session_id)

        # 2. Process task progression
        process_task_progression(db, session_id, user_message)

        # 3. Analyze intent for skills
        inferred_skills = analyze_intent(user_message, db, session_id)
        first_inferred = inferred_skills[0] if inferred_skills else None

        # 4. Resolve active skill
        # Priority order:
        #   (a) Manually activated skill (e.g. from header X-Skill)
        #   (b) Persistent workflow skill in Working Memory (wf_skill)
        #   (c) Top inferred skill from user message intent
        current_state = load_workflow_state(db, session_id)
        
        resolved_skill = manual_skill
        if not resolved_skill:
            resolved_skill = current_state.active_skill
        if not resolved_skill:
            resolved_skill = first_inferred

        # 5. Update workflow state transitions
        workflow_state = update_workflow(db, session_id, user_message, resolved_skill)

        # 6. Get suggestions for alternative skills and persist them in memory
        suggested = get_suggested_skills(db, session_id, user_message, workflow_state)
        
        from runtime.memory.manager import WorkingMemoryManager
        mem_mgr = WorkingMemoryManager()
        mem_mgr.set_variable(db, session_id, "wf_suggestions", ",".join(suggested))

        # 7. Generate runtime context block
        runtime_context = self.build_runtime_context_block(workflow_state, resolved_skill)

        return CoordinatorDecision(
            resolved_skill=resolved_skill,
            suggested_skills=suggested,
            workflow_state=workflow_state,
            runtime_context=runtime_context
        )

    def enforce_memory_limits(self, db: Session, session_id: str) -> None:
        """Enforce strict memory limits to avoid DB bloat & token pollution."""
        try:
            # 1. Variables: max 15 (excluding workflow variables wf_*)
            variables = db.query(MemoryVariable).filter_by(session_id=session_id).order_by(MemoryVariable.created_at.asc()).all()
            user_vars = [v for v in variables if not v.key.startswith("wf_")]
            if len(user_vars) > 15:
                excess_count = len(user_vars) - 15
                for i in range(excess_count):
                    logger.info(f"[LIMIT-ENFORCE] Trimming old variable: {user_vars[i].key}")
                    db.delete(user_vars[i])

            # 2. Tasks: max 10
            tasks = db.query(MemoryTask).filter_by(session_id=session_id).order_by(MemoryTask.created_at.asc()).all()
            if len(tasks) > 10:
                excess_count = len(tasks) - 10
                # Try to delete completed/failed tasks first
                completed_tasks = [t for t in tasks if t.status in ["completed", "failed"]]
                pending_tasks = [t for t in tasks if t.status not in ["completed", "failed"]]
                
                deleted_count = 0
                for ct in completed_tasks:
                    if deleted_count < excess_count:
                        db.delete(ct)
                        deleted_count += 1
                
                if deleted_count < excess_count:
                    # Delete oldest pending tasks if still over limit
                    for pt in pending_tasks:
                        if deleted_count < excess_count:
                            db.delete(pt)
                            deleted_count += 1

            # 3. Observations: max 20
            observations = db.query(MemoryObservation).filter_by(session_id=session_id).order_by(MemoryObservation.created_at.asc()).all()
            if len(observations) > 20:
                excess_count = len(observations) - 20
                for i in range(excess_count):
                    db.delete(observations[i])

            db.commit()
        except Exception as e:
            logger.warning(f"Error enforcing memory limits: {e}")

    def build_runtime_context_block(self, state: WorkflowState, active_skill: Optional[str]) -> str:
        """Build the runtime context block to inject into the system prompt."""
        if not state.objective and not state.current_phase and not active_skill:
            return ""

        lines = ["## RUNTIME CONTEXT"]
        if state.objective:
            lines.append(f"Active objective: {state.objective}")
        if state.current_phase:
            lines.append(f"Current phase: {state.current_phase}")
        if state.current_focus:
            lines.append(f"Current focus: {state.current_focus}")
        if active_skill:
            lines.append(f"Active skill: {active_skill}")
        
        return "\n".join(lines).strip()
