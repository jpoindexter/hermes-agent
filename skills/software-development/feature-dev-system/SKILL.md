---
name: feature-dev-system
description: End-to-end feature development system for Hermes. Orchestrates codegraph-context → writing-plans → test-driven-development → executing-plans → requesting-code-review. Invoke with a feature description.
---

# Feature Development System (Hermes)

**Announce at start:** "Running feature-dev-system for: [feature description]"

## Skill chain (in order)

1. `codegraph-context` — map relevant code before touching anything
2. `writing-plans` — write a bite-sized implementation plan
3. `test-driven-development` — failing tests first
4. `subagent-driven-development` — dispatch subagents per plan task
5. `requesting-code-review` — review before merge

## HITL checkpoints
- After plan: "Plan ready. Proceed with TDD?" → wait for yes
- After red phase: "Tests failing. Implement?" → wait for yes
- After review: "Review passed. Merge?" → wait for yes

## Rules
- Step 1 always runs first.
- Never proceed past a HITL checkpoint without explicit yes.
- Scope creep → park in PARKED.md, don't build.
- >2 fix attempts → log in ERRORS.md.

## Input
Feature description + project path.

## Trigger
"build [feature]", "implement [feature]", "add [X] to hermes"
