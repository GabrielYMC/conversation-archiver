---
name: conversation-archiver
description: >
  Conversation archival service that transforms raw chat transcripts into structured,
  searchable Markdown archives. Use this skill whenever the user wants to archive a
  conversation, save a chat for future reference, create a summary of a discussion,
  preserve dialogue history, or export conversation knowledge. Also trigger when the
  user says "archive this", "summarize this chat", "save this conversation", "封存對話",
  "整理對話", or refers to preserving discussion outcomes. Works with any conversation
  format — Claude, Hermes, Discord, Slack, or plain text. Outputs structured .md files
  following the conversation-archive protocol from agent-commons.
---

# Conversation Archiver

A service that reads raw conversation transcripts and produces structured Markdown
archives — complete with frontmatter, development trajectory, key concepts, decisions,
deliverables, and the original conversation text.

## What It Does

Input: a conversation transcript (text, JSON, or pasted content)
Output: one or more .md files, each containing a structured summary + the original dialogue

If the conversation is long enough that the summary would exceed ~800 words, the service
first identifies natural split points and asks the user to confirm before generating
multiple files.

## How It Works

The archival process has three stages:

### Stage 1: Scan for Split Points

Read the entire conversation and identify natural topic boundaries. A split point is
where the conversation shifts focus — e.g., from design discussion to implementation,
from one project to another, or from building something to analyzing an external resource.

Signals that indicate a split point:
- Explicit topic change ("OK, now let's talk about...")
- A deliverable is completed and a new thread begins
- The user introduces new external material (a URL, a paper, a new project)
- A major decision is made and the conversation moves to its consequences

Output a numbered list of suggested segments with one-sentence descriptions:
```
I suggest splitting into 3 segments:
1. Kanban skill design and generalization (messages 1-34)
2. Behavioral framework and TUI war room design (messages 35-62)
3. Open-source repo structure and compression strategy (messages 63-81)

Do you agree, or would you like to adjust the boundaries?
```

If the conversation is short enough for a single file (~800 words summary), skip
this stage and go directly to Stage 3.

### Stage 2: User Confirms

Wait for the user to confirm, adjust, or override the suggested split. The user
may merge segments, split them further, or choose not to split at all.

### Stage 3: Generate Archives

For each segment (or the whole conversation if no split), generate a .md file
containing all required sections. Read `references/archive-schema.md` for the
exact schema and formatting rules.

**File naming:**
```
{{DATE}}_{{TOPIC_SLUG}}-{{PART}}.md
```
Example: `2026-04-13_kanban-agent-collaboration-1.md`

If only one file, omit the part number.

## Model Routing

This skill is designed to work with cost-efficient models. It does not require
frontier-level reasoning.

| Stage | Task | Recommended model |
|---|---|---|
| Scan split points | Read full conversation, identify topic shifts | Needs long context: Gemma 4 31B, Qwen3-30B-A3B, or any 128K+ model |
| Generate summary | Fill structured schema, ~600 words per segment | Any instruction-following model: Gemma 4 E4B (local) is sufficient |
| Validate format | Check frontmatter YAML and section completeness | No LLM needed — regex/script validation |

If running locally via Ollama, use the largest available model for Stage 1 (scan)
and the fastest available model for Stage 3 (generate). This matches the AgentOpt
principle: model selection is a pipeline-level optimization, not a single-model choice.

## Input Formats

The service accepts conversation transcripts in several formats:

**Plain text (pasted):**
```
H: 你好，我想討論一下專案架構
A: 好的，讓我們從需求開始...
```

**JSON (Claude export, Hermes session):**
```json
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

**Markdown (already formatted):**
```markdown
**User:** 你好
**Assistant:** 好的...
```

The skill auto-detects the format and normalizes to H:/A: pairs internally.

## Usage

### From Hermes (Discord/CLI)

```
archive this conversation
```
or
```
/archive --input ./session-2026-04-13.jsonl --output ./archives/
```

### From command line

```bash
python scripts/archiver.py --input conversation.txt --output ./archives/
```

### Programmatic

```python
from archiver import ConversationArchiver

archiver = ConversationArchiver(model="gemma4:31b")
segments = archiver.scan_splits("conversation.txt")
# user confirms segments
archiver.generate(segments, output_dir="./archives/")
```
