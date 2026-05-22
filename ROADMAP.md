# ROADMAP

AS Code is evolving from a local chat server into a **Unified Smart Main Agent Runtime** (Offline-first, modular, and extensible alternative to Claude Code, Cursor, and NotebookLM).

---

## ✅ Phase 1 — Core Runtime, RAG & Skills (Completed)

*   **LiteRT-LM Windows Runtime:** GPU-accelerated local inference utilizing Gemma 3.
*   **Smart Routing:** Multi-role orchestration (Chat, Code, Reasoning).
*   **SSE Streaming & OpenAI API:** Drop-in compatibility for client tools (Cline, Continue, etc.).
*   **Hardware-Adaptive Profiles:** Auto-tuning of parameters based on VRAM/CPU capability.
*   **NotebookLM RAG Pipeline (RAG v2):**
    *   Direct RAG ingest via `/api/rag/documents/upload`.
    *   Local embeddings (`BAAI/bge-small-en-v1.5`) + FAISS index + SQLite metadata.
    *   AST parsing for Python (.py), heading hierarchy for markdown, and structure-agnostic adaptive semantic segmenting (paragraph → sentence → char fallback) for PDFs, Word documents, and text.
    *   Hybrid retrieval: `alpha * semantic + (1 - alpha) * keyword (BM25)`.
    *   Structured context composition (`NotebookContextBuilder`) with `normal`, `thinking`, and `code` modes.
*   **Runtime Capability Registry:** Dynamic discovery of environment primitives (Git, Terminal, Documents, RAG).
*   **Skill Runtime v1:** Discoverable JSON manifests and dynamic system prompt injection framework.

---

## ✅ Phase 2 — Working Memory Layer (Completed)

A structured short-term cognitive scratchpad to keep track of agent goals, variables, and observations, fully isolated by session.

*   **Session Isolation:** Explicit `session_id` on all memory tables for future-proof multi-chat / VSCode tab isolation.
*   **Runtime-Native Protocol:** Simple endpoints (`/v1/memory/*`) for CRUD operations on variables, tasks, and observations.
*   **Task Management:** Priority-aware task list (P0, P1...) allowing the agent to sort objectives.
*   **Fact Tracking (Observations):** Observation logs categorized by source (`user`, `system`, `rag`, `capability`) for explanation and debugging.
*   **System Prompt Injection:** Injects formatted memory state directly into the system context in the correct cognitive order: `base_prompt` → `skill_prompt` → `Working Memory` → `RAG Context` (user message) → `History` → `User Message`.
*   **Event-Driven UI:** Collapsible Memory Drawer showing real-time state, updating only on interactions to save resources.

---

## ✅ Phase 3 — Smart Main Agent Foundation & Runtime Coordinator (Completed)

Developing the coordinator, deterministic state machines, task auto-progression, and recommended skills engine.

*   **Runtime Coordinator Manager:** Central orchestrator managing cognitive limits (15 vars, 10 tasks, 20 observations) to prevent token pollution.
*   **Workflow State Machine:** Deterministic transition tracker (`wf_objective`, `wf_phase`, `wf_focus`) with automatic task progression based on user intent.
*   **Skill Recommendation Engine:** Suggestions for switching/activating compatible runtime skills based on intent and phase.
*   **Unified UI Integration:** Beautiful Workflow Header badge, active Phase pill, Current Focus info, and clickable Suggested Skill chips.

---

## 🚧 Phase 3.5 — Agent Control Loop & Native Call Parser (Current Focus)

Developing the decision-making loop and output syntax parsing to allow the unified model to orchestrate its own actions.

*   **Native Protocol Parser:** Stream-aware XML or JSON tag listener detecting capability execution requests (e.g. `{"capability": "git", "action": "status", "params": {}}`).
*   **Server-Side Agent Loop:** Intercepting capability calls, suspending generation, executing the action, and feeding outputs back into the chat loop.
*   **Cognitive Prompt Tuning:** Formatting base instructions to guide the model on when to write to memory and when to call tools.

---

## 🔮 Phase 4 — Capability Execution (using `capability.execute()`)

Activating capabilities by providing execution primitives directly within capability classes.

*   **Base Interface Extension:** Adding an async `execute(action, params)` method to `BaseCapability`.
*   **Local Terminal Command Runner:** Running shell processes safely, handling outputs, timeouts, and return codes.
*   **Local Git Interface:** wrapper to fetch diffs, checkout branches, and stage commits.
*   **Scope Security Boundaries:** Enforcing permission boundaries before letting a skill invoke a capability.

---

## 🔮 Phase 5 — Human-in-the-Loop (HITL) Queue

Adding user confirmation gates for high-impact or destructive operations.

*   **Suspended Execution Queue:** FastAPI state queue keeping pending commands.
*   **HITL API Endpoints:** Endpoints `/v1/capabilities/pending` and `/v1/capabilities/confirm`.
*   **Interactive UI Modal:** Consent dialog inside the browser UI to allow the user to modify or approve commands.

---

## 🔮 Phase 6 — IDE / VSCode Integration

Exposing the Unified Agent Runtime to external developer editors.

*   **Workspace Sync API:** Syncing working folders, cursor positions, and open file buffers.
*   **Cline / Continue Adapters:** Formatting local routes to act as custom providers for standard extensions.

---

## 🔮 Phase 7 — Enterprise, Workspace & Multi-Tenant (Long term)

*   **Sidebar Conversation History:** Navigation list, conversation naming, and database persistence.
*   **Secure Authentication:** Secure logins, password hashing (bcrypt), JWT tokens, and user database isolation.
*   **Production Scaling:** PostgreSQL database support and distributed multi-GPU worker pools.
