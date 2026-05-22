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

class RuntimeContract(BaseModel):
    request_id: str
    session_id: str
    model_id: str
    user_message: str
    previous_user_message: Optional[str] = None
    manual_skill: Optional[str] = None
    preset_name: Optional[str] = None
    timestamp: float

class RAGHitMetadata(BaseModel):
    document_id: int
    filename: str
    section: Optional[str] = None
    score: float

class ContextManifest(BaseModel):
    contract_id: str
    active_skill: Optional[str] = None
    workflow_state: WorkflowState
    suggested_skills: List[str] = []
    
    # RAG metadata (sin contenido de texto gigante)
    rag_enabled: bool
    rag_query: Optional[str] = None
    rag_hits: List[RAGHitMetadata] = []
    
    # Conteos de Working Memory
    memory_variables_count: int = 0
    memory_tasks_count: int = 0
    memory_observations_count: int = 0
    
    # Presupuesto físico del prompt (caracteres)
    char_budget: int = 16000
    char_count: int = 0
    
    # Prompt compilado definitivo
    system_prompt_snapshot: str


