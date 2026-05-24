---
name: debug-system
description: End-to-end debugging skill system. Orchestrates codegraph-context → systematic-debugging → root cause confirmation → fix → verification. Invoke with a bug description and project name.
---

# debug-system

Orchestrated debugging pipeline. Run this instead of ad-hoc debugging.

## Skill chain

| Step | Skill | HITL |
|------|-------|------|
| 1 | `software-development/codegraph-context` | none |
| 2 | `software-development/systematic-debugging` | none |
| 3 | Root cause summary | **STOP — confirm root cause before writing any fix** |
| 4 | Fix (in-place or via `software-development/test-driven-development`) | none |
| 5 | `software-development/requesting-code-review` (self-review) | none |
| 6 | Regression test + verify | **STOP — show passing tests, get sign-off** |

## Step 1: codegraph-context

Run `software-development/codegraph-context` with the bug description as the task.

## Step 2: systematic-debugging

Run `software-development/systematic-debugging`. Collect:
- Error message / symptom
- Stack trace or last known good state
- Hypotheses ranked by probability
- Cheapest experiment to falsify #1

## HITL checkpoint — root cause

Before writing any fix:
1. State root cause in one sentence
2. State confidence (high/medium/low) and what would change it
3. Wait for explicit "yes" before proceeding

## Step 4: Fix

- If fix is >20 lines or touches >2 files: run `software-development/test-driven-development` (red → green)
- If fix is small: write directly, add regression test inline

## Step 5: Self-review

Run `software-development/requesting-code-review` on the diff. Surface any risk before shipping.

## Step 6: Verification

Run tests. Show output. State:
- Which test covers the regression
- Whether any related tests changed behavior

Wait for sign-off before closing.

## Anti-patterns

- Never skip root cause checkpoint — "obvious fixes" are where regressions live
- Never delete a failing test to make the suite pass
- Never log-spam to find the bug — write a targeted test instead
