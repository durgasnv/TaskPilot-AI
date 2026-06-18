# Ingestion And Extraction

## Summary
Day 2 was about moving from pure scaffolding to runnable ingestion and extraction preparation. We still did not connect a real LLM, but we made the agent flow ready for that connection.

## What We Built
### Source configuration
We added default source paths in `src/taskpilot_ai/config.py`.

Why:
The agent needs to know which source types it should try to load.

How:
`AppConfig` defines a list of `SourceConfig` entries for Jira, ServiceNow, Outlook, and meeting notes.

### Source document model
We added `SourceDocument` in `src/taskpilot_ai/models.py`.

Why:
The system needs both the raw content and the metadata about where it came from.

How:
Each source document stores the source type, text content, and file location.

### Source reader tool
We added `SourceReader` and `FileSystemSourceReader` in `src/taskpilot_ai/tools/source_reader.py`.

Why:
Agents should use a tool interface instead of reading files directly in scattered code.

How:
The tool returns a `ReadResult`. If the file exists, it returns a `SourceDocument`. If not, it returns an error string.

### ReAct prompts
We added prompt builders in `src/taskpilot_ai/prompts/extraction.py`.

Why:
Prompt behavior should be explicit and centralized instead of hidden inside one agent.

How:
The prompts tell the future LLM to stay grounded in the source text, reason through a Thought/Action/Observation/Final loop, and return evidence-backed tasks.

### ReAct runtime packet
We added `ReActPromptPacket` in `src/taskpilot_ai/agents/react_runtime.py`.

Why:
Most LLM integrations need a system prompt plus a user prompt. Packaging them together makes later execution simpler.

How:
The runtime builds one packet for ingestion and one for extraction for each source document.

### Ingestion agent upgrade
We upgraded the ingestion agent in `src/taskpilot_ai/agents/specialists.py`.

Why:
Day 2 required connecting tool dependencies to the agent flow.

How:
The agent loops through configured sources, asks the file reader for each file, stores successful documents in state, and records traces for both success and failure cases.

### Extraction agent upgrade
We upgraded the extraction agent in `src/taskpilot_ai/agents/specialists.py`.

Why:
We needed a bridge between raw source documents and future LLM-based task extraction.

How:
The agent builds extraction prompt packets for each loaded document and writes prompt previews into `memory.react_scratchpad`.

## Main Concepts To Remember
- Tool abstraction: agents depend on interfaces
- Grounding: outputs must be tied to source evidence
- ReAct structure: reason in steps, act deliberately, report final result
- Graceful degradation: missing inputs should not break the whole system
- Runtime contracts: build the integration boundary before the full implementation
