# FinSentinel AI — Agent Constitution

## What this project is
A multi-agent financial operations platform. The core is a fraud/anomaly
investigation system for transaction ledgers. A natural-language SQL agent
and an executive reporting agent support it — they are NOT independent
features; they exist to enrich and deliver the investigation agent's output.

## Non-negotiable architecture rules
1. Orchestration: LangGraph ONLY. Do not import, suggest, or scaffold CrewAI,
   AutoGen, or any other agent framework. All multi-step agent logic is a
   LangGraph StateGraph.
2. Every high-risk action (flagging a transaction above a configurable dollar
   threshold, closing an investigation, any credit-related output) MUST pause
   on a LangGraph `interrupt()` call and resume only via `Command(resume=...)`.
   No silent autonomous decisions on high-risk actions, ever.
3. Checkpointing uses `PostgresSaver` in every environment beyond local
   scratch testing. `MemorySaver` is allowed only for the first throwaway
   test of a new node — never commit code that defaults to it.
4. Every LLM call, every generated SQL query, every tool invocation is
   written to the `audit_log` table before its result is used. No exceptions,
   no "we'll add logging later."
5. Data layer: DuckDB for ingesting and cleaning uploaded CSV/XLSX files
   in-memory. PostgreSQL (with the pgvector extension enabled) for
   persistent storage, the audit log, and case-similarity embeddings.
6. The Credit Risk module (if built) never outputs an autonomous
   approve/deny decision. It surfaces ratios and risk factors for a human
   underwriter. Enforce this in code, not just in the prompt — the function
   signature should make an autonomous decision impossible to return.

## Tech stack (do not substitute without being asked)
- Backend: Python, FastAPI
- Orchestration: LangGraph (StateGraph, interrupt/Command, PostgresSaver)
- Data: DuckDB (ingestion), PostgreSQL + pgvector (persistence, embeddings)
- Frontend: Next.js, Tailwind CSS, Recharts
- LLM: Groq (Llama) for fast/cheap first-pass calls, OpenAI API for the
  deeper investigation reasoning calls — see the tiered-routing rule below
- Documents: python-pptx, openpyxl

## Cost/latency discipline
Never route every transaction through an expensive LLM call. Rule-based and
statistical checks (Z-score, Bloom filter, Count-Min Sketch) run first and
are nearly free. These act purely as a **statistical classifier** to assign a
risk threshold and fast-screen signals. 
Only transactions that cross an ambiguity threshold escalate to an LLM call.
The actual reasoning step inside `investigate_node` is powered by a local 
Ollama endpoint (e.g., `phi4-mini` or `qwen3:8b`), using the structured 
signals from the classifier to synthesize the final execution trace. Embeddings
are generated locally using `nomic-embed-text`.

## Verification standard
Before marking any milestone done: if a test suite doesn't exist for the
code you just touched, write one first, then implement against it, then run
it and show me the output. Don't ask me to trust a diff I haven't seen pass
a test.

## Working style
Use Planning Mode for anything touching the LangGraph graph, the audit log,
or the HITL flow — I want to review the implementation plan before code gets
written. Fast Mode is fine for boilerplate: scaffolding, config files,
straightforward CRUD endpoints, styling.