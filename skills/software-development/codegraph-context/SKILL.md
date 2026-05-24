---
name: codegraph-context
description: Builds code-graph context for a dev task using the codegraph MCP. Run first in any dev task in an indexed project. Queries the knowledge graph for relevant symbols, files, and call graph before touching code.
---

# CodeGraph Context Builder (Hermes)

## When to use
At the start of any development task on an indexed project (hermes-agent-clean, indx, brutal, hashmark, gripe, prova). Always invoke before reading files or writing code.

## Steps

1. **Confirm index.** Call the codegraph MCP tool `codegraph_status` with the project path.
   If not initialized → skip to step 5.

2. **Query context.** Call `codegraph_context` with the task description and project path.

3. **Present the summary:**
   - Files to read (prioritised by relevance)
   - Key symbols (functions/classes)
   - Likely test files
   - Relevant call graph edges

4. **Read top 3–5 files** with targeted offset/limit reads only.

5. **State:** "Context built for [project]. Relevant files: [list]. Ready."

## Output contract
```
{
  files: string[],
  symbols: string[],
  tests: string[],
  summary: string
}
```

## Project paths
- hermes-agent-clean: `/Users/jasonpoindexter/.hermes/hermes-agent-clean`
- indx: `/Users/jasonpoindexter/Documents/GitHub/_active/indx`
- brutal: `/Users/jasonpoindexter/Documents/GitHub/_active/brutal`
- hashmark: `/Users/jasonpoindexter/Documents/GitHub/_active/hashmark`
- gripe: `/Users/jasonpoindexter/Documents/GitHub/_active/gripe`
- prova: `/Users/jasonpoindexter/Documents/GitHub/_active/prova`

## Rules
- Max 3 codegraph calls per invocation.
- Skip if project not indexed.
- Do not re-read files already in context.
