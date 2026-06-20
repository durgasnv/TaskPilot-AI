# LLM Client Abstraction + Mock (Day 3 — Task 2)

## What This Is
`src/taskpilot_ai/llm/client.py` provides:
- `LLMClient` — an abstract base class with one method: `complete(system_prompt, user_prompt) -> LLMResponse`
- `MockLLMClient` — a deterministic fake that returns pre-written JSON without any API call

`ExtractionAgent` in `specialists.py` was updated to call the LLM and
parse the response into real `TaskRecord` objects.

## Why It Exists
Before this task, `ExtractionAgent.run()` built prompt packets but never
called anything — `state.extracted_tasks` always stayed empty. That meant
`DeduplicationAgent` and `PrioritizationAgent` had nothing to work with.

The abstraction layer exists so:
- Development works offline (MockLLMClient, no API key required)
- The real LLM swap is a one-line change at construction time
- Tests stay fast and deterministic

## How the LLM Call Works

```
ExtractionAgent.run()
  ├── build_extraction_packet(document)  → system + user prompts
  ├── self.llm.complete(system, user)    → LLMResponse with JSON string
  └── _parse_task_records(content, source) → list[TaskRecord]
```

The `_parse_task_records` function does `json.loads()` on the LLM output
and maps each dict to a `TaskRecord`. If the JSON is malformed it returns
an empty list (silent degradation, never a crash).

## MockLLMClient Key Lookup
The mock detects which source is being extracted by scanning the user
prompt for the line `Source: <name>`. It returns a different hardcoded
JSON array per source:
- `jira` → 2 tasks (payment gateway bug + JWT upgrade)
- `servicenow` → 1 task (DB connection pool)
- `outlook` → 1 task (VP escalation response)
- `meeting_notes` → 1 task (retry logic action item)

## Swapping to a Real LLM
When another teammate or the demo integration connects a real model:

```python
from anthropic import Anthropic

class AnthropicLLMClient(LLMClient):
    def __init__(self):
        self._client = Anthropic()

    def complete(self, system_prompt, user_prompt):
        msg = self._client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return LLMResponse(
            content=msg.content[0].text,
            model=msg.model,
            tokens_used=msg.usage.input_tokens + msg.usage.output_tokens,
        )
```

Then pass it to `ExtractionAgent(llm=AnthropicLLMClient())` and nothing
else needs to change.

## Impact on Pipeline
After this task the end-to-end flow produces real data when source files
exist:
```
Ingestion → loads files → WorkflowState.raw_inputs populated
Extraction → calls MockLLM → WorkflowState.extracted_tasks populated
Dedup → passes tasks through
Prioritization → creates RankedTask placeholders with scores
Planning → builds daily_plan list from ranked tasks
```
