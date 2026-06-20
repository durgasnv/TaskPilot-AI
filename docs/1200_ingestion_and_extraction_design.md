# Ingestion And Extraction Design

## Purpose
This document explains the Day 2 Dev 2 work. The goal was to prepare the ingestion and extraction agent path so real source files and real LLM calls can be connected later with minimal rewrites.

## Feature: Source Configuration
### What it is
Default source entries for Jira, ServiceNow, Outlook, and meeting notes.

### Why it exists
The ingestion layer needs to know what sources should exist and where it should look for them.

### How it works
`src/taskpilot_ai/config.py` defines `AppConfig` and `SourceConfig`. Each source has a logical name and an expected file path such as `data/jira.json`.

## Feature: Source Document Model
### What it is
A typed object representing a raw source payload.

### Why it exists
Raw strings are not enough. The system also needs metadata such as source type and file location for tracing and explainability.

### How it works
`src/taskpilot_ai/models.py` defines `SourceDocument` with `source`, `content`, and `location`. Ingestion writes these objects into `WorkflowState.raw_inputs`.

## Feature: File Reader Tool Abstraction
### What it is
An interface for reading source inputs, plus a filesystem implementation.

### Why it exists
The ingestion agent should depend on a tool contract, not directly on the filesystem. That makes it easier to swap in alternate readers later.

### How it works
`src/taskpilot_ai/tools/source_reader.py` defines `SourceReader` and `FileSystemSourceReader`. The agent asks the reader for a `ReadResult`, which contains either a `SourceDocument` or an error string.

## Feature: Graceful Handling Of Missing Files
### What it is
The graph keeps running even when source files are not present yet.

### How it works
If a file path is missing, `FileSystemSourceReader` returns an error instead of raising. The ingestion agent writes an execution trace such as `Skipped source 'jira': Missing source file...` and the pipeline continues.

## Feature: ReAct Prompt Builders
### What it is
Prompt constructors for ingestion and extraction agents.

### Why it exists
Prompt logic should be centralized and explicit so LLM wiring later is predictable and reviewable.

### How it works
`src/taskpilot_ai/prompts/extraction.py` builds:
- an ingestion system prompt
- an extraction system prompt
- a user prompt that embeds the source metadata and source content

The user prompt also encodes a ReAct-style structure: Thought, Action, Observation, Final.

## Feature: ReAct Runtime Packet
### What it is
A small data structure that groups a system prompt and a user prompt.

### Why it exists
Most LLM clients expect prompts in structured pieces. Storing them together makes the later LLM integration cleaner.

### How it works
`src/taskpilot_ai/agents/react_runtime.py` creates `ReActPromptPacket` objects through `build_ingestion_packet()` and `build_extraction_packet()`.

## Feature: Ingestion Agent File Loading
### What it is
The ingestion agent now actively tries to read configured source files.

### Why it exists
Day 2 required associating file-reading tool dependencies with the agent flow.

### How it works
For each configured source, the ingestion agent:
1. maps the config name to `TaskSource`
2. asks the reader to load the file
3. stores successful results in `WorkflowState.raw_inputs`
4. stores source locations in `AgentMemory`
5. records a trace entry
6. stores the prompt context in the ReAct scratchpad

## Feature: Extraction Agent Prompt Preparation
### What it is
The extraction agent now prepares extraction prompt packets for every loaded source.

### Why it exists
This is the final step before real LLM execution. It proves the prompt path is grounded and repeatable.

### How it works
For each `SourceDocument` in `WorkflowState.raw_inputs`, the extraction agent builds an extraction packet and writes a prompt preview to `memory.react_scratchpad`. Right now it does not call an LLM yet; it only prepares the runtime contract.

## Current Limit
The branch prepares the ingestion and extraction runtime but still uses placeholder extraction results. Actual task extraction and structured outputs are the next Dev 2 integration step.
