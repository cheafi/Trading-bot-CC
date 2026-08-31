# CC X — Investment Committee Resolution

**Product:** CC X (Clarity Console X) · `TradingAI_Bot`  
**Subtitle:** Investment Decision Operating System (IDOS)  
**Date:** 2026-08-25  
**Status:** **Binding** — supersedes CC X Self-Critique  
**Branch:** `cc/upgrade-regime-tracking`  
**Living docs:** [`CC_X_ENGINEERING_BACKLOG.md`](./CC_X_ENGINEERING_BACKLOG.md) · [`CC_X_DECISION_LOG.md`](./CC_X_DECISION_LOG.md) (ADR-021 · ADR-022 · ADR-023 · ADR-024 · ADR-025)

> Professional firms optimize **decision quality under uncertainty** via a repeatable operating system — not decision volume. This document is not advisory. It is a capital allocation decision. Engineering capital is finite. Every recommendation below has a status: **APPROVED**, **DEFERRED**, or **REJECTED**. No recommendation remains "interesting."

---

## Constitution (immutable)

**We are a partnership of one human and one operating system, managing capital as if it cannot be replaced — because it cannot.**

**Purpose.** Not to trade, predict, or perform. To **compound calibrated judgment** over decades through fewer, better, fully-owned decisions.

**Authority.** The human alone deploys capital. The system advises with radical honesty, fails closed when uncertain, and never confuses research quality with deploy permission. The page gate outranks every card rank.

Full one-page Constitution → [`CC_X_INVESTMENT_FIRM.md`](./CC_X_INVESTMENT_FIRM.md) §15.

---

## The Four Questions — immutable law

Immediately after the Constitution in all relevant docs. **Every surface, report, recommendation, review, and AI explanation must answer at least one.** If a feature cannot answer at least one → it should not exist.

| # | Question | Operator meaning |
|---|----------|------------------|
| 1 | **What do we know?** | Facts. Measured. Fresh. Verified. |
| 2 | **What do we believe?** | Hypothesis. Confidence. Trade-offs. |
| 3 | **What don't we know?** | Missing evidence. Unknowns. Assumptions. Alternatives. |
| 4 | **What should we do?** | Deploy / Monitor / Research / Repair / Wait |

**Operator mental model:** **KNOW → BELIEVE → DOUBT → ACT** — not engines, tabs, or scores.

### Screen redesign principle

Every screen begins:

```
TODAY
We know ...
We believe ...
We don't know ...
Therefore ...
```

Not indicators, scores, or charts first.

### IDOS reframe (from IOS)

| From | To |
|------|-----|
| Investment Operating System (IOS) | **Investment Decision Operating System (IDOS)** |
| Optimize activity and surface coverage | Optimize **decision quality under uncertainty** |
| Operator thinks in engines/tabs | Operator thinks in **KNOW → BELIEVE → DOUBT → ACT** |

The operator cares about four things only: what is true? what is likely? what is uncertain? what deserves capital?

Seven engines remain **internal implementation** (Architecture appendix). Deprecated from operator-facing philosophy: "Seven Engines" as primary mental model, score-first dashboards, engine-improvement framing in reviews.

---

## 1. Executive Summary

CC X is a **strong authority system** wearing an **incomplete compounding system**. The team got the hardest thing right first: **truth, gates, and deploy separation**. That is rare and should not be undervalued.

The honest problem: we built **engines before loops**. InvestmentObject, AlphaObject, forward outcomes, knowledge graph, meta intelligence — many exist as **artifacts without rituals**. The operator gets better gates but not yet a better **30-year judgment curve**. Documentation was recently consolidated (good), but **code and docs still drift** because living docs lag uncommitted Phase B work.

We over-indexed on **architectural completeness** (seven engines, sprint modules, provenance contracts) and under-indexed on **operator closure** (belief review, calibration, knowledge retrieval, marginal ROC). We also accumulated **UI surfaces** faster than we deleted them — Mission Control helped, but Today still fights for attention on WAIT days.

**IC verdict:** Keep the Constitution. Burn the vanity. Close four loops (Belief, Capital, Learning, Knowledge). Delete half the visible surfaces. Measure everything by **decision quality → behavior change → identity change** — not feature count.

---

## 2. INVESTMENT COMMITTEE DECISION

Engineering capital is finite. Treat engineering time like portfolio capital: every hour allocated is capital withdrawn from something else.

**Rules:**
- Every recommendation receives **APPROVED**, **DEFERRED**, or **REJECTED**
- No recommendation remains "interesting," "explore later," or "nice to have"
- **REJECTED** items receive **0** engineering points and must not appear in P0 backlog
- **DEFERRED** items require a review date and kill criteria before any work begins
- **APPROVED** items are the only work eligible for P0/P1 sprint assignment

### Decision table — all major recommendations

| # | Recommendation | Status | Rationale |
|---|----------------|--------|-----------|
| 1 | Belief Review ritual (thesis + kill + conviction required) | **APPROVED** | Highest decision-quality ROI; closes Learning loop |
| 2 | Marginal ROC daily panel | **APPROVED** | Capital allocation is the product; CCX-053 |
| 3 | WAIT-day silence + deletion batch | **APPROVED** | Negative complexity; highest attention ROI |
| 4 | Portfolio SSOT (server truth, no localStorage split) | **APPROVED** | Split-brain is capital risk |
| 5 | Knowledge retrieval on ticker open | **APPROVED** | Write-only graph is wasted compounding |
| 6 | Calibration quarterly report (Brier/ECE from forward outcomes) | **APPROVED** | T+20 marks exist; ritual missing |
| 7 | Override journal + cooldown | **APPROVED** | Trust map from existing override spirit |
| 8 | Trust-weighted CIIO (speak less, trust more) | **APPROVED** | Reduces cognitive load on WAIT days |
| 9 | Weekly IC digest (CIIO template) | **APPROVED** | Firm cadence; CCX-136 |
| 10 | Forward outcomes T+20 → belief grades | **APPROVED** | CCX-041 done; wire to Belief Review |
| 11 | Discovery demotion (not equal nav) | **APPROVED** | Attention sink; route through Mission Control |
| 12 | Meta Intelligence Phase 1 — usage log only | **APPROVED** | CCX-132; telemetry before dashboard |
| 13 | Attribution root ref on all board rows | **APPROVED** | CCX-005; audit chain |
| 14 | Mandatory provenance on all prices | **APPROVED** | CCX-006; stale = no deploy CTA |
| 15 | CI blocks authority regressions | **APPROVED** | CCX-007; protect the moat |
| 16 | Hide mock factor on deploy surfaces | **APPROVED** | CCX-008; false confidence risk |
| 17 | Deletion batch (10 surfaces) | **APPROVED** | Complexity must trend down |
| 18 | Today PM strip parity (best action SSOT) | **APPROVED** | CCX-UX-04; one mission answer |
| 19 | Evolution Dashboard UI (full) | **DEFERRED** | CCX-134; after usage log proves value |
| 20 | Playwright E2E breadth | **DEFERRED** | CCX-090; after belief loop tests exist |
| 21 | InvestmentObject full consumer migration | **DEFERRED** | CCX-126; after Belief Review proves IO need |
| 22 | Knowledge Graph MVP | **DEFERRED** | CCX-070; retrieval first, graph second |
| 23 | Alpha Factory artifact per candidate | **DEFERRED** | CCX-020; factory before ritual was wrong order |
| 24 | Institutional Research Workspace (11 tabs) | **DEFERRED** | CCX-025; surface bloat risk |
| 25 | Command palette ⌘K | **DEFERRED** | CCX-100; power-user nice-to-have |
| 26 | Real-Time Alpha Monitor (6 KPIs) | **DEFERRED** | CCX-042; after calibration ritual |
| 27 | Monthly Evolution Report PDF | **DEFERRED** | CCX-137; Phase 3 MIE |
| 28 | Curiosity Engine research queue | **DEFERRED** | CCX-139; after Discovery demotion |
| 29 | New AI narrative features | **REJECTED** | Unproven decision quality; provenance absent |
| 30 | More discovery filters | **REJECTED** | Attention sink; negative ROI |
| 31 | Additional top-level nav tabs | **REJECTED** | Complexity index must trend down |
| 32 | Enterprise RBAC / multi-tenant | **REJECTED** | CCX-120/122; one PM, one firm |
| 33 | Auto bracket submit | **REJECTED** | Human confirm permanent |
| 34 | ML/Thompson auto-apply | **REJECTED** | ADR-009; advisory only |
| 35 | Richer AI commentary on decision surfaces | **REJECTED** | CCX-108 demotion continues |
| 36 | Mock factor polish without live wire | **REJECTED** | CCX-052 deferred; polish rejected |
| 37 | Seven-engine taxonomy in operator UI | **REJECTED** | Docs only; operator sees Decide/Learn/Remember |
| 38 | Separate scored review documents | **REJECTED** | ADR-013; living docs only |
| 39 | Decision Journal — pre-outcome deploy + wait records | **APPROVED** | Highest IDOS ROI; CCX-156 P0 |
| 40 | Red Team structured challenge (not AI theater) | **APPROVED** | CCX-157 stub |
| 41 | Outside View class base rates | **APPROVED** | CCX-158 stub |
| 42 | Decision Committee virtual debate | **APPROVED** | CCX-159 stub |
| 43 | Decision Health calibration inputs (non-blocking) | **APPROVED** | CCX-160 stub |
| 44 | Wisdom loop closure (Learning → Wisdom) | **APPROVED** | CCX-161 design |

**Decision counts:** **23 APPROVED** · **10 DEFERRED** · **10 REJECTED**

---

## 3. Biggest Mistakes / Overengineering / Missed Opportunities

### Architectural mistakes (condensed)

| Mistake | Evidence | IC action |
|---------|----------|-----------|
| Engines without loop closure | IO/Alpha born; belief stub only | **APPROVED** Belief Review first |
| Portfolio split-brain | Client localStorage vs server | **APPROVED** Portfolio SSOT |
| Sprint modules shipped unwired | forward_outcomes had zero callers (fixed) | Rule: no module without consumer + test |
| Discovery as peer nav tab | Attention sink | **APPROVED** demotion |
| Doc sprawl then rescue | 66 files archived | ADR-013 enforced |
| Mock/synthetic near live labels | False confidence | **APPROVED** CCX-008 |

### Overengineering (condensed)

| Area | Overbuilt | Should have built |
|------|-----------|-------------------|
| Object factories | Full IO/Alpha schemas | Belief review + 3 fields |
| Seven-engine taxonomy | Architecture docs | Three loops: Decide, Learn, Remember |
| Meta Intelligence v15 | Full engine design | Usage log + monthly delete list |
| Guide content | Reference competing with mission | External wiki (demoted — keep) |

### Missed opportunities (condensed)

1. Override journal → trust map (not productized) → **APPROVED**
2. Silence as first-class WAIT mode (partial) → **APPROVED** deletion batch
3. Calibration from forward outcomes (marks exist, no report) → **APPROVED**
4. Knowledge retrieval before scan (write-only graph) → **APPROVED**
5. Marginal ROC as daily gate (backlog only) → **APPROVED**
6. Monthly deletion ceremony (MIE specifies, not enforced) → **APPROVED** MIE Phase 1
7. One improvement per month (90-item backlog) → backlog P0 cap enforced

---

## 4. Engineering Investment Portfolio

Each item is a capital allocation. **Only APPROVED items are sprint-eligible at P0.**

---

### P-001 — Belief Review Ritual

| Field | Value |
|-------|-------|
| **Priority** | P0 |
| **Expected Value** | ★★★★★ |
| **Risk** | Low |
| **Time** | 3 eng weeks |
| **Dependency** | CCX-041 forward outcomes (done) |
| **Kill Criteria** | If calibration (Brier) does not improve after two quarters, redesign thesis/kill UX |
| **Owner** | Core |
| **Quarter** | Q3 2026 |
| **Review Date** | 2026-11-25 |
| **Success Metric** | ≥80% of deploys contain completed Belief Review before handoff |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Alpha Factory artifacts, IO schema expansion, Evolution Dashboard UI |
| **Behavior Change** | Current: deploy without logged thesis/kill → Desired: no deploy without belief record → Evidence: Ops belief panel populated → Metric: deploy-with-belief % |
| **Decision Quality** | Increases correct (thesis-aligned) deploys; reduces impulsive entries; measured via forward outcome grade vs stated conviction |

**Backlog:** CCX-131, CCX-135

---

### P-002 — Marginal ROC Panel

| Field | Value |
|-------|-------|
| **Priority** | P0 |
| **Expected Value** | ★★★★★ |
| **Risk** | Low |
| **Time** | 2.5 eng weeks |
| **Dependency** | Portfolio SSOT (P-004) partial |
| **Kill Criteria** | If operator ignores panel 90 consecutive days, merge into Mission Brief one-liner |
| **Owner** | Core |
| **Quarter** | Q3 2026 |
| **Review Date** | 2026-11-25 |
| **Success Metric** | Marginal ROC consulted on ≥70% of TRADE days |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | EV Ranking 3.0 decomposition, Capital Allocation panel polish |
| **Behavior Change** | Current: size by rank → Desired: size by marginal return on capital → Evidence: trim/add actions cite ROC → Metric: trap-hold duration ↓ 25% |
| **Decision Quality** | Reduces capital trapped in low-ROC positions; increases correct trim timing; measured via post-trim forward outcomes |

**Backlog:** CCX-053

---

### P-003 — WAIT-Day Silence / Deletion Batch

| Field | Value |
|-------|-------|
| **Priority** | P0 |
| **Expected Value** | ★★★★☆ |
| **Risk** | Low |
| **Time** | 1 eng week |
| **Dependency** | CCX-UX-07 (done) |
| **Kill Criteria** | If Mission Brief engagement drops on WAIT days, restore one secondary strip only |
| **Owner** | UX |
| **Quarter** | Q3 2026 |
| **Review Date** | 2026-10-25 |
| **Success Metric** | WAIT-day session time ↓ 40%; duplicate banner count = 0 |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Buffett/thematic strips, rank #1 hero, redundant gate banners |
| **Behavior Change** | Current: browse rank on WAIT → Desired: read Mission Brief, close app → Evidence: delta-only CIIO → Metric: Discovery opens on WAIT ↓ 40% |
| **Decision Quality** | Reduces incorrect "action for action's sake" trades; measured via WAIT-day deploy attempt rate (should stay ~0) |

**Backlog:** CCX-UX-07 (extend), Silence Engine

---

### P-004 — Portfolio SSOT

| Field | Value |
|-------|-------|
| **Priority** | P0 |
| **Expected Value** | ★★★★★ |
| **Risk** | Medium |
| **Time** | 2 eng weeks |
| **Dependency** | None |
| **Kill Criteria** | If migration causes >1 session data loss incident, rollback with explicit degraded banner |
| **Owner** | Core |
| **Quarter** | Q3 2026 |
| **Review Date** | 2026-10-25 |
| **Success Metric** | 100% holdings read from server; localStorage portfolio writes = 0 |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Portfolio settings UX polish, rebalance sim embed |
| **Behavior Change** | Current: client/server holdings diverge → Desired: one book truth → Evidence: sizing matches IBKR → Metric: holdings mismatch incidents = 0 |
| **Decision Quality** | Reduces incorrect sizing from stale local state; measured via pre-deploy holdings audit pass rate |

**Backlog:** _new row or CCX-109 extension_

---

### P-005 — Knowledge Retrieval

| Field | Value |
|-------|-------|
| **Priority** | P0 |
| **Expected Value** | ★★★★☆ |
| **Risk** | Medium |
| **Time** | 2.5 eng weeks |
| **Dependency** | closed_trades.jsonl, forward_outcomes.jsonl |
| **Kill Criteria** | If retrieval shown but dismissed >90% for 60 days, reduce to one-line lesson only |
| **Owner** | Core |
| **Quarter** | Q4 2026 |
| **Review Date** | 2026-12-25 |
| **Success Metric** | Lesson card shown on ≥60% of ticker opens with prior history |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Knowledge Graph MVP, analog engine, thematic tagger |
| **Behavior Change** | Current: repeat mistakes on same ticker → Desired: prior lesson surfaces first → Evidence: "last time" card on dossier open → Metric: repeat-mistake rate ↓ |
| **Decision Quality** | Reduces incorrect re-entry on failed theses; measured via same-ticker loss streak length |

**Backlog:** CCX-073 (Research Memory index)

---

### P-006 — Calibration Quarterly Report

| Field | Value |
|-------|-------|
| **Priority** | P0 |
| **Expected Value** | ★★★★★ |
| **Risk** | Low |
| **Time** | 2 eng weeks |
| **Dependency** | CCX-041, P-001 Belief Review |
| **Kill Criteria** | If n<10 graded beliefs after two quarters, extend window; do not add UI complexity |
| **Owner** | Ops |
| **Quarter** | Q4 2026 |
| **Review Date** | 2026-12-25 |
| **Success Metric** | Quarterly Brier/ECE report generated; operator reviews within 7 days |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Real-Time Alpha Monitor KPIs, Council outcome tracking |
| **Behavior Change** | Current: confidence uncalibrated → Desired: quarterly honest grade → Evidence: Belief Report PDF/JSON → Metric: stated vs realized conviction correlation |
| **Decision Quality** | Increases calibration accuracy; reduces overconfidence; measured via Brier score trend |

**Backlog:** CCX-045, CCX-135

---

### P-007 — Override Journal + Cooldown

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Expected Value** | ★★★★☆ |
| **Risk** | Low |
| **Time** | 1.5 eng weeks |
| **Dependency** | CCX-133 trust feedback hook |
| **Kill Criteria** | If override rate <5% over 90 days, merge into Learning log only |
| **Owner** | Core |
| **Quarter** | Q4 2026 |
| **Review Date** | 2026-12-25 |
| **Success Metric** | 100% gate overrides logged with reason; cooldown enforced on repeat override |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Trust Engine Phase 2 automation |
| **Behavior Change** | Current: silent override → Desired: logged override + 24h cooldown → Evidence: override journal in Ops → Metric: repeat override without review ↓ |
| **Decision Quality** | Reduces incorrect habitual gate-breaking; measured via override outcome vs system recommendation |

**Backlog:** CCX-044, CCX-133

---

### P-008 — Trust-Weighted CIIO

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Expected Value** | ★★★★☆ |
| **Risk** | Low |
| **Time** | 2 eng weeks |
| **Dependency** | P-007 override journal |
| **Kill Criteria** | If CIIO word count does not ↓ 30% on WAIT days, revert to template-only |
| **Owner** | Core |
| **Quarter** | Q4 2026 |
| **Review Date** | 2026-12-25 |
| **Success Metric** | CIIO volume ↓ 30% on WAIT; trust score visible on brief |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | New AI narrative blocks, richer commentary |
| **Behavior Change** | Current: read long brief → Desired: read delta only → Evidence: collapsed AI on WAIT → Metric: brief read time ↓ 30% |
| **Decision Quality** | Reduces noise-driven decisions; measured via action rate after brief read |

**Backlog:** CCX-108 (extend)

---

### P-009 — Weekly IC Digest

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Expected Value** | ★★★★☆ |
| **Risk** | Low |
| **Time** | 1.5 eng weeks |
| **Dependency** | Mission Brief, forward outcomes |
| **Kill Criteria** | If digest unread 4 consecutive weeks, reduce to Telegram one-liner |
| **Owner** | Ops |
| **Quarter** | Q4 2026 |
| **Review Date** | 2026-12-25 |
| **Success Metric** | Weekly digest delivered; operator completes IC checklist ≥75% of weeks |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Monthly Evolution Report, Curiosity Engine |
| **Behavior Change** | Current: ad-hoc weekly review → Desired: structured IC ritual → Evidence: Sunday digest template → Metric: IC checklist completion rate |
| **Decision Quality** | Increases correct weekly posture shifts; measured via regime-aligned action rate |

**Backlog:** CCX-136

---

### P-010 — Forward Outcomes T+20 → Belief Grades

| Field | Value |
|-------|-------|
| **Priority** | P0 |
| **Expected Value** | ★★★★★ |
| **Risk** | Low |
| **Time** | 1 eng week |
| **Dependency** | CCX-041 (done) |
| **Kill Criteria** | If T+20 marks missing >20% of closes after 90 days, fix scheduler before Belief UI |
| **Owner** | Core |
| **Quarter** | Q3 2026 |
| **Review Date** | 2026-10-25 |
| **Success Metric** | ≥95% closes have T+20 mark; marks flow to Belief Review items |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Additional forward outcome horizons (T+60) |
| **Behavior Change** | Current: close and forget → Desired: close triggers grade → Evidence: belief item shows T+20 → Metric: beliefs with outcome grade % |
| **Decision Quality** | Closes learning loop; measured via conviction vs outcome correlation |

**Backlog:** CCX-041 (extend), CCX-135

---

### P-011 — Discovery Demotion

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Expected Value** | ★★★☆☆ |
| **Risk** | Low |
| **Time** | 0.5 eng weeks |
| **Dependency** | Mission Control attention queue |
| **Kill Criteria** | If monitor promotion rate drops >50% vs baseline, restore Discovery nav with badge only |
| **Owner** | UX |
| **Quarter** | Q3 2026 |
| **Review Date** | 2026-10-25 |
| **Success Metric** | Discovery as non-equal nav; opens ↓ 40%; attention queue promotion unchanged |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Discovery theme clustering, more filters |
| **Behavior Change** | Current: open Discovery first → Desired: Mission Control first → Evidence: CIIO routes candidates → Metric: Discovery session starts ↓ 40% |
| **Decision Quality** | Reduces browse-without-gate behavior; measured via Discovery→deploy conversion vs Mission path |

**Backlog:** _UX nav change_

---

### P-012 — Meta Intelligence Phase 1 (Usage Log Only)

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Expected Value** | ★★★☆☆ |
| **Risk** | Low |
| **Time** | 1.5 eng weeks |
| **Dependency** | None |
| **Kill Criteria** | If log volume <100 events/week after 60 days, pause MIE entirely |
| **Owner** | Ops |
| **Quarter** | Q4 2026 |
| **Review Date** | 2026-12-25 |
| **Success Metric** | Surface dwell + dismiss events in JSONL; monthly delete list generated |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Evolution Dashboard UI, Attention Cost scoring, Curiosity Engine |
| **Behavior Change** | Current: build features blind → Desired: delete by evidence → Evidence: usage/ignore log → Metric: surfaces deleted per quarter ≥3 |
| **Decision Quality** | Reduces building unused features; measured via feature dwell vs dismiss ratio |

**Backlog:** CCX-132, CCX-133

---

### P-013 — Evolution Dashboard UI

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Expected Value** | ★★☆☆☆ |
| **Risk** | Medium |
| **Time** | 2 eng weeks |
| **Dependency** | P-012 usage log (60 days data) |
| **Kill Criteria** | If dashboard not opened in 30 days after launch, delete panel |
| **Owner** | Ops |
| **Quarter** | Q1 2027 |
| **Review Date** | 2027-03-25 |
| **Success Metric** | Monthly SER completed using dashboard |
| **Decision** | **DEFERRED** |
| **Opportunity Cost** | Belief Review polish, calibration report |
| **Behavior Change** | N/A until deferred criteria met |
| **Decision Quality** | N/A until telemetry proves need |

**Backlog:** CCX-134

---

### P-014 — New AI Narrative Features

| Field | Value |
|-------|-------|
| **Priority** | — |
| **Expected Value** | ★☆☆☆☆ |
| **Risk** | High (false confidence) |
| **Time** | — |
| **Dependency** | — |
| **Kill Criteria** | N/A — rejected at birth |
| **Owner** | — |
| **Quarter** | — |
| **Review Date** | — |
| **Success Metric** | — |
| **Decision** | **REJECTED** |
| **Opportunity Cost** | Would consume Belief Review, calibration, silence work |
| **Behavior Change** | Current: read AI prose → Desired: read proven facts only → Evidence: CCX-108 demotion → Metric: AI block expand rate |
| **Decision Quality** | Unproven; reject until calibration proves AI improves decisions |

---

### P-015 — More Discovery Filters

| Field | Value |
|-------|-------|
| **Priority** | — |
| **Expected Value** | ★☆☆☆☆ |
| **Risk** | High (attention sink) |
| **Time** | — |
| **Dependency** | — |
| **Kill Criteria** | N/A — rejected at birth |
| **Owner** | — |
| **Quarter** | — |
| **Review Date** | — |
| **Success Metric** | — |
| **Decision** | **REJECTED** |
| **Opportunity Cost** | Discovery demotion, Mission Control attention queue |
| **Behavior Change** | Filters increase browse time without gate integration |
| **Decision Quality** | Negative ROI; increases incorrect "found something" urgency |

---

### P-016 — Playwright E2E Breadth

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Expected Value** | ★★★☆☆ |
| **Risk** | Low |
| **Time** | 2 eng weeks |
| **Dependency** | CCX-007 CI gate foundation |
| **Kill Criteria** | If E2E flaky >10% of runs, reduce to WAIT→deploy-disabled only |
| **Owner** | Ops |
| **Quarter** | Q1 2027 |
| **Review Date** | 2027-03-25 |
| **Success Metric** | E2E WAIT path green in CI |
| **Decision** | **DEFERRED** |
| **Opportunity Cost** | Belief loop integration tests |
| **Behavior Change** | N/A — infrastructure |
| **Decision Quality** | Protects authority regressions when implemented |

**Backlog:** CCX-090

---

### P-017 — Attribution Root Ref

| Field | Value |
|-------|-------|
| **Priority** | P0 |
| **Expected Value** | ★★★★☆ |
| **Risk** | Low |
| **Time** | 1 eng week |
| **Dependency** | Decision board SSOT (done) |
| **Kill Criteria** | If chain breaks on >5% of rows, block release |
| **Owner** | Core |
| **Quarter** | Q3 2026 |
| **Review Date** | 2026-10-25 |
| **Success Metric** | 100% board rows have attribution_root_ref |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Attribution tree E2E export |
| **Behavior Change** | Current: orphan decisions → Desired: PnL traceable to belief → Evidence: decision_id on row → Metric: attribution chain completeness |
| **Decision Quality** | Enables correct post-mortems; measured via audit export success rate |

**Backlog:** CCX-005

---

### P-018 — Mandatory Provenance on Prices

| Field | Value |
|-------|-------|
| **Priority** | P0 |
| **Expected Value** | ★★★★☆ |
| **Risk** | Low |
| **Time** | 1.5 eng weeks |
| **Dependency** | CCX-UX-06 |
| **Kill Criteria** | If STALE rate >15% during market hours for 5 days, escalate data feed not hide badge |
| **Owner** | Core |
| **Quarter** | Q3 2026 |
| **Review Date** | 2026-10-25 |
| **Success Metric** | 100% price fields labeled; STALE hides deploy CTAs |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Dossier instant core perf |
| **Behavior Change** | Current: trade on stale price → Desired: STALE = no deploy → Evidence: provenance strip → Metric: deploy on STALE = 0 |
| **Decision Quality** | Reduces incorrect entries on stale data |

**Backlog:** CCX-006, CCX-UX-06

---

### P-019 — CI Authority Regression Gate

| Field | Value |
|-------|-------|
| **Priority** | P0 |
| **Expected Value** | ★★★★★ |
| **Risk** | Low |
| **Time** | 1 eng week |
| **Dependency** | Existing pytest authority suite |
| **Kill Criteria** | N/A — permanent infrastructure |
| **Owner** | Ops |
| **Quarter** | Q3 2026 |
| **Review Date** | 2026-10-25 |
| **Success Metric** | verify_10_10.sh blocks PR on authority regression |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Walk-forward CI, k6 perf gates |
| **Behavior Change** | N/A — protects moat |
| **Decision Quality** | Prevents incorrect deploy path reintroduction |

**Backlog:** CCX-007

---

### P-020 — Today PM Strip Parity

| Field | Value |
|-------|-------|
| **Priority** | P0 |
| **Expected Value** | ★★★★☆ |
| **Risk** | Low |
| **Time** | 1 eng week |
| **Dependency** | CCX-001 (done) |
| **Kill Criteria** | If best_action diverges from board >5% of polls, fix SSOT not add UI |
| **Owner** | UX |
| **Quarter** | Q3 2026 |
| **Review Date** | 2026-10-25 |
| **Success Metric** | 5-second deploy/wait/monitor answer on Today |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Command tab sync, near-miss triggers |
| **Behavior Change** | Current: hunt for answer across strips → Desired: one PM strip → Evidence: best_action SSOT → Metric: time-to-decision ↓ |
| **Decision Quality** | Increases correct first-glance posture |

**Backlog:** CCX-UX-04

---

### P-021 — Decision Journal (IDOS Phase 1)

| Field | Value |
|-------|-------|
| **Priority** | **P0 APPROVED** |
| **Expected Value** | ★★★★★ |
| **Risk** | Low |
| **Time** | 2 eng weeks |
| **Dependency** | decision_id on board rows (CCX-005 partial) |
| **Kill Criteria** | If <50% deploy/wait days have journal row after 90d, redesign UX |
| **Owner** | Core |
| **Quarter** | Q3 2026 |
| **Review Date** | 2026-11-25 |
| **Success Metric** | Pre-outcome entry before every deploy AND explicit wait |
| **Decision** | **APPROVED** |
| **Opportunity Cost** | Red Team full UI, legacy journal merge (CCX-044) |
| **Behavior Change** | Current: post-hoc stories → Desired: thesis before outcome → Evidence: JSONL + Ops panel |
| **Decision Quality** | Decision → Outcome → Learning (never Outcome → Explanation) |

**Backlog:** CCX-156

---

### P-022 — Red Team Engine (stub → full)

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Expected Value** | ★★★★☆ |
| **Risk** | Low (stub) |
| **Time** | 1 eng week stub · 3 weeks full |
| **Dependency** | CCX-156 journal |
| **Kill Criteria** | Theater-only AI without checklist → delete |
| **Owner** | Core |
| **Quarter** | Q3 2026 |
| **Review Date** | 2026-12-25 |
| **Success Metric** | Five challenges answered before deploy intent |
| **Decision** | **APPROVED** (stub) |
| **Opportunity Cost** | Committee full automation |
| **Behavior Change** | Pre-mortem before deploy |
| **Decision Quality** | Reduces inside-view deploys |

**Backlog:** CCX-157

---

### P-023 — Outside View Engine (stub)

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Expected Value** | ★★★★☆ |
| **Risk** | Low |
| **Time** | 1 eng week stub |
| **Dependency** | Calibration data (CCX-045) |
| **Kill Criteria** | Base rates without sample floors → defer |
| **Owner** | Quant |
| **Quarter** | Q4 2026 |
| **Review Date** | 2026-12-25 |
| **Success Metric** | Thesis compared to class prior on deploy review |
| **Decision** | **APPROVED** (stub) |
| **Opportunity Cost** | EV rank expansion |
| **Behavior Change** | Inside view challenged by class base rate |
| **Decision Quality** | Calibrates conviction |

**Backlog:** CCX-158

---

### P-024 — Decision Committee (stub)

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Expected Value** | ★★★☆☆ |
| **Risk** | Low |
| **Time** | 1 eng week stub |
| **Dependency** | CCX-156 |
| **Kill Criteria** | Auto-approve from committee → reject feature |
| **Owner** | Core |
| **Quarter** | Q4 2026 |
| **Review Date** | 2026-12-25 |
| **Success Metric** | Dissent logged on deploy review |
| **Decision** | **APPROVED** (stub) |
| **Opportunity Cost** | Full committee UI |
| **Behavior Change** | Virtual members challenge; human decides |
| **Decision Quality** | Surfaces opposing views |

**Backlog:** CCX-159

---

### P-025 — Decision Health (stub)

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Expected Value** | ★★★☆☆ |
| **Risk** | Low |
| **Time** | 0.5 eng week stub |
| **Dependency** | None |
| **Kill Criteria** | Used as deploy gate → delete |
| **Owner** | Core |
| **Quarter** | Q4 2026 |
| **Review Date** | 2027-01-25 |
| **Success Metric** | Self-report before deploy on TRADE days |
| **Decision** | **APPROVED** (stub, non-blocking) |
| **Opportunity Cost** | Behavioral rules engine |
| **Behavior Change** | Honest rushed/emotional/distracted inputs |
| **Decision Quality** | Calibration inputs only |

**Backlog:** CCX-160

---

### P-026 — Wisdom Loop Closure

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Expected Value** | ★★★★★ (30-year) |
| **Risk** | Medium |
| **Time** | 4 eng weeks |
| **Dependency** | CCX-156 Phase 2 |
| **Kill Criteria** | Wisdom docs without journal data → defer |
| **Owner** | Core |
| **Quarter** | Q1 2027 |
| **Review Date** | 2027-03-25 |
| **Success Metric** | Quarterly wisdom review from journal + outcomes |
| **Decision** | **APPROVED** (design) |
| **Opportunity Cost** | New engine features |
| **Behavior Change** | Operator character compounds |
| **Decision Quality** | Pyramid top: Learning → **Wisdom** |

**Backlog:** CCX-161

---

**Portfolio decision counts:** **21 APPROVED** · **2 DEFERRED** · **2 REJECTED** (in portfolio section; IC table is authoritative superset)

---

## 5. Kill Criteria

### Template (required for every APPROVED feature)

```
Why should this feature exist?
  → [Decision quality or behavior change it enables]

How do we know it works?
  → [Success metric + measurement cadence]

When do we delete it?
  → [Kill criteria — time, usage, or calibration threshold]
```

### Per-feature kill / merge / keep rules

| Feature | Keep if | Merge if | Delete if |
|---------|---------|----------|-----------|
| **Trust Engine** | Trust calibration (Brier/ECE) improves quarter-over-quarter | CIIO can absorb trust score in one line | Operator ignores trust signals 180 consecutive days |
| **Belief Review** | Deploy-with-belief ≥80%; calibration improves | Into Learning exit review only | Calibration flat 2 quarters after full UI |
| **Marginal ROC panel** | Consulted ≥70% TRADE days; trap-hold ↓ | Into Mission Brief one-liner | Ignored 90 consecutive days |
| **Discovery tab** | Monitor promotion rate maintained after demotion | Into Attention queue only (no tab) | Opens still >baseline after demotion + routing |
| **Evolution Dashboard** | Opened ≥1×/month; drives ≥3 deletions/quarter | Into Firm Health Ops tab | Not opened 30 days post-launch |
| **CIIO narrative** | Brief read time ↓; action quality ↑ | Into Mission Brief template | Word count ↑ on WAIT; override rate ↑ |
| **Knowledge Graph** | Retrieval dismiss <90%; repeat-mistake ↓ | Into lesson cards on dossier | Write-only with zero retrieval 180 days |
| **Playwright E2E** | Flaky <10%; catches ≥1 regression/quarter | Into authority pytest fixture only | Flaky >25% after 2 fix attempts |
| **Meta Intelligence** | ≥3 surfaces deleted/quarter from usage log | Into Review Cycle doc only | <100 events/week after 60 days |
| **Guide tab** | Reference lookups ≥2/week | External wiki link | Zero lookups 90 days |

---

## 6. Ten Deletions

Each deletion is **APPROVED**. No replacement UI without IC re-vote.

| # | Delete | Kill Criteria | Decision |
|---|--------|---------------|----------|
| 1 | Rank #1 hero card on WAIT days | Mission Brief engagement maintained | **APPROVED** |
| 2 | Duplicate WAIT/gate banners | Single Mission Control banner remains | **APPROVED** |
| 3 | Default-visible Buffett/thematic strips on WAIT | Operator feedback neutral or positive | **APPROVED** |
| 4 | Discovery as top-level equal nav | Attention queue promotion rate stable | **APPROVED** |
| 5 | Synthetic flow/insider without SIMULATED label | CCX-107 watermark deployed | **APPROVED** |
| 6 | Redundant broker status strips | Broker status visible in one location | **APPROVED** |
| 7 | AI narrative blocks without provenance | CCX-108 collapsed by default | **APPROVED** |
| 8 | Duplicate CCX backlog rows | Process: one ID per item enforced | **APPROVED** |
| 9 | Unused sprint module exports (zero callers) | CI import audit clean | **APPROVED** |
| 10 | Alerts with 100% dismiss rate (after 90d telemetry) | CCX-132 usage log active | **APPROVED** |

---

## 7. Ten Simplifications

Each simplification includes a **behavior change metric**.

| # | Simplify | Behavior Change Metric | Decision |
|---|----------|------------------------|----------|
| 1 | Mission Control + Opportunity Verdict → one mission card | Time-to-mission answer ↓ 50% | **APPROVED** |
| 2 | Regime/crisis/index strips → one expand drawer | Strip count above fold ↓ from 4+ to 1 | **APPROVED** |
| 3 | Confidence/trust/quality pills → one calibrated line | Pill count per row ↓ 66% | **APPROVED** |
| 4 | Today + Command best_action → one mission SSOT | best_action divergence = 0% | **APPROVED** |
| 5 | Near-miss + watchlist + triggers → monitor queue | Queue entry points ↓ from 3 to 1 | **APPROVED** |
| 6 | Seven engines in operator UI → **KNOW → BELIEVE → DOUBT → ACT** | Operator vocabulary = Four Questions only | **APPROVED** |
| 7 | Guide → external or bottom nav only | Guide opens on decision tabs = 0 | **APPROVED** |
| 8 | Settings → display prefs only | Settings affecting deploy logic = 0 | **APPROVED** |
| 9 | Playbook row → Rank · Quality · Authority above fold | Fields above fold ↓ from 8+ to 3 | **APPROVED** |
| 10 | Cadence docs v10–v16 → Constitution + Firm OS + Meta (3) | Active design prompts = 3 | **APPROVED** |

---

## 8. Ten Merges

Each merge includes **opportunity cost** (what we NOT build separately).

| # | Merge | Into | Opportunity Cost | Decision |
|---|-------|------|------------------|----------|
| 1 | Attention Engine + Discovery entry | CIIO-routed queue | Separate Discovery filters, theme clustering | **APPROVED** |
| 2 | Belief Engine + Learning exit review | Belief Review ritual | Duplicate post-trade forms | **APPROVED** |
| 3 | Knowledge Engine + Learning lessons | Lesson cards with retrieval | Standalone Knowledge tab | **APPROVED** |
| 4 | Meta Intelligence + Review Cycle | Monthly System Evolution | Separate MIE review doc | **APPROVED** |
| 5 | Alpha Flywheel + v16 cadences | Firm operating calendar | Duplicate cadence stubs | **APPROVED** |
| 6 | forward_outcomes + calibration | Quarterly Belief Report | T+60/T+90 horizons | **APPROVED** |
| 7 | Portfolio local + server holdings | Server SSOT | Rebalance sim, crisis stress UI | **APPROVED** |
| 8 | cost_adjusted_ranker + opportunity_pipeline | Shared pipeline (done) | Re-splitting rank paths | **APPROVED** |
| 9 | Ops panels (belief + evolution + cadence) | Firm Health Ops tab | Three separate Ops panels | **APPROVED** |
| 10 | test_operator_mode_ux + deploy SSOT grep | Shared authority test fixture | Duplicate grep tests | **APPROVED** |

---

## 9. Engineering Capital Allocation (100 Points)

Rejected items receive **0 points**. Total must equal 100.

| Area | Points | Status |
|------|--------|--------|
| Belief loop closure (P-001, P-010) | 20 | APPROVED |
| Capital / marginal ROC (P-002) | 18 | APPROVED |
| Deletions + simplification (§6–7) | 15 | APPROVED |
| Portfolio SSOT (P-004) | 10 | APPROVED |
| Calibration + forward outcomes (P-006) | 10 | APPROVED |
| Knowledge retrieval (P-005) | 10 | APPROVED |
| Silence + attention ROI (P-003, P-011) | 8 | APPROVED |
| Trust-weighted CIIO (P-008) | 5 | APPROVED |
| Firm cadence templates (P-009) | 4 | APPROVED |
| **New features / engines / data feeds** | **0** | REJECTED |
| Evolution Dashboard UI | 0 | DEFERRED |
| Playwright E2E breadth | 0 | DEFERRED |
| Knowledge Graph MVP | 0 | DEFERRED |
| New AI narrative | 0 | REJECTED |
| More discovery filters | 0 | REJECTED |
| Enterprise RBAC | 0 | REJECTED |
| **Total** | **100** | |

---

## 10. Updated Roadmap

### Classification

| Class | Items |
|-------|-------|
| **KEEP** | All APPROVED portfolio items (P-001–P-012, P-017–P-020) |
| **DEFER** | P-013 Evolution Dashboard · P-016 Playwright breadth · CCX-126 IO migration · CCX-070 KG · CCX-025 Research Workspace · CCX-100 Command palette |
| **MERGE** | CCX-132–134 → usage + trust + monthly delete · Cadence stubs → Firm Health · forward_outcomes → Belief Report |
| **DELETE** | §6 ten deletions · duplicate backlog rows · unused exports |
| **REJECTED** | P-014 AI narrative · P-015 Discovery filters · CCX-120 RBAC · auto bracket · ML auto-apply |

### Six-month execution (APPROVED only)

| Month | Focus | Deliverables |
|-------|-------|--------------|
| 1–2 | Loop closure | Belief Review full · Marginal ROC · Portfolio SSOT · Deletion batch 1 |
| 3–4 | Measurement | Calibration quarterly · Knowledge retrieval · Override journal · Silence default |
| 5–6 | Firm cadence | Weekly IC digest · MIE Phase 1 usage log · Quarterly belief trial |

---

## 11. Product Philosophy

### Hierarchy: Decision Quality → Behavior Change → Identity Change

| Layer | What it means | How CC measures it |
|-------|---------------|-------------------|
| **Decision Quality** | Correct deploy/hold/trim under uncertainty | Brier, forward outcomes, override rate |
| **Behavior Change** | Operator habits shift (Mission first, silence on WAIT) | Session paths, Discovery opens, deploy-with-belief % |
| **Identity Change** | After 30 years, the investor *is* disciplined — with or without CC | Investment Partner Test (§14) |

**Old implicit philosophy:** Build the world's smartest investment dashboard.

**New explicit philosophy:**

> CC exists to make the operator progressively less dependent on CC itself by transforming disciplined thinking into lasting habit.

**Product laws:**
1. No surface without answering at least one Four Question
2. No surface without a decision it changes
3. No engine without a loop it closes
3. No addition without a deletion
4. No deploy path outside Decision Engine + human
5. No metric without an action
6. Silence is a shipped feature
7. Cash is a first-class outcome
8. Complexity index must trend down
9. Trust is earned, not asserted
10. The operator's calibration curve is the product scorecard

---

## 12. If Started Again Today

**Build first (90 days):**
1. Decision board + deploy gates only
2. Mission Control (5 fields)
3. Belief log (thesis, kill, conviction) linked to every deploy
4. Portfolio SSOT + marginal ROC
5. Learning log + forward outcome marks
6. One CIIO voice — delta-only on WAIT

**Would NOT build early:**
- Seven-engine taxonomy in UI
- Full IO/Alpha object schemas
- Discovery tab
- Knowledge graph
- Meta Intelligence dashboard
- Multiple rank contexts
- Guide inside app

**Architecture choice:** Monolith service with **three domains** — Decide, Learn, Remember — not nine engines.

---

## 13. What Should Never Change

1. Human deploy authority
2. Page Gate > Card Rank
3. Research ≠ deploy authority
4. deploy_open as sole deploy signal
5. Fail-closed on regime/uncertainty
6. Quality tier never grants deploy
7. Process review on wins and losses
8. Beliefs before capital
9. Kill conditions logged at birth
10. One PM, one firm — no complexity to simulate scale
11. The Constitution
12. Purpose: better decisions, less effort — expressed as habit formation (§14)

---

## 14. THE INVESTMENT PARTNER TEST

Assume CC disappears tomorrow.

**Could the operator still think the same way?**

If **yes** — CC has **failed**. The operator should not need the software to be disciplined. CC should teach better judgment, not dependence.

**Success is measured by what remains after CC is gone:**
- Written beliefs with kill conditions
- Calibration habits (quarterly honest grading)
- Silence on WAIT days (no action for action's sake)
- Marginal ROC thinking before every capital move
- Override awareness (know when you broke your own rules)
- Lesson retrieval (check prior mistakes before re-entry)

The operator should become **more independent, more disciplined, more calibrated, and more patient** every year — not more tethered to a dashboard.

CC is a **training partner**, not a **crutch**. When the training works, the partner becomes unnecessary for daily discipline — only for data and execution plumbing.

---


## 14. IDOS maturity — Decision Quality Pyramid (ADR-023)

**Optimize:** Decision Quality → Decision Process → **Investor Character**. After 30 years the product is who the operator became.

**Pyramid:** Information → Understanding → Belief → Decision → Execution → Outcome → Learning → **Wisdom**

CC previously ended at Learning; five IDOS capabilities close toward Wisdom.

| Layer | Score | Notes |
|-------|------:|-------|
| Architecture | 10 | Authority SSOT, living docs |
| Authority | 10 | Human deploy only; `deploy_open` SSOT |
| Constitution | 10 | Resolution + Four Questions |
| CIIO | 10 | Mission Brief + gate discipline |
| Alpha Flywheel | 10 | Forward outcomes → belief review |
| Meta Intelligence | 10 | Question-lift scoring design |
| Decision Journal | Missing → **Phase 1** | CCX-156 P0 APPROVED |
| Red Team · Outside View · Committee · Health | Missing → **stubs** | CCX-157–160 |
| Wisdom loop | Missing → design | CCX-161 |

Flow: **Decision → Outcome → Learning** — journal entries written **before** outcome known.

---

## 15. Meta Intelligence reframe (ADR-022)

Instead of "which engine improved?" ask: **Which question became easier to answer?**

Monthly System Evolution Review scores each surface by question lift (Q1–Q4). Example format → [`CC_X_META_INTELLIGENCE.md`](./CC_X_META_INTELLIGENCE.md) § Monthly review (Four Questions).

| Surface / change | Q1 Know | Q2 Believe | Q3 Doubt | Q4 Act | Verdict |
|------------------|---------|------------|----------|--------|---------|
| Mission Brief rewrite | ↑ | — | ↑ | ↑ | Keep |
| Rank hero on WAIT days | — | ↓ | — | ↓ | Delete |
| Belief Review stub | — | ↑ | ↑ | — | Extend |

---

## 16. Engineering & PR gate

Before any feature or PR, the author must answer convincingly:

1. **What do we know better because of this?** (Q1)
2. **What uncertainty does it reduce?** (Q3)
3. **How does it improve future capital allocation?** (Q4)
4. **What existing complexity can be removed because of it?**

If not convincingly answered → **reject**.

**Proposal review (reject if none):** Reduces uncertainty? · Improves judgment? · Improves capital allocation? · Improves future learning?

Enforcement: [`.github/pull_request_template.md`](../.github/pull_request_template.md) · [`AGENTS.md`](../AGENTS.md) · backlog PR gate banner.

---


## 17. Final Sentences

**The market is uncertain. Our process should not be. CC exists to help the operator continuously reduce avoidable uncertainty before risking irrecoverable capital.**

**Progressive independence.** The purpose of CC is to make the operator progressively less dependent on CC itself by transforming disciplined thinking into lasting habit.

---

*Next review: quarterly Engineering IC ritual — see [`CC_X_REVIEW_CYCLE.md`](./CC_X_REVIEW_CYCLE.md). Backlog P0 reordered to APPROVED items only — see [`CC_X_ENGINEERING_BACKLOG.md`](./CC_X_ENGINEERING_BACKLOG.md).*
