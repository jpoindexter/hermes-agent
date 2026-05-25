---
name: theft-ai-context
description: Orients any agent working on the THEFT AI repo. Loads project shape, active code paths, current task, and verification commands without reading 30 docs. Invoke first in any THEFT AI session.
---

# theft-ai-context

Fast orientation for THEFT AI. Read this instead of BUILD-FROM-THIS/.

## What this repo is

THEFT AI is a local-first company operating system. A founder signs in, completes onboarding, sees 8 departments (Engineering, Design, Marketing, Sales, Operations, Finance, Legal, Support), runs real agent tasks, and reviews output in a Library.

## Active runtime

```
/Users/jasonpoindexter/Documents/GitHub/THEFT AI/paperclip/
```

This is the only runtime. `app/` is an archived prototype — do not add code there.

## Run the app

```bash
cd "/Users/jasonpoindexter/Documents/GitHub/THEFT AI"
pnpm dev:once          # starts Paperclip host at http://127.0.0.1:3100
pnpm smoke:health      # verify it's up
```

## Verify changes

```bash
pnpm typecheck         # required after every code change
pnpm test              # for runtime/Paperclip behavior changes
pnpm verify:active-ui  # for active product UI changes
```

## Active spec (implement this — do not invent new work)

```
specs/004-task-review-output-finalization/spec.md
```

Key user stories from spec 004:
1. Founder can start execution from task review (start button → opens chat/run surface)
2. Founder can publish output to Library when none exists (create issue document)
3. After publish, task review focuses the artifact editing flow

Active code paths for spec 004:
- `paperclip/ui/src/` — React frontend
- `paperclip/server/src/` — backend/API
- `paperclip/ui/src/pages/` — route pages (issue detail = task review)

## What's done

Slices 0.0–1.2 are complete. The app runs, onboarding works, 8 departments run via the `process` adapter, Library outputs land as issue documents, and the design system gate passes. Do not re-litigate architecture decisions — read `BUILD-FROM-THIS/DECISIONS.md` if needed.

## Anti-patterns that stall agents

- Reading all 30 docs in BUILD-FROM-THIS/ before acting → pick up spec 004 and code
- Continuing T120 design-system migration → that is paused; spec 004 is the priority
- Making changes in `app/` → wrong directory; all product work is in `paperclip/`
- Skipping `pnpm typecheck` → required, commits that don't type-check are blocked

## Code conventions

- File limit: 300 lines hard, 200 soft. Over 300 = split into modules.
- Tailwind: use THEFT token classes only. No raw hex, no arbitrary values in active routes.
- shadcn/ui primitives for all interactive controls.
- Branch: `002-founder-happy-path` is the active feature branch.

## Navigation shortcuts (codegraph indexed)

The repo is indexed by codegraph. Before reading files, use codegraph_context or codegraph_search to locate symbols, callers, and file boundaries. Saves 10-20 file reads per task.
