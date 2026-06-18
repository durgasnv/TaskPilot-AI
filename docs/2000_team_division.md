# 4-Day Cross-Functional Tactical Sprint Plan

## Team Topology: 5 Members | Fixed Timeline

### 1. Role Definitions

- **Dev 1 (Data Pipeline & Privacy Lead)**: Responsible for mock environment architecture, file parsers, and deterministic PII scrubbing routines.
- **Dev 2 (Agent Architecture Lead)**: Responsible for CrewAI/LangGraph state design, ReAct loop control, and agent execution policies.
- **Dev 3 (Analytics & Math Logic Lead)**: Responsible for Pydantic schema validation, embedding similarity metrics, and LLM prioritization logic.
- **Dev 4 (Interface & Event Lead)**: Responsible for conversation route handling, background file-drop listeners, and push notification triggers.
- **Dev 5 (QA Automation & Release Lead)**: Responsible for regression validation scripts, metrics auditing (deduplication accuracy tracking), and pitch/video delivery.

---

## 2. Daily Gantt Sequence

### Day 1: Architecture Baseline, Core Schema, & Mock Setups

- **Dev 1**: Build simulated data environment files (Jira JSON, ServiceNow logs, Outlook text logs) mapping out overlapping targets.
- **Dev 2**: Scaffold the repository, initialize the multi-agent topology framework (CrewAI/LangGraph), and construct agent memory variables.
- **Dev 3**: Draft validation blueprints utilizing Pydantic. Ensure strict formatting rules for all cross-agent transactions.
- **Dev 4**: Build basic CLI infrastructure or Slack webhook routes to intercept and stream intermediate LLM token traces.
- **Dev 5**: Code the assessment harness to log execution speeds and parse accuracy baselines against the source mock inputs.

### Day 2: Ingestion Logic, Data Anonymization, & Semantic Extraction

- **Dev 1**: Write regex/token-matching pre-scrubbing routines to process text streams before handing them off to the LLM agent.
- **Dev 2**: Program the Ingestion and Extraction Agent's ReAct loop prompts and associate file-reading tool dependencies.
- **Dev 3**: Spin up an isolated Vector DB instance (ChromaDB/FAISS) to compute similarity metrics and isolate duplicate inputs.
- **Dev 4**: Code the core processing system for the conversational framework to route the required five natural language queries.
- **Dev 5**: Run extraction sweeps over noisy text segments to verify text retrieval scores.

### Day 3: Prioritization Calculation Matrix & Event Listeners

- **Dev 1 & Dev 3**: Refine the prioritization agent prompt. Enforce deterministic scoring inputs across variables (deadlines, severities, dependencies).
- **Dev 2 & Dev 4**: Set up an event polling monitor. Build code to detect a sudden file insertion (simulating a surprise emergency bug) and trigger a state recalculation.
- **Dev 5**: Validate the system against hallucination bugs by checking output item tags strictly against source context identifiers.

### Day 4: Hardening, Demo Simulation, & Disaster Mitigation

- **All Hands**: Absolute feature freeze at midday.
- **Dev 1, Dev 2, & Dev 3**: Run bug-hunting operations, optimize prompt tokens, and clean code paths.
- **Dev 4 & Dev 5**: Rehearse the live verification workflow script explicitly matching the hackathon criteria.
- **Dev 5**: Capture a local high-definition backup screen recording of the operational execution sequence to protect against network lag or API timeouts.