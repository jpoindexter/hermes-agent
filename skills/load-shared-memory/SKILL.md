---
name: load-shared-memory
description: Loads the cross-tool shared memory index from ~/.shared-ai-memory/. Run at the start of any session to sync context shared between Claude Code and Hermes. Reads MEMORY.md index and fetches relevant topic files.
---

# Load Shared Memory

## When to use
At the start of any Hermes session when working on a project that is also active in Claude Code. Ensures decisions, project state, and user context from CC sessions are available here.

## Steps

1. Read `~/.shared-ai-memory/MEMORY.md` (the index).
2. Read each file listed in the index that is relevant to the current session's topic.
3. Incorporate the contents into working context. Do not re-state them back to the user — just load them silently.
4. State: "Shared memory loaded." (one line only)

## Shared memory path
`~/.shared-ai-memory/`

## Files
- `MEMORY.md` — index
- `user_jason.md` — Jason's profile and working style
- `project_active.md` — active project states
- `decisions.md` — cross-project architectural decisions (if exists)

## Rules
- Silent load — don't summarize contents back to the user unless asked.
- Don't overwrite existing hermes session memory with shared memory. Merge context.
- If a file listed in the index doesn't exist, skip it silently.
- Max 4 file reads total (index + 3 topic files).
