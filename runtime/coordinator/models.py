from pydantic import BaseModel
from typing import List, Optional

class WorkflowState(BaseModel):
    objective: Optional[str] = None
    current_phase: Optional[str] = None
    current_focus: Optional[str] = None
    active_skill: Optional[str] = None

class CoordinatorDecision(BaseModel):
    resolved_skill: Optional[str] = None
    suggested_skills: List[str] = []
    workflow_state: WorkflowState
    runtime_context: str
