# Hackathon Problem Statement Template

## 1. Problem Title
**TaskPilot AI — Build an Agentic AI Assistant That Conquers Engineer Task Overload**

## 2. Background / Context
Modern software engineers are drowning — not in code, but in context fragmentation. Work arrives from Scrum boards, defect trackers, emails, Slack threads, meeting notes, and ad-hoc requests. There is no single pane of glass. Prioritization is gut driven. Critical tasks slip through the cracks.

### The Scale of the Problem

| Pain Point | Impact | Data (Available through some sources) |
| :--- | :--- | :--- |
| **Source Fragmentation** | Engineers juggle 4-7 different tools daily (Jira, GitHub Issues, Outlook, Slack, Confluence, ServiceNow, etc.) | 73% of engineers report tool fatigue (Stack Overflow 2024 Survey) |
| **Context Switching Tax** | Every context switch costs 23 minutes to regain deep focus (UC Irvine research) | Engineers lose ~2.1 hours/day to switching |
| **Invisible Task Debt** | Emails and chat messages contain hidden action items that never make it to a tracker | ~35% of tasks are “off-the-books” and untracked |
| **Priority Blindness** | Without holistic visibility, engineers optimize locally (what’s loudest) instead of globally (what matters most) | ~40% of sprint tasks are reprioritized mid-sprint |
| **Summarization Burden** | Engineers manually read, triage, and summarize dozens of email threads and meeting transcripts daily | 45+ minutes/day spent on email triage alone |

## 3. Problem Description (The Core Problem)
Engineers often struggle with task overload and fragmentation across multiple sources of work. There is no unified view of tasks across systems (Agile boards, Outlook, defect trackers). Engineers spend valuable time switching contexts instead of focusing on execution. Prioritization is subjective and inconsistent, causing delays in critical work. There is also a pervasive lack of summarization from the large volume of asks and actions sent via emails and meeting notes.

Deploy a personal AI Agent for each software engineer that autonomously aggregates tasks from multiple heterogeneous sources (Scrum boards, defect trackers, email inboxes, meeting transcripts), deduplicates and correlates related work, intelligently prioritizes based on multi-dimensional criteria, and delivers a dynamic, actionable daily/weekly task plan through a conversational interface.

### Core Challenges to Address:
* **No unified view:** Tasks are scattered across Jira, ServiceNow, Outlook, Slack, and GitHub. The engineer has no single pane of glass.
* **Hidden action items:** Emails and meeting transcripts contain buried tasks that never reach any tracker. ~35% of work is invisible.
* **Subjective prioritization:** Without holistic visibility, engineers optimize for what is loudest (latest Slack message) rather than what is most important (P1 defect with SLA expiring).
* **Manual summarization overhead:** Engineers spend 45+ minutes daily reading, triaging, and mentally consolidating information across tools.
* **Missed commitments:** Untracked work and poor prioritization lead to 28% of sprint commitments being missed.

## 4. Objectives / Desired Outcomes

### Primary Objective:
Design and build an AI Agent (**TaskPilot AI**) that serves as a personal task intelligence assistant for a software engineer, capable of:
1. Autonomously aggregating tasks from heterogeneous sources (Scrum boards, defect trackers, email inboxes, meeting transcripts)
2. Extracting actionable items from unstructured communications (emails, meeting notes)
3. Deduplicating and correlating related work across systems
4. Intelligently prioritizing based on multi-dimensional criteria (deadlines, dependencies, business impact)
5. Presenting a dynamic, adaptive task plan through a conversational and proactive interface.

### Desired Outcomes

| Outcome | Description |
| :--- | :--- |
| **Unified Task View** | All tasks from all sources consolidated into a single, deduplicated list |
| **Zero Hidden Tasks** | Action items automatically extracted from emails and meeting notes — nothing falls through the cracks |
| **Explainable Prioritization** | Every task ranked with clear, auditable rationale the engineer can trust |
| **Daily/Weekly Plans** | Structured, actionable plans generated automatically each morning |
| **Proactive Alerts** | Agent notifies engineers of new urgent items, approaching deadlines, and blocked teammates without being asked |
| **Natural Language Interaction** | Engineers can ask questions, request summaries, and get context through conversation |
| **Reduced Overhead** | Engineer saves 45+ minutes/day previously spent on manual task triage and context switching |

### Workflow Transformation
* **Before:** Engineer manually checks 5+ tools, mentally tracks priorities, misses a P1 defect buried in email, sprint commitment slips, manager escalation at standup.
* **After:** TaskPilot Agent autonomously scans all sources, extracts 3 hidden action items from emails, detects P1 defect correlates with Jira story, generates prioritized daily plan, alerts engineer: *“Your top 3 for today, with rationale,”* and tracks progress through the day.

## 5. Scope Definition

### In Scope (Must-Have — MVP required for submission)

| Requirement | Description |
| :--- | :--- |
| **Multi-source ingestion** | Ingest tasks from at least 3 different simulated sources (e.g., Jira-like board, email inbox, defect tracker) |
| **Unstructured text parsing** | Use LLM to extract action items from at least email-format unstructured text |
| **Task deduplication** | Detect and merge semantically similar tasks across sources |
| **Intelligent prioritization** | Rank tasks using at least 3 factors (deadline, severity, dependencies) with explainable output |
| **Daily plan generation** | Generate a structured daily TODO with priority ordering |
| **Conversational interface** | Support at least 5 natural language queries (e.g., “What’s my top priority?”, “Summarize my emails”) |
| **Agentic behavior** | Agent must demonstrate autonomous reasoning — not just respond to prompts, but proactively process and organize information |

### In Scope (Should-Have — Differentiators)

| Requirement | Description |
| :--- | :--- |
| **Weekly summary generation** | Produce a rollup summary suitable for standup or status reports |
| **Dynamic re-prioritization** | Re-rank plan when new high-priority tasks are detected |
| **Dependency graph awareness** | Identify blocking/blocked relationships and factor into prioritization |
| **Proactive alerting** | Detect and notify on urgent new items without user prompting |
| **Meeting notes parsing** | Extract action items from meeting transcript text |

### In Scope (Could-Have — Bonus Differentiators)

| Requirement | Description |
| :--- | :--- |
| **Multi-agent architecture** | Implement as a team of specialized agents (e.g., Email Agent, Jira Agent, Prioritization Agent) |
| **Memory and learning** | Agent remembers engineer preferences over time and adapts |
| **Team-level dashboard** | Aggregate view for a manager persona |
| **MCP/A2A protocol usage** | Implement tool connectivity via Model Context Protocol |
| **Calendar-aware planning** | Factor in meeting schedule when generating time-blocked plans |

## 6. Constraints / Limitations
* **LLM API Usage:** Teams may use any LLM provider. Free-tier models (Gemini, Llama via Ollama) are encouraged.
* **No Pre-Built Task Managers:** You may not wrap an existing tool (Todoist, Notion, etc.). Intelligence must be built by your team.
* **Data Sources:** Use the provided simulated data. You may add additional simulated sources but the provided data must be processable.
* **Open Source:** All code must be written during the hackathon. Open-source libraries and frameworks are allowed.
* **Guidelines:** * Try to use simulated data, wherever feasible use the real world data.
  * Agent must be transparent about its reasoning (no black-box decisions).
  * Prioritization logic must be auditable and explainable.

## 7. Assumptions
* **Simulated environment:** Teams will work with simulated data that represents realistic enterprise task sources.
* **Single engineer focus:** The primary use case is a single engineer’s task management. Team-level views are a stretch goal, not a requirement.
* **LLM availability:** Teams have access to at least one LLM (via API or locally hosted). Free-tier options are sufficient for the hackathon scope.
* **Internet access:** Teams have internet access for API calls, package installation, and documentation reference.
* **No real-time streaming:** The agent processes data on-demand or on a triggered schedule, not via real-time event streams from live systems.
* **Correctness over completeness:** It is more important that the agent produces accurate, trustworthy results for the data it processes than that it covers every edge case.

## 8. Target Users / Personas

### Primary Persona — Full-Stack Engineer

| Attribute | Detail |
| :--- | :--- |
| **Role** | Mid-level full-stack engineer |
| **Team** | 8-person Agile scrum team, 2-week sprints |
| **Tools** | Jira, GitHub, Outlook, Slack, ServiceNow |
| **Pain** | Spends first 45 min each morning just figuring out what to work on. Missed a P1 last week because it was buried in a Friday email which was not read until Monday. |
| **Goal** | *“I want to open one thing in the morning and know exactly what my day should look like, with nothing falling through the cracks.”* |

### Secondary Persona — Engineering Manager

| Attribute | Detail |
| :--- | :--- |
| **Role** | Engineering Manager overseeing 3 scrum teams |
| **Pain** | No visibility into true workload distribution; relies on standup self-reports |
| **Goal** | *“I want to understand my team’s load and blockers at a glance, without micromanaging.”* |

## 9. Current State Summary
Today, without TaskPilot AI, an engineer’s morning workflow looks like this:
1. **Open Jira:** Scan sprint board, identify assigned stories and bugs, mentally note carry-overs from last sprint.
2. **Check ServiceNow:** Look for new production defects assigned overnight. Assess severity.
3. **Read Outlook inbox:** Scroll through 40-50 emails. Mentally extract action items. Some get missed.
4. **Scan Slack:** Read DMs, channel mentions, and thread replies. Respond to urgent pings.
5. **Review GitHub:** Check PR review requests. Assess which ones are blocking teammates.
6. **Recall meeting notes:** Try to remember follow-up items from yesterday’s meetings.
7. **Mentally prioritize:** Gut-feel decision on what to work on first. No formal scoring or rationale.
8. **Start working:** Begin on a task, get interrupted by Slack/email, context-switch, lose multiple minutes re-focusing.

## 10. Expected Target State / Vision
With TaskPilot AI deployed, the engineer’s morning transforms to this:
1. **Open TaskPilot:** A single interface presents the unified, deduplicated, prioritized task plan for the day.
2. **Review plan:** Top 3 priorities are highlighted with clear rationale (*“P1 severity + VP escalation + SLA deadline tomorrow”*).
3. **Check alerts:** Agent has already flagged: *“New P1 defect assigned overnight. SLA: 1 business day remaining.”*
4. **Ask questions:** *“Why is the upload bug ranked #1?”* / *“Summarize the VP’s email.”* / *“What’s blocking my teammates?”*
5. **Start executing:** Confidence that nothing is missed. Focus on the right work from minute one.
6. **Mid-day adaptation:** New urgent email arrives; agent automatically re-prioritizes and notifies: *“New item bumped to #2.”*
7. **End-of-day summary:** Agent generates progress report: 3 tasks completed, 1 in progress, 2 deferred to tomorrow.
8. **Weekly rollup:** Agent produces standup-ready summary of the week’s accomplishments and blockers.

The vision is an agent that functions as a personal chief of staff for every engineer — one that never forgets a task, never misses an email, and always has a data-driven answer to *“what should I work on next?”*

## 11. Success Metrics & Acceptance Criteria

### Quantitative Metrics

| Metric | Target | How Measured |
| :--- | :--- | :--- |
| **Task Discovery Rate** | 95%+ of all actionable items captured | Compare agent-discovered tasks vs. manually identified tasks in test dataset |
| **Deduplication Accuracy** | 90%+ of duplicate/related tasks correctly merged | Precision and recall on labeled test data |
| **Time-to-Plan** | < 60 seconds to generate daily plan | Measured from trigger to output |
| **Actionability Score** | 4.0+ / 5.0 user satisfaction on plan usefulness | Evaluated by judges simulating engineer persona |

### Acceptance Criteria (Demo Scenario)
During the live demo, teams must successfully walk through this scenario:
* **Ingest:** Show the agent consuming all provided sample data (Scrum board, defect tracker, emails, meeting transcript).
* **Extract:** Show at least 2 action items extracted from emails or meeting notes.
* **Deduplicate:** Show the agent detecting that Jira ID-1234 and email with customer escalation are about the same issue.
* **Prioritize:** Show the ranked task list with explanations for the top 3 priorities.
* **Plan:** Show the generated daily plan for “Monday morning.”
* **Converse:** Ask the agent at least 2 natural language questions (e.g., “Why is the upload bug my #1?”, “Summarize the VP’s email”).
* **Adapt:** Inject a new simulated P1 defect mid-demo and show the agent re-prioritizing.

## 12. Risks & Dependencies

### Risks

| Risk | Likelihood | Impact | Mitigation |
| :--- | :--- | :--- | :--- |
| **LLM hallucination** — Agent fabricates tasks or attributes that don’t exist in source data | Medium | High | Implement grounding checks; always trace output back to source data; require citations |
| **Poor extraction accuracy** — LLM misinterprets email content or misses action items | Medium | High | Use structured prompting with few-shot examples; test iteratively against sample data |
| **Deduplication false positives** — Agent incorrectly merges unrelated tasks | Medium | Medium | Set confidence thresholds; require >85% semantic similarity for auto-merge; flag borderline cases for review |
| **API rate limits / cost overrun** — Excessive LLM API calls during hackathon | Low | Medium | Use caching, batch processing, and smaller models for initial passes; reserve larger models for final reasoning |
| **Demo instability** — Live demo fails due to API timeouts or edge cases | Medium | High | Pre-record backup demo video; test demo scenario end-to-end before presentation |
| **Scope creep** — Team attempts too many features, fails to deliver MVP | High | High | Follow the prioritized scope (Must-Have first, then Should-Have) |

### Dependencies

| Dependency | Description | Fallback |
| :--- | :--- | :--- |
| **LLM API Access** | At least one LLM provider must be accessible (OpenAI, Anthropic, Google, or local model) | Use Ollama with Llama 3 locally as zero-cost fallback |
| **Python / Java / Node.js runtime** | Development environment with package manager | Pre-configured dev containers or cloud IDE |
| **Simulated data files** | Provided JSON files for Scrum board, defect tracker, email inbox, and meeting transcript | Included in this problem statement |
| **Internet access** | Required for API calls and package installation | Local model + pre-installed packages as fallback |

## 13. Expected Deliverables from Participants

| Deliverable | Sample Format | Description |
| :--- | :--- | :--- |
| **Working Prototype** | GitHub Repository | Source code with README containing setup instructions. |
| **Live Demo** | Presentation + QA | Demonstrate the agent processing the sample data provided and generating outputs. Walk through the required demo scenario. |
| **High Level Architecture Document** | 1-2 page PDF or Markdown | Describe your system architecture, LLM integration approach, and design decisions. |

## 14. Provided Inputs / Resources for Hackathon Teams
Use the simulated data on your own.

## 15. Evaluation Criteria

| Category | Description |
| :--- | :--- |
| **Agentic Intelligence** | How autonomous, reasoning-driven, and proactive is the agent? |
| **Task Aggregation & Extraction** | Quality of multi-source ingestion and unstructured text parsing |
| **Prioritization & Planning** | Sophistication and explainability of priority logic and daily plan |
| **Technical Execution** | Code quality, architecture, reliability, error handling |
| **Demo & Presentation** | Clarity of demo, storytelling, and real-world applicability |

## 16. Stretch Goals (Bonus Points)
*[Add details here]*

## 17. Additional References / Links

| Resource | URL |
| :--- | :--- |
| **ReAct Pattern (Reasoning + Acting)** | “ReAct: Synergizing Reasoning and Acting in Language Models” |
| **LangChain Agent Documentation** | https://python.langchain.com/docs/modules/agents/ |
| **CrewAI Documentation** | https://docs.crewai.com/ |
| **Model Context Protocol (MCP)** | https://modelcontextprotocol.io/ |
| **Agent-to-Agent Protocol (A2A)** | https://google.github.io/A2A/ |
| **Building Effective Agents (Anthropic)** | https://docs.anthropic.com/en/docs/build-with-claude/agentic |