---
name: review-ship-system
description: Pre-ship review and deployment pipeline. Orchestrates code-review → security gate → deploy checklist → finishing-a-development-branch. Run before any branch merge or deploy.
---

# review-ship-system

Final gate before merge or deploy. Run this when work is done and tests pass.

## Skill chain

| Step | Skill | Gate |
|------|-------|------|
| 1 | `software-development/requesting-code-review` | Must pass — no merge with open HIGH findings |
| 2 | Security self-audit | Hard gate — auth, secrets, injection, OWASP top 10 |
| 3 | Deploy checklist | Must complete — migrations, env vars, feature flags |
| 4 | `software-development/writing-plans` (if hotfix) | Optional |

## Step 1: Code review

Run `software-development/requesting-code-review`. Report findings by severity:
- **HIGH**: Must fix before merge
- **MEDIUM**: Fix or explicitly accept with reason
- **LOW**: Note in PR description

Do not proceed past step 1 with any open HIGH finding.

## Step 2: Security audit

Check each surface that changed:
- Auth: every new route/endpoint has an auth guard
- Secrets: no keys, tokens, or credentials in code or logs
- Input: Zod validation at every boundary
- SQL: no string interpolation in queries
- Dependencies: any new dep checked for known CVEs

If any item fails: **STOP**. Fix before proceeding.

## Step 3: Deploy checklist

Before merge:
- [ ] Migrations: all new migrations reviewed, additive, reversible
- [ ] Env vars: new vars documented in `.env.example`
- [ ] Tests: suite passes (`scripts/run_tests.sh`)
- [ ] Type check: `.venv/bin/ty check` clean
- [ ] Lint: `.venv/bin/ruff check .` clean
- [ ] CHANGELOG or commit message describes the change

## Output

Report:
```
CODE REVIEW: PASS | FAIL (n HIGH, n MEDIUM)
SECURITY: PASS | FAIL (items)
DEPLOY CHECKLIST: n/n complete
VERDICT: SHIP | BLOCK (reason)
```

Only output SHIP when all gates pass.
