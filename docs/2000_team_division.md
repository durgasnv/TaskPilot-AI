# 4-Day Cross-Functional Tactical Sprint Plan

## Team Topology: 5 Members | Fixed Timeline

### 1. Role Definitions

- **Dev 1 (Data Pipeline & Privacy Lead)**: Responsible for mock environment architecture, file parsers, and deterministic PII scrubbing routines.
- **Dev 2 (Agent Architecture Lead)**: Responsible for custom multi-agent pipeline design, ReAct loop control, agent execution policies, and integration of Dev 1 and Dev 3 outputs into the unified pipeline.
- **Dev 3 (Analytics & Math Logic Lead)**: Responsible for Pydantic schema validation, embedding similarity metrics (ChromaDB/FAISS), and LLM prioritization logic.
- **Dev 4 (Interface & Event Lead)**: Responsible for conversation route handling, background file-drop listeners, and push notification triggers.
- **Dev 5 (QA Automation & Release Lead)**: Responsible for regression validation scripts, metrics auditing (deduplication accuracy tracking), and pitch/video delivery.

> **Note:** Framework choice — we did not use CrewAI or LangGraph. We built a lightweight custom agent framework (`TaskPilotGraph` + `WorkflowState`) to avoid external dependencies and maintain full control over the pipeline for demo stability.

---

## 2. Daily Gantt Sequence

### Day 1: Architecture Baseline, Core Schema, & Mock Setups

- **Dev 1**: Build simulated data environment files (Jira JSON, ServiceNow logs, Outlook text logs) mapping out overlapping targets. ✅ Done
- **Dev 2**: Scaffold the repository, initialize the multi-agent pipeline framework, and construct agent memory variables (`WorkflowState`, `WorkflowMemory`, `AgentTrace`). ✅ Done
- **Dev 3**: Draft validation blueprints utilizing Pydantic. Ensure strict formatting rules for all cross-agent transactions. ✅ Done (schemas in `src/taskpilot_ai/unified_task.py`)
- **Dev 4**: Build basic CLI infrastructure to intercept and stream intermediate agent traces. ✅ Covered by Dev 2 (`main.py` trace output)
- **Dev 5**: Code the assessment harness to log execution speeds and parse accuracy baselines against the source mock inputs.

### Day 2: Ingestion Logic, Data Anonymization, & Semantic Extraction

- **Dev 1**: Write regex/token-matching pre-scrubbing routines (phone, email, Aadhaar, credit card, AWS keys) to process text streams before handing them off to the LLM agent. ✅ Done (`src/pipeline/privacy.py`)
- **Dev 2**: Program the Ingestion and Extraction Agent's ReAct loop prompts and associate file-reading tool dependencies. Connect Dev 1's normalizer to the agent pipeline. ✅ Done (`NormalizerSourceReader`, `IngestionAgent`, `ExtractionAgent`)
- **Dev 3**: Spin up an isolated Vector DB instance (ChromaDB/FAISS) to compute similarity metrics and isolate duplicate inputs. ⏳ Pending
- **Dev 4**: Code the core processing system for the conversational framework to route the required five natural language queries. ✅ Covered by Dev 2 (`src/taskpilot_ai/chat.py` — 10 query types)
- **Dev 5**: Run extraction sweeps over noisy text segments to verify text retrieval scores.

### Day 3: Prioritization Calculation Matrix & Event Listeners

- **Dev 1 & Dev 3**: Refine the prioritization agent prompt. Enforce deterministic scoring inputs across variables (deadlines, severities, dependencies). ✅ Covered by Dev 2 (`_score_task()` — 4-factor scoring with plain-English rationale)
- **Dev 2 & Dev 4**: Set up an event polling monitor. Build code to detect a sudden file insertion (simulating a surprise emergency bug) and trigger a state recalculation. ✅ Done (`src/taskpilot_ai/events/monitor.py` + `FileDropMonitor`)
- **Dev 2**: Keyword-based deduplication fallback built as placeholder until Dev 3's vector engine is ready (`_basic_keyword_dedup()`, 65 → 36 tasks). ✅ Done
- **Dev 5**: Validate the system against hallucination bugs by checking output item tags strictly against source context identifiers.

### Day 4: Hardening, Demo Simulation, & Disaster Mitigation

- **All Hands**: Absolute feature freeze at midday.
- **Dev 3**: Replace keyword dedup with ChromaDB/FAISS vector engine. Plug into `DeduplicationAgent(engine=YourEngine())`. ⏳ Pending
- **Dev 4**: Add push notification support (Slack webhook or terminal alert) using the `NotifierProtocol` stub in `src/taskpilot_ai/interfaces/protocols.py`. ⏳ Pending
- **Dev 1, Dev 2, & Dev 3**: Run bug-hunting operations, optimize prompt tokens, and clean code paths.
- **Dev 4 & Dev 5**: Rehearse the live verification workflow script explicitly matching the hackathon criteria.
- **Dev 5**: Capture a local high-definition backup screen recording of the operational execution sequence to protect against network lag or API timeouts.

---

## 3. Current Implementation Status

| Component | Owner | Status | Notes |
| :--- | :--- | :--- | :--- |
| Simulated data (Jira, SN, Email, Meetings) | Dev 1 | ✅ Done | `data/raw/` — 65 tasks across 4 sources |
| PII scrubbing pipeline | Dev 1 | ✅ Done | `src/pipeline/privacy.py` — phone, email, Aadhaar, CC, AWS keys |
| All 4 source parsers | Dev 1 | ✅ Done | `src/parsers/` — jira, servicenow, email, meeting |
| Multi-agent pipeline framework | Dev 2 | ✅ Done | `TaskPilotGraph` + `WorkflowState` — 5 agents |
| Ingestion & extraction agents | Dev 2 | ✅ Done | `IngestionAgent`, `ExtractionAgent` with ReAct prompts |
| Dev 1 ↔ Dev 2 integration | Dev 2 | ✅ Done | `NormalizerSourceReader` bridges both pipelines |
| Adaptive file format handling | Dev 2 | ✅ Done | Handles any JSON/text format dropped at runtime |
| File-drop event monitor | Dev 2 | ✅ Done | `FileDropMonitor` — watches `data/injected/`, triggers re-run |
| Priority scoring (4-factor) | Dev 2 | ✅ Done | `_score_task()` — severity + deadline + blocks + impact |
| Keyword deduplication (fallback) | Dev 2 | ✅ Done | `_basic_keyword_dedup()` — 65 → 36 tasks |
| Conversational interface | Dev 2 | ✅ Done | `chat.py` — 10 NL query types, `--chat` mode |
| Daily plan generation | Dev 2 | ✅ Done | `PlanningAgent` — sorted, severity-labelled plan |
| Pydantic schemas | Dev 3 | ✅ Done | `UnifiedTask`, `WorkflowState`, protocol interfaces |
| Vector deduplication (ChromaDB/FAISS) | Dev 3 | ⏳ Pending | `VectorDeduplicatorProtocol` slot ready in `DeduplicationAgent` |
| Push notifications | Dev 4 | ⏳ Pending | `NotifierProtocol` stub ready in `interfaces/protocols.py` |
| QA regression suite | Dev 5 | ⏳ Pending | 25 tests passing; full audit coverage needed |
| Demo script & backup recording | Dev 5 | ⏳ Pending | — |

---

## 4. Integration Points for Dev 3 and Dev 4

**Dev 3 — plug in vector deduplication:**
```python
# In src/taskpilot_ai/main.py, swap:
DeduplicationAgent()
# for:
DeduplicationAgent(engine=YourChromaDBEngine())
```
Implement `VectorDeduplicatorProtocol` from `src/taskpilot_ai/interfaces/protocols.py`.

**Dev 4 — plug in push notifications:**
```python
# NotifierProtocol is already defined in interfaces/protocols.py
# Implement it and wire it into the emergency re-run path in events/monitor.py
```
The `FileDropMonitor` already detects new P1 files and triggers re-ranking — Dev 4 just needs to add the notification call after re-rank completes.