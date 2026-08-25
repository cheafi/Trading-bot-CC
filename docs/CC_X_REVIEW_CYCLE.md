# CC X — Review Cycle

**Purpose:** How future reviews update the living docs — without creating new scored review documents.

**Living SSOTs:**

| Doc                                                              | Updates when                                                    |
| ---------------------------------------------------------------- | --------------------------------------------------------------- |
| [`CC_X_ARCHITECTURE.md`](./CC_X_ARCHITECTURE.md)                 | Structure, modules, data flow, or authority enforcement changes |
| [`CC_X_ENGINEERING_BACKLOG.md`](./CC_X_ENGINEERING_BACKLOG.md)   | Every finding that requires work                                |
| [`CC_X_PRODUCTION_READINESS.md`](./CC_X_PRODUCTION_READINESS.md) | Deploy, soak, chaos, perf, security, runbook changes            |
| [`CC_X_DECISION_LOG.md`](./CC_X_DECISION_LOG.md)                 | Irreversible or binding product/engineering choices             |

---

## Process (every review)

1. **Run review** using type checklist below (code-verified facts only for architecture claims).
2. **Add backlog rows** — one row per actionable item in `CC_X_ENGINEERING_BACKLOG.md`. Include Priority, Sprint, Acceptance criteria.
3. **Update Architecture** only if modules, boundaries, or authority flow changed.
4. **Update Production Readiness** if new soak step, chaos scenario, perf target, or runbook needed.
5. **Add ADR** if a binding decision was made or an existing ADR was superseded.
6. **Do not** publish a standalone review doc with scores, scorecards, or "Pass N" naming.
7. **Optional:** Link PR or commit in backlog `Evidence/PR` column.

---

## Review types

| Type                     | Focus                                                               | Primary output                                          |
| ------------------------ | ------------------------------------------------------------------- | ------------------------------------------------------- |
| **Architecture**         | Engine boundaries, SSOT objects, router/service split, data flow    | Architecture doc + backlog migrations                   |
| **Production Readiness** | Soak, chaos, CI gates, runbooks, security checklist                 | Production Readiness doc + backlog P0 ops items         |
| **Performance**          | Latency p95, poll consolidation, cache policy (never permission)    | Prod Readiness perf table + backlog perf rows           |
| **Operator UX**          | Mission Brief, authority strips, bilingual copy, workflow friction  | Backlog UX rows only (no UX score doc)                  |
| **Quant**                | Bias checks, sample floors, mock data on surfaces, EV decomposition | Backlog + ADR if threshold policy changes               |
| **Security**             | Secrets, RBAC, input validation, dependency audit                   | Prod Readiness security table + backlog                 |
| **Postmortem**           | Incident root cause, deploy drift, broker failure                   | ADR if policy change; backlog for fixes; runbook update |

---

## Prompt template

Use [`CC_X_MASTER_REVIEW_PROMPT.md`](./CC_X_MASTER_REVIEW_PROMPT.md) as the review prompt, with this override:

> Output findings as backlog rows and doc diffs only. Do not produce subsystem scorecards or overall platform scores.

---

## Archive policy

- Superseded review documents live in [`docs/archive/`](./archive/).
- One-line banner at top of retained copies: _"Superseded by CC_X_ENGINEERING_BACKLOG.md and CC_X_ARCHITECTURE.md — retained for history only."_
- Roadmap narrative: [`CC_X_INSTITUTIONAL_ALPHA_OS.md`](./CC_X_INSTITUTIONAL_ALPHA_OS.md) (historical; not SSOT for work tracking).

---

## Cadence (suggested)

| Cadence       | Review type                                    |
| ------------- | ---------------------------------------------- |
| Every sprint  | Backlog grooming; mark done/in-progress        |
| Monthly       | Architecture + Production Readiness spot-check |
| Pre-release   | Full Production Readiness soak sign-off        |
| Post-incident | Postmortem within 48h                          |
| Quarterly     | Quant + Security pass                          |

---

## Forbidden outputs

- New `CC_*_REVIEW.md` with numeric scores
- "Top 100" standalone lists (use backlog)
- Duplicate sprint plans as primary tracking (link from backlog only)
