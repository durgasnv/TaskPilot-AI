# Product Requirement Document (PRD): TaskPilot AI
## Target System Profile: Autonomous Task Intelligence Agent

### 1. Context & Constraints
- **Core Objective**: Deploy a personal AI Agent for software engineers to conquer task overload and context fragmentation.
- **Anti-Patterns (Strict Rules)**: Must NOT be built as a static dashboard or standard chatbot. It must operate autonomously via event loops or state triggers.
- **Privacy Paradigm**: Principle of Least Privilege (PoLP). Raw data streams must be localized or scrubbed of Personally Identifiable Information (PII) prior to LLM interaction.

### 2. Functional Requirements

#### 2.1 Multi-Source Ingestion & Scrubbing
- **Silos**: Ingest from minimum 3 simulated heterogeneous sources (Jira Scrum board, ServiceNow defect tracker, Outlook email inbox, and meeting transcripts).
- **Data Guard**: A deterministic pre-processing script must filter out structural PII (e.g., telephone numbers, personal messages) to isolate work telemetry.

#### 2.2 Extraction & Semantic Deduplication
- **Unstructured Parsing**: Extract hidden action items from unstructured text (emails, transcripts) using structured LLM outputs.
- **Deduplication Engine**: Compute embedding vectors on tasks. Merge cross-system tasks pointing to identical issues if semantic similarity exceeds an 85% threshold (e.g., matching a customer email escalation to a live Jira ID). Target accuracy: >= 90%.

#### 2.3 Multi-Factor Prioritization Engine
- **Formula Matrix**: Compute absolute priority metrics dynamically rather than relying on local urgency.
- **Variables**: Inputs must factor in Proximity of Deadline, Severity (SLA impact), and Dependency Graphs (blocking links).
- **Auditable Explainability**: Every ranking calculation must output an explicit, logical justification string.Black-box ranking is blocked.

#### 2.4 Interface & Proactive Orchestration
- **Workspace Generation**: Automatically compile a structured, clean daily TODO plan.
- **Proactive Alerting**: The system must run background polls. If an overnight or mid-day P1 issue hits the dataset, the agent must instantly calculate its impact, alter the current execution sequence, and push a critical notification.
- **Conversational Queries**: Support natural language interrogation supporting at least 5 variants (e.g., "Why is task X ranked #1?", "Summarize the VP's email thread").

### 3. Verification & Acceptance Criteria
- [cite_start]**Performance**: End-to-end plan generation lifecycle must execute under 30-60 seconds.
- [cite_start]**Demo Proof Sequence**: Ingest $\rightarrow$ Extract $\rightarrow$ Deduplicate $\rightarrow$ Prioritize (Top 3 with Rationale) $\rightarrow$ Daily Plan Display $\rightarrow$ Conversational Query $\rightarrow$ Mid-demo Injection of a P1 Emergency (Dynamic Re-prioritization verification).