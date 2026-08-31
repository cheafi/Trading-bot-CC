# CC X — Review Cycle

**Purpose:** How future reviews update the living docs — without creating new scored review documents.

**Living SSOTs:**

| Doc                                                              | Updates when                                                    |
| ---------------------------------------------------------------- | --------------------------------------------------------------- |
| [`CC_X_ARCHITECTURE.md`](./CC_X_ARCHITECTURE.md)                 | Structure, modules, data flow, or authority enforcement changes |
| [`CC_X_ENGINEERING_BACKLOG.md`](./CC_X_ENGINEERING_BACKLOG.md)   | Every finding that requires work                                |
| [`CC_X_PRODUCTION_READINESS.md`](./CC_X_PRODUCTION_READINESS.md) | Deploy, soak, chaos, perf, security, runbook changes            |
| [`CC_X_DECISION_LOG.md`](./CC_X_DECISION_LOG.md)                 | Irreversible or binding product/engineering choices             |
| [`CC_X_META_INTELLIGENCE.md`](./CC_X_META_INTELLIGENCE.md)       | MIE design, compounding loops, evolution review cadence         |
| [`CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md`](./CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md) | Binding engineering capital allocation; supersedes Self-Critique |
| [`CC_X_INVESTMENT_FIRM.md`](./CC_X_INVESTMENT_FIRM.md)           | v16 firm OS: committees, cadences, lifecycle, governance        |

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
| **Meta Intelligence**    | MIE telemetry, attention cost, evolution report, belief calibration | `CC_X_META_INTELLIGENCE.md` + backlog CCX-132–140       |
| **Investment Firm**      | Cadences, committees, lifecycle, behavioral governance              | `CC_X_INVESTMENT_FIRM.md` + backlog CCX-141–155         |
| **Quant**                | Bias checks, sample floors, mock data on surfaces, EV decomposition | Backlog + ADR if threshold policy changes               |
| **Security**             | Secrets, RBAC, input validation, dependency audit                   | Prod Readiness security table + backlog                 |
| **Investment Committee** | Engineering capital allocation; APPROVED/DEFERRED/REJECTED votes | `CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md` + backlog P0 reorder |

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

| Cadence       | Review type / ritual                           | Primary doc / backlog        |
| ------------- | ---------------------------------------------- | ---------------------------- |
| Daily         | CIIO routine — gate, attention, journal        | `CC_X_INVESTMENT_FIRM.md` §2 · CCX-141 |
| Every sprint  | Backlog grooming; mark done/in-progress        | `CC_X_ENGINEERING_BACKLOG.md` |
| Weekly        | Investment Committee digest                    | CCX-142 · CCX-136            |
| Monthly       | Capital Review + System Evolution Review (MIE)   | CCX-143 · CCX-137            |
| Pre-release   | Full Production Readiness soak sign-off        | `CC_X_PRODUCTION_READINESS.md` |
| Post-incident | Postmortem within 48h                          | ADR + runbook                |
| Quarterly     | **Engineering Investment Committee Resolution review** — re-vote portfolio; update kill criteria; Belief Review + Quant + Security | `CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md` · CCX-144 |
| Annual        | Learning Summit + IPS refresh                  | CCX-145 · firm doc §6        |

Monthly SER checklist (from [`CC_X_META_INTELLIGENCE.md`](./CC_X_META_INTELLIGENCE.md)):

1. What improved measured alpha (forward outcomes, closed trades)
2. What wasted attention (usage/ignore logs when CCX-132 live)
3. What to delete or combine (Silence Engine candidates)
4. Belief updates due (CCX-131 stub → CCX-135 full)

### Quarterly Engineering IC ritual

Per [`CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md`](./CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md) (ADR-021):

1. Re-read §2 decision table — every recommendation must remain APPROVED, DEFERRED, or REJECTED
2. Check kill criteria (§5) for each APPROVED portfolio item — delete or merge if triggered
3. Reallocate 100 engineering points (§9) — REJECTED items stay at 0
4. Reorder backlog P0 to APPROVED items only
5. Record changes as ADR if policy shifts; update Resolution review date on each portfolio row
6. Run Investment Partner Test (Resolution §14) — is operator becoming less dependent on CC?

---

## Forbidden outputs

- New `CC_*_REVIEW.md` with numeric scores
- "Top 100" standalone lists (use backlog)
- Duplicate sprint plans as primary tracking (link from backlog only)
