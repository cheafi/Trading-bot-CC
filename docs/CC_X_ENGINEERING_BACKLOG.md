# CC X — Engineering Backlog (Living SSOT)

**Product:** CC X · `TradingAI_Bot`  
**Last updated:** 2026-08-31 (Roadmap P0 complete — provenance, override/calibration/usage/weekly IC, Discovery demotion, CI gate)  
**Architecture:** [`CC_X_ARCHITECTURE.md`](./CC_X_ARCHITECTURE.md)  
**MIE design:** [`CC_X_META_INTELLIGENCE.md`](./CC_X_META_INTELLIGENCE.md)  
**Governance / PR gate:** [`CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md`](./CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md) — **binding**; P0 below matches APPROVED portfolio only  
**Sprint reference:** [`archive/CC_VNEXT_SPRINT_PLAN.md`](./archive/CC_VNEXT_SPRINT_PLAN.md), [`archive/CC_X_INSTITUTIONAL_ALPHA_OS.md`](./archive/CC_X_INSTITUTIONAL_ALPHA_OS.md)

> Single backlog for all CC X work. Future reviews add rows here — no new scored review docs. See [`CC_X_REVIEW_CYCLE.md`](./CC_X_REVIEW_CYCLE.md). **REJECTED** items (AI narrative, Discovery filters, RBAC) receive 0 points and must not be P0.

### PR gate (Four Questions — binding)

Before any feature/PR, author must answer convincingly (see Resolution):

1. What do we know better because of this? (**Q1**)
2. What uncertainty does it reduce? (**Q3**)
3. How does it improve future capital allocation? (**Q4**)
4. What existing complexity can be removed because of it?

Proposal review: reduces uncertainty? improves judgment? improves capital allocation? improves future learning? If not → reject.

P0 items include **Questions** served (Q1–Q4). A feature that serves none should not ship.

---

## P0 — Investment Committee APPROVED (execution order)

Reordered per [`CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md`](./CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md) §4. Only these items are sprint-eligible at P0 until next quarterly IC review.

| Order | ID | Item | Questions | Portfolio | Status |
|------:|----|------|-----------|-----------|--------|
| 0 | CCX-156 | **Decision Journal Phase 1** (JSONL + API + Ops) | Q2, Q3, Q4 | P-021 | **APPROVED / Phase 2 checklist** |
| 0a | CCX-162 | Pre-Decision Checklist (Phase 1 stub) | Q2, Q3, Q4 | P-028 | **done** |
| 0b | CCX-170 | Decision Cooling stub | Q3, Q4 | P-029 | **done** |
| 0c | CCX-171 | Research Queue stub | Q3, Q4 | P-030 | **done** |
| 1 | CCX-131 / CCX-135 | Belief Review ritual (Phase 2 thesis/kill) | Q2, Q3 | P-001 | in-progress |
| 2 | CCX-041 | Forward outcomes T+20 → belief grades | Q1, Q2 | P-010 | done (extend wiring) |
| 3 | CCX-053 | Marginal ROC daily panel (stub API + strip) | Q1, Q4 | P-002 | **in-progress** (live wire portfolio+playbook) |
| 4 | _Portfolio SSOT_ | Server holdings truth (no localStorage split) | Q1 | P-004 | **done** (v7 endpoint + fallback banner) |
| 5 | CCX-UX-07 + deletions | WAIT-day silence / deletion batch 1 | Q3, Q4 | P-003 | done (hero hidden) |
| 6 | CCX-005 | Attribution root ref on all board rows | Q1, Q4 | P-017 | **done** |
| 7 | CCX-006 / CCX-UX-06 | Mandatory provenance on all prices | Q1 | P-018 | **done** |
| 8 | CCX-007 | CI blocks authority regressions | Q4 | P-019 | **done** |
| 9 | CCX-008 | Hide mock factor on deploy surfaces | Q1, Q3 | P-008 adj | **done** |
| 10 | CCX-UX-04 | Today PM strip parity (best action SSOT) | Q3, Q4 | P-020 | **done** |
| 11 | CCX-073 | Knowledge retrieval on ticker open | Q1, Q2 | P-005 | **done** |
| 12 | CCX-045 / CCX-135 | Calibration quarterly report | Q2, Q3 | P-006 | **done** |
| 13 | CCX-044 / CCX-133 | Override journal + cooldown | Q1, Q3 | P-007 | **done** |
| 14 | CCX-108 | Trust-weighted CIIO (speak less) | Q3 | P-008 | in-progress |
| 15 | CCX-136 | Weekly IC digest | Q1–Q4 | P-009 | **done** |
| 16 | CCX-132 | Meta Intelligence Phase 1 — usage log only | Q3 | P-012 | **done** |
| 17 | _Discovery demotion_ | Non-equal nav; route via Mission Control | Q4 | P-011 | **done** |

**DEFERRED from P0:** CCX-090 Playwright E2E · CCX-134 Evolution Dashboard · CCX-126 IO migration · CCX-070 Knowledge Graph · CCX-025 Research Workspace

**REJECTED (0 points):** New AI narrative · More Discovery filters · CCX-120/122 Enterprise RBAC

---

## In-flight UX (current sprint)

| ID        | Item                                                        | Priority | Questions | Status      | Owner   | Sprint | Acceptance criteria                                                                           | Evidence/PR                                                              |
| --------- | ----------------------------------------------------------- | -------- | --------- | ----------- | ------- | ------ | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| CCX-UX-01 | Mission Brief panel — bilingual NOW/BLOCKER/NEXT            | P1       | Q3, Q4    | done        | CC Core | 115    | `[data-cc="today-mission-panel"]`; title "TODAY · Mission Brief · 今日任務"; WAIT copy honest | `4905a4e`, `cc-helpers.js`                                               |
| CCX-UX-02 | Opportunity quality on decision board regime block          | P1       | Q2, Q4    | done        | CC Core | 115    | `opportunity_quality` in board regime; Hostile macro consistency                              | `bf94f8e`, `decision_board_service.py`                                   |
| CCX-UX-03 | Opportunity quality chips on Playbook monitor cards         | P1       | Q2        | done        | CC Core | 115    | Quality tier visible; never implies deploy                                                    | `bf94f8e`, `opportunity_quality.py`, `tests/test_opportunity_quality.py` |
| CCX-UX-04 | Today PM strip — best action, near-miss, sleeve gate_status | P1       | Q3, Q4    | in-progress | CC Core | 115    | 5-second deploy/wait/monitor answers; board SSOT via `buildPmStripBoardLine` | `cc-app.js`, `cc-helpers.js`, `deploy_surfaces.html` |
| CCX-UX-05 | Guide tab as Help — suspended decision language             | P1       | Q4        | done        | CC Core | 115    | Guide shows reference-only; no deploy chips                                                   | `4905a4e`, `surface_authority.py`                                        |
| CCX-UX-06 | Provenance strip on price fields                            | P0       | Q1        | **done**        | CC Core | 116    | source/as_of/mode on prices; STALE hides deploy CTAs                                          | `cc-helpers.js`, `deploy_surfaces.html`, `opportunity_pipeline.py` |
| CCX-UX-07 | Today WAIT-day context collapse — Expand context            | P0       | Q3, Q4    | done        | CC Core | 115    | Mission Brief + Attention queue always visible; secondary strips behind expand on WAIT        | `deploy_surfaces.html`, `cc-app.js` `todayContextExpanded`               |
| CCX-UX-08 | Dashboard historical replay / decision demo (Phase 1)       | P1       | Q1, Q2    | **done**    | CC Core | —      | Extends time-travel; `GET /api/v7/replay/dashboard`; LIVE AUTHORITY: NONE                     | [`CC_HISTORICAL_DECISION_REPLAY.md`](./CC_HISTORICAL_DECISION_REPLAY.md) |

---

## Authority & decision

| ID       | Item                                                  | Priority | Questions | Status | Owner   | Sprint | Acceptance criteria                                                                         | Evidence/PR                                                      |
| -------- | ----------------------------------------------------- | -------- | --------- | ------ | ------- | ------ | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| CCX-001  | DecisionBoardService SSOT — all deploy surfaces       | P0       | Q4        | done   | CC Core | 115    | Today, Playbook, cc-header identical `deploy_open`; UI uses `system_state.deploy_open` only | `decision_board_service.py`, `cc-app.js` `deployOpen()`, Phase A |
| CCX-001b | Shared opportunity pipeline — Today + Playbook parity | P0       | Q1, Q2    | done   | CC Core | 115    | `finalize_opportunity_pipeline`; quality + IO/Alpha on both paths                           | `opportunity_pipeline.py`, `tests/test_opportunity_pipeline.py`  |
| CCX-002  | Never cache `deploy_open` on cached scan read         | P0       | Q4        | done   | CC Core | 115    | Authority fields recomputed on read                                                         | `8b51620`, `test_decision_board_authority_cache.py`              |
| CCX-003  | Fail-closed regime on router/service errors           | P0       | Q1, Q4    | done   | CC Core | 115    | Errors → WAIT; no optimistic TRADE                                                          | `8b51620`                                                        |
| CCX-004  | cc-header light mode honest deploy/regime             | P0       | Q1, Q4    | done   | CC Core | 115    | Header poll matches board                                                                   | `8b51620`, `test_cc_header_light.py`                             |
| CCX-005  | Attribution root ref on all board rows                | P0       | Q1, Q4    | **done**   | CC Core | 115    | Each row has `attribution_root_ref` / `decision_id`                                         | `opportunity_pipeline.py`, `decision_board_service.py` |
| CCX-006  | Mandatory provenance on all prices                    | P0       | Q1        | **done**   | CC Core | 116    | 100% price fields labeled; CI contract                                                      | `provenance_contract.py`, `opportunity_pipeline.py` |
| CCX-007  | CI blocks authority regressions                       | P0       | Q4        | **done**   | CC Core | 116    | CC X authority pytest gate on every PR                                                      | `.github/workflows/ci.yml` |
| CCX-008  | Hide mock factor on deploy surfaces                   | P0       | Q1, Q3    | **done**   | CC Core | 116    | degraded or hidden on Portfolio deploy                                                      | `cc-app.js` `hideMockSurfacesOnDeploy()`, dossier/portfolio |
| CCX-009  | Extract 25 largest main.py handlers                   | P1       | todo   | CC Core | 116    | Routes moved to routers                                                                     | Sprint 116                                                       |
| CCX-010  | Unified header poll                                   | P1       | todo   | CC Core | 116    | −40% API QPS                                                                                | Sprint 116                                                       |
| CCX-011  | Server-render authority labels                        | P2       | todo   | CC Core | 116    | Authority chip from API                                                                     | Sprint 116                                                       |
| CCX-012  | Near-miss consolidate in contract                     | P2       | todo   | CC Core | 115    | Single near_miss source                                                                     | Sprint 115                                                       |
| CCX-013  | Shared \_norm_action utility                          | P2       | todo   | CC Core | 115    | Dedupe action normalization                                                                 | Sprint 115                                                       |
| CCX-014  | Decision hub monitor payload unify                    | P2       | todo   | CC Core | 115    | One monitor poll path                                                                       | Sprint 115                                                       |

---

## Research & alpha factory

| ID      | Item                                    | Priority | Status | Owner   | Sprint | Acceptance criteria               | Evidence/PR |
| ------- | --------------------------------------- | -------- | ------ | ------- | ------ | --------------------------------- | ----------- |
| CCX-020 | Alpha Factory artifact per candidate    | P1       | todo   | CC Core | 117    | top-12 rows have `artifact_id`    | Sprint 117  |
| CCX-021 | AlphaObject birth at hypothesis         | P1       | todo   | CC Core | 117    | Scanner spawns valid AlphaObject  | Sprint 117  |
| CCX-022 | Playbook snapshot SWR p95 <2s           | P1       | todo   | CC Core | 117    | Cache hit p95; stale banner       | Sprint 117  |
| CCX-023 | artifact_id chain scan→dossier→playbook | P1       | todo   | CC Core | 117    | End-to-end linkage                | Sprint 117  |
| CCX-024 | Opportunity Intel v3 Dossier embed      | P1       | todo   | CC Core | 119    | Intel chips; research_only        | Sprint 119  |
| CCX-025 | Institutional Research Workspace MVP    | P1       | todo   | CC Core | 119    | Eleven tabs on IO + AlphaObject   | Sprint 119  |
| CCX-026 | InvestmentObject adapter (new paths)    | P1       | todo   | CC Core | 119    | Legacy rank fallback until parity | Sprint 119  |
| CCX-027 | Discovery theme clustering              | P2       | todo   | CC Core | 119    | Theme tags on Discovery           | Sprint 119  |
| CCX-028 | Scanner decay half-life chip            | P2       | todo   | CC Core | 119    | Stale scores penalized            | Sprint 119  |
| CCX-029 | Validation lab → playbook row link      | P2       | todo   | CC Core | 119    | Backtest grade never labeled live | Sprint 119  |
| CCX-030 | Explanation why on 90% playbook cards   | P2       | todo   | CC Core | 119    | Operator sentence on cards        | Sprint 119  |

---

## Learning & measured alpha

| ID      | Item                              | Priority | Status      | Owner   | Sprint | Acceptance criteria                                                      | Evidence/PR                                             |
| ------- | --------------------------------- | -------- | ----------- | ------- | ------ | ------------------------------------------------------------------------ | ------------------------------------------------------- |
| CCX-040 | IBKR → closed_trades.jsonl ≥95%   | P1       | todo        | CC Core | 118    | Nightly capture job                                                      | Sprint 118                                              |
| CCX-041 | Forward outcomes T+1/T+5/T+20     | P1       | done        | CC Core | 118    | `run_forward_outcome_marks`; scheduler 4:45 PM ET weekdays; T+0 on close | `forward_outcomes.py`, `scheduler/main.py`, `test_forward_outcomes_hook.py` |
| CCX-042 | Real-Time Alpha Monitor (6 KPIs)  | P1       | todo        | CC Core | 118    | Produced/Lost/Preserved in Ops                                           | Sprint 118                                              |
| CCX-043 | Thompson/ML hidden n<5 / n<30     | P1       | todo        | CC Core | 118    | Insufficient sample not shown as precision                               | Sprint 118                                              |
| CCX-044 | Merge decision journal SSOT       | P2       | todo        | CC Core | 118    | Single journal path                                                      | Sprint 118                                              |
| CCX-045 | Ops Alpha QA panel                | P2       | todo        | CC Core | 118    | IC decay, Brier visible                                                  | Sprint 118                                              |
| CCX-046 | Self-learning audit log UI        | P3       | todo        | CC Core | 118    | Apply rate visible; default 0                                            | Sprint 118                                              |
| CCX-047 | Regime params versioned changelog | P3       | todo        | CC Core | 118    | Threshold changes human-reviewed                                         | Sprint 118                                              |
| CCX-048 | Council outcome tracking          | P2       | todo        | CC Core | 118    | Council vs outcome calibration                                           | Sprint 118                                              |

---

## Portfolio & capital

| ID      | Item                                   | Priority | Status | Owner   | Sprint | Acceptance criteria                                     | Evidence/PR |
| ------- | -------------------------------------- | -------- | ------ | ------- | ------ | ------------------------------------------------------- | ----------- |
| CCX-050 | EV Ranking 3.0 decomposition           | P1       | todo   | CC Core | 122    | `ev_ranking.py`; research_only                          | Sprint 122  |
| CCX-051 | Capital Allocation panel               | P1       | todo   | CC Core | 122    | Next $10K ranked; no gate bypass                        | Sprint 122  |
| CCX-052 | Live factor wire (remove mock)         | P1       | todo   | CC Core | 122    | Real factor or explicit degraded                        | Sprint 122  |
| CCX-053 | marginal_return_on_capital on IO       | P0       | in-progress | CC Core | 122    | `/api/v7/capital/marginal-roc` stub + Mission Control/Portfolio panels; research_only | `marginal_roc.py`, Phase B |
| CCX-054 | Sector cap blocks portfolio quick-add  | P1       | todo   | CC Core | 122    | max_sector_pct enforced in UI                           | Sprint 122  |
| CCX-055 | Portfolio replacement rank             | P2       | todo   | CC Core | 124    | Sell-first ranked; human confirm                        | Sprint 124  |
| CCX-056 | sell_first_candidates[] on AlphaObject | P2       | todo   | CC Core | 124    | Swap discipline on IO                                   | Sprint 124  |
| CCX-057 | Portfolio brain IO consumer            | P2       | todo   | CC Core | 122    | Fit-delta sim uses IO                                   | Sprint 122  |
| CCX-058 | Crisis stress on portfolio tab         | P3       | todo   | CC Core | 122    | Regime stress visible                                   | Sprint 122  |
| CCX-059 | Drawdown sizer live wire               | P2       | todo   | CC Core | 122    | Sizing discipline in UI                                 | Sprint 122  |
| CCX-060 | Book-level capacity rollup             | P2       | todo   | CC Core | 122    | Aggregate capacity on book                              | Sprint 122  |
| CCX-061 | Rebalance sim portfolio embed          | P3       | todo   | CC Core | 122    | What-if in Portfolio tab                                | Sprint 122  |

---

## Knowledge & intelligence

| ID      | Item                                 | Priority | Status | Owner   | Sprint | Acceptance criteria                  | Evidence/PR |
| ------- | ------------------------------------ | -------- | ------ | ------- | ------ | ------------------------------------ | ----------- |
| CCX-070 | Knowledge Graph MVP                  | P1       | todo   | CC Core | 121    | `knowledge_graph.py`; neighbor API   | Sprint 121  |
| CCX-071 | Analog engine                        | P1       | todo   | CC Core | 121    | n≥5 or confidence low; research_only | Sprint 121  |
| CCX-072 | AlphaObject lifecycle close          | P2       | todo   | CC Core | 125    | CLOSED → ARCHIVED with lessons       | Sprint 125  |
| CCX-073 | Research Memory index                | P2       | todo   | CC Core | 125    | alpha_id → decision → outcome        | Sprint 125  |
| CCX-074 | Intelligence Engine daily report     | P2       | todo   | CC Core | 126    | Seven quality scores; research_only  | Sprint 126  |
| CCX-075 | Historical analog pattern library    | P2       | todo   | CC Core | 123    | Knowledge tab only                   | Sprint 123  |
| CCX-076 | failure_mode on AlphaObject lessons  | P3       | todo   | CC Core | 123    | Post-mortem fields                   | Sprint 123  |
| CCX-077 | Hidden thematic concentration tagger | P2       | todo   | CC Core | 121    | AI overlap detection                 | Sprint 121  |
| CCX-078 | Graph neighbor API                   | P2       | todo   | CC Core | 121    | `/api/v7/graph/neighbors/{ticker}`   | Sprint 121  |

---

## Attribution & export

| ID      | Item                           | Priority | Status | Owner   | Sprint  | Acceptance criteria              | Evidence/PR |
| ------- | ------------------------------ | -------- | ------ | ------- | ------- | -------------------------------- | ----------- |
| CCX-080 | Attribution tree E2E           | P1       | todo   | CC Core | 120,125 | PnL → Market Data chain          | Sprint 120  |
| CCX-081 | Board snapshot JSON/CSV export | P1       | todo   | CC Core | 120     | Export with authority disclaimer | Sprint 120  |
| CCX-082 | Alpha attribution tree export  | P2       | todo   | CC Core | 120     | Governance export                | Sprint 120  |

---

## Testing, CI, performance

| ID      | Item                                  | Priority | Status | Owner   | Sprint | Acceptance criteria      | Evidence/PR |
| ------- | ------------------------------------- | -------- | ------ | ------- | ------ | ------------------------ | ----------- |
| CCX-090 | Playwright E2E WAIT → deploy disabled | P1       | todo   | CC Core | 120    | E2E in CI                | Sprint 120  |
| CCX-091 | k6 playbook p95 CI gate               | P1       | todo   | CC Core | 117    | p95 <2s cached           | Sprint 117  |
| CCX-092 | Chaos IBKR reconnect test             | P1       | todo   | CC Core | 118    | Handoff under disconnect | Sprint 118  |
| CCX-093 | Shadow digest scheduled test          | P2       | todo   | CC Core | 120    | Behavior audit job       | Sprint 120  |
| CCX-094 | Walk-forward CI weekly                | P3       | todo   | CC Core | —      | OOS regression           | Tier 3      |
| CCX-095 | Dossier instant core <500ms           | P2       | todo   | CC Core | 117    | Core fields fast path    | Sprint 117  |
| CCX-096 | gzip instant dashboard always         | P2       | todo   | CC Core | 116    | Today load <800ms        | Sprint 116  |
| CCX-097 | yfinance async batch per scan         | P2       | todo   | CC Core | 117    | Scan latency reduction   | Sprint 117  |

---

## UX & operator productivity

| ID      | Item                                                        | Priority | Status      | Owner   | Sprint | Acceptance criteria                                             | Evidence/PR                                    |
| ------- | ----------------------------------------------------------- | -------- | ----------- | ------- | ------ | --------------------------------------------------------------- | ---------------------------------------------- |
| CCX-100 | Command palette ⌘K v0                                       | P2       | todo        | CC Core | 120    | Launcher for surfaces                                           | Sprint 120                                     |
| CCX-101 | Keyboard shortcuts G T/P/D                                  | P3       | todo        | CC Core | 120    | Power-user nav                                                  | Sprint 120                                     |
| CCX-102 | Command tab best_action sync                                | P1       | todo        | CC Core | 115    | Command strip = Today best_action                               | Backlog N7                                     |
| CCX-103 | Near-miss → watchlist triggers                              | P1       | todo        | CC Core | 115    | POST /api/watchlist/trigger                                     | Backlog M9/N8                                  |
| CCX-104 | i18n Ops remaining strings                                  | P2       | todo        | CC Core | —      | HK operator UX                                                  | Tier 3                                         |
| CCX-105 | i18n completion all tabs                                    | P3       | todo        | CC Core | —      | Bilingual all surfaces                                          | Tier 3                                         |
| CCX-106 | Template partial split Today/Playbook                       | P2       | todo        | CC Core | —      | build-cc-template.mjs                                           | Tier 3                                         |
| CCX-107 | Flow synthetic watermark persistent                         | P2       | todo        | CC Core | 116    | Synthetic flow labeled                                          | Sprint 116                                     |
| CCX-108 | AI Commentary collapsed by default                          | P2       | in-progress | CC Core | 115    | Non-decision AI demoted                                         | Backlog R2                                     |
| CCX-109 | Portfolio settings persist (cachedState buffer)             | P1       | done        | CC Core | 115    | SettingsView binds cachedState; no live-state race              | `6aa222e`, AGENTS.md pattern                   |
| CCX-129 | Docs consolidation — single backlog SSOT                    | P2       | done        | CC Core | 115    | No new scored review docs; living backlog only                  | `7032700`, `CC_X_ENGINEERING_BACKLOG.md`       |
| CCX-130 | CC X sprint modules wired (EV, Alpha, KG, Intel)            | P1       | done        | CC Core | 115    | Module tests green; research_only authority                     | `a540602`, `tests/test_cc_x_sprint_modules.py` |
| CCX-131 | Belief / conviction review loop — post-trade calibration UI | P0       | Q2, Q3    | in-progress | CC Core | 118    | Ops panel; thesis + kill_condition edit; PATCH API; linked to forward outcomes | `belief_review.py`, Phase B Phase 2 |

---

## Notifications & ops

| ID      | Item                              | Priority | Status | Owner   | Sprint | Acceptance criteria    | Evidence/PR   |
| ------- | --------------------------------- | -------- | ------ | ------- | ------ | ---------------------- | ------------- |
| CCX-110 | System Telegram BDR/regime alerts | P2       | done   | CC Core | 114    | Deploy-gate aware      | `telegram.py` |
| CCX-111 | Discord research mute default     | P2       | done   | CC Core | —      | Alert noise controlled | Observed      |
| CCX-112 | Telegram deploy-gate hardening    | P2       | todo   | CC Core | 116    | Token hygiene          | Sprint 116    |
| CCX-113 | Platform error log → Ops digest   | P3       | todo   | CC Core | 116    | Reliability digest     | Sprint 116    |

---

## Meta Intelligence Engine (v15)

| ID      | Item                                      | Priority | Status | Owner   | Sprint | Acceptance criteria                              | Evidence/PR                    |
| ------- | ----------------------------------------- | -------- | ------ | ------- | ------ | ------------------------------------------------ | ------------------------------ |
| CCX-132 | Usage/ignore logging contract             | P1       | todo   | CC Core | 127    | Surface dwell + dismiss events → JSONL           | `CC_X_META_INTELLIGENCE.md` P1 |
| CCX-133 | Trust one-tap feedback hook               | P1       | todo   | CC Core | 127    | Dismiss/override → trust feedback log            | Trust Engine Phase 1           |
| CCX-134 | Evolution Dashboard stub (Ops)            | P1       | todo   | CC Core | 127    | Ops panel; `research_only`; MIE summary          | `CC_X_META_INTELLIGENCE.md` P1 |
| CCX-135 | Belief Review full items (conviction drift) | P0     | todo   | CC Core | 118    | beliefs due, thesis updates; extends CCX-131 stub | v14 compounding                |
| CCX-136 | Weekly CIO Review digest                  | P2       | todo   | CC Core | 118    | Weekly ops digest automation                   | v14 compounding                |
| CCX-137 | Monthly Evolution Report                  | P2       | todo   | CC Core | 127    | MIE monthly JSON/PDF export                      | System Evolution Review        |
| CCX-138 | Attention Cost scoring per surface        | P2       | todo   | CC Core | 128    | Per-surface attention cost metrics               | Attention Cost Engine          |
| CCX-139 | Curiosity Engine research queue           | P2       | todo   | CC Core | 128    | Unexplored monitor candidates queue              | Curiosity Engine               |
| CCX-140 | Top 20 self-improvements ranker           | P3       | todo   | CC Core | 129    | IC-lift potential ranking; delete/combine list   | MIE Phase 3                    |

---

## Investment Firm OS (v16)

| ID      | Item                                              | Priority | Status      | Owner   | Sprint | Acceptance criteria                                      | Evidence/PR                         |
| ------- | ------------------------------------------------- | -------- | ----------- | ------- | ------ | -------------------------------------------------------- | ----------------------------------- |
| CCX-141 | Daily firm routine CIIO template                  | P1       | todo        | CC Core | 130    | Mission Brief checklist; gate→attention→journal          | `CC_X_INVESTMENT_FIRM.md` §2        |
| CCX-142 | Weekly Investment Committee digest                | P1       | todo        | CC Core | 130    | Weekly CIO narrative ≤1 page; belief status board        | v16 §3; extends CCX-136             |
| CCX-143 | Monthly Capital Review template                   | P1       | todo        | CC Core | 131    | Marginal ROC ladder + cash audit checklist               | v16 §4; integrates CCX-137          |
| CCX-144 | Quarterly Belief Review ritual                    | P1       | todo        | CC Core | 131    | Calibration + death certificates; extends CCX-135          | v16 §5                              |
| CCX-145 | Annual Learning Summit stub                       | P2       | todo        | CC Core | 132    | Attribution tree + letter-to-future-self scaffold        | v16 §6                              |
| CCX-146 | Committee checklists in Ops                       | P1       | in-progress | CC Core | 130    | Ops panels per committee; research_only                  | firm-cadence panel Phase 1          |
| CCX-147 | Firm cadence API + Mission Control strip          | P1       | done        | CC Core | 130    | `/api/v7/firm-cadence/summary`; next ritual display      | `decision.py`, `cc-app.js`          |
| CCX-148 | Investment lifecycle — Idea→Research wired        | P2       | todo        | CC Core | 132    | IO birth on scan promote; stage labels in dossier          | v16 lifecycle                       |
| CCX-149 | Investment lifecycle — Belief→Decision wired      | P2       | todo        | CC Core | 132    | Thesis + kill conditions on deploy log                     | Decision Engine                     |
| CCX-150 | Investment lifecycle — Capital→Execution wired    | P2       | todo        | CC Core | 133    | Sizing rationale + marginal ROC on handoff                 | Portfolio + Execution               |
| CCX-151 | Investment lifecycle — Stewardship→Exit wired     | P2       | todo        | CC Core | 133    | Kill condition triggers; death certificate on close        | Learning loop                       |
| CCX-152 | Investment lifecycle — Learning→Knowledge wired   | P2       | todo        | CC Core | 133    | Lesson cards + idea graveyard retrieval                    | AlphaObject + Knowledge             |
| CCX-153 | Behavioral governance rules in Ops                | P2       | todo        | CC Core | 134    | Override cooldown + loss-day cash rule surfaced            | v16 §11                             |
| CCX-154 | Debate protocol (steel man / inversion) on deploy | P2       | todo        | CC Core | 134    | Pre-deploy checklist modal; logged not blocking            | v16 §10                             |
| CCX-155 | Knowledge preservation retrieval before scan      | P2       | todo        | CC Core | 134    | Prior lessons surface on ticker research                   | v16 §7                              |

---

## Workflow Operating System (CCX-162–172)

| ID      | Item                                      | Priority | Status      | Owner   | Sprint | Acceptance criteria                                              | Evidence/PR                              |
| ------- | ----------------------------------------- | -------- | ----------- | ------- | ------ | ---------------------------------------------------------------- | ---------------------------------------- |
| CCX-162 | Pre-Decision Checklist                    | **P0**   | **done**    | CC Core | 130    | 7 fields; GET/POST checklist; Mission strip; research_only       | `decision_readiness.py`, Phase 1 stub    |
| CCX-163 | Daily IC 5 min                            | P1       | in-progress | CC Core | 130    | One-page Mission→Market→Portfolio→Capital→One Belief             | `/api/v7/daily-ic/summary`, Mission Control strip |
| CCX-164 | Attention Budget                          | P1       | **in-progress** | CC Core | 130    | Category time budgets; CIIO Enough signal                        | `attention_budget.py`, Mission+Ops strip |
| CCX-165 | Decision Pipeline stages                  | P1       | todo        | CC Core | 131    | Idea→Review stages; 80% die labels on dossier                    | Workflow #4                              |
| CCX-166 | Opportunity Lifecycle                     | P1       | todo        | CC Core | 131    | Born→Archived state on IO/Alpha                                  | Workflow #5 · CCX-148–152                |
| CCX-167 | Time cadence (morning/close/weekly/…)     | P2       | todo        | CC Core | 131    | Rhythm strip on Mission Brief                                    | Workflow #6                              |
| CCX-168 | Opportunity Funnel                        | P1       | todo        | CC Core | 131    | Funnel stage ≠ rank on Playbook cards                            | Workflow #7                              |
| CCX-169 | Capital Workflow stages                   | P1       | todo        | CC Core | 132    | Cash→Review ladder on Portfolio                                  | Workflow #8                              |
| CCX-170 | Decision Cooling                          | **P0**   | **done**    | CC Core | 130    | READY→COOLING→READY_TO_CONFIRM; cancel reasons; research_only    | `decision_cooling.py`, Phase 1 stub      |
| CCX-171 | Research Queue                            | **P0**   | **done**    | CC Core | 130    | Time-budget queue; validated tickers; Ops read-only panel        | `research_queue.py`, Phase 1 stub        |
| CCX-172 | Workflow-nav replace tab mental model     | P1       | **in-progress** | CC Core | 130    | Stage-first workflow; tabs as evidence; ADR-024                  | Architecture § Workflow-first nav        |

**P0 APPROVED:** CCX-162 · CCX-170 · CCX-171 (Phase 1 stubs shipped).

**IDOS capabilities (prior):** CCX-156 Decision Journal · CCX-157 Red Team · CCX-158 Outside View · CCX-159 Decision Committee · CCX-160 Decision Health · CCX-161 Four Questions wiring.

---

## IDOS decision process (ADR-023)

| ID      | Item                                              | Priority | Status      | Owner   | Sprint | Acceptance criteria                                      | Evidence/PR                         |
| ------- | ------------------------------------------------- | -------- | ----------- | ------- | ------ | -------------------------------------------------------- | ----------------------------------- |
| CCX-156 | **Decision Journal Phase 1** — JSONL + API + Ops  | **P0**   | in-progress | CC Core | 135    | Pre-outcome entries; deploy + WAIT; Phase 2 deploy-intent checklist API | `decision_journal.py`, ADR-023      |
| CCX-157 | Red Team Engine stub                              | P1       | done (stub) | CC Core | 135    | `GET /api/v7/red-team/challenge`; Four Questions         | `red_team.py`                       |
| CCX-158 | Outside View Engine stub                          | P1       | done (stub) | CC Core | 135    | `GET /api/v7/outside-view/base-rate`                     | `outside_view.py`                   |
| CCX-159 | Decision Committee stub                           | P1       | done (stub) | CC Core | 135    | Seven virtual members; research_only                     | `decision_committee.py`             |
| CCX-160 | Decision Health stub                              | P2       | done (stub) | CC Core | 135    | Calibration inputs; non-blocking                         | `decision_health.py`                |
| CCX-161 | Wisdom loop closure                               | P1       | todo        | CC Core | 136    | Journal review → character; quarterly ritual             | Pyramid top; after CCX-156 Phase 2    |

---

## Enterprise & scale (P3)

| ID      | Item                                      | Priority | Status | Owner   | Sprint | Acceptance criteria      | Evidence/PR            |
| ------- | ----------------------------------------- | -------- | ------ | ------- | ------ | ------------------------ | ---------------------- |
| CCX-120 | Enterprise RBAC                           | P3       | todo   | CC Core | —      | Role-based deploy/export | Tier 3                 |
| CCX-121 | Audited P&L ledger                        | P3       | todo   | CC Core | —      | Institutional ledger     | Long-term              |
| CCX-122 | Multi-tenant book isolation               | P3       | todo   | CC Core | —      | SaaS isolation           | Long-term              |
| CCX-123 | Polygon primary + yfinance fallback       | P2       | todo   | CC Core | —      | Data quality             | Tier 3                 |
| CCX-124 | Redis horizontal scan fan-out             | P3       | todo   | CC Core | —      | Scale scanner            | Tier 3                 |
| CCX-125 | SSE trigger vs health poll                | P2       | todo   | CC Core | —      | Latency                  | Tier 3                 |
| CCX-126 | Investment Object full consumer migration | P1       | todo   | CC Core | 125    | All new paths on IO      | Sprint 125             |
| CCX-127 | TypedDict SystemState strict mypy         | P2       | todo   | CC Core | 116    | Type safety              | Sprint 116             |
| CCX-128 | Living architecture doc maintained        | P3       | done   | CC Core | —      | Code-verified SSOT       | `CC_X_ARCHITECTURE.md` |

---

## Alpha compounding (v14) — cross-track

Maps v14 compounding loops to canonical backlog IDs (no duplicate rows):

| Loop                         | Backlog ID(s)     | Status      |
| ---------------------------- | ----------------- | ----------- |
| Trade close → forward outcomes | CCX-041         | **done**    |
| Belief Review (stub → full)  | CCX-131, CCX-135  | Phase 2 (thesis/kill edit) / todo |
| Weekly CIO Review digest     | CCX-136           | todo        |
| Monthly Evolution Report     | CCX-137           | todo        |
| Dossier belief tab           | _future_          | todo        |

Design: [`CC_X_META_INTELLIGENCE.md`](./CC_X_META_INTELLIGENCE.md) § v14 Alpha Compounding loops.

---

## Summary

| Metric                  |   Count |
| ----------------------- | ------: |
| **Total backlog items** | **141** |
| done                    |      29 |
| in-progress             |       7 |
| todo                    |     112 |
| blocked                 |       0 |

**Done:** CCX-001, CCX-001b, CCX-002, CCX-003, CCX-004, CCX-041, CCX-UX-01, CCX-UX-02, CCX-UX-03, CCX-UX-05, CCX-UX-07, CCX-109, CCX-110, CCX-111, CCX-128, CCX-129, CCX-130, CCX-147, CCX-157, CCX-158, CCX-159, CCX-160, CCX-162, CCX-170, CCX-171

**In-progress:** CCX-108, CCX-131, CCX-053 (live wire), CCX-146, CCX-172, **CCX-156 (Journal Phase 2 checklist)**, **CCX-UX-04**, **CCX-163**, **CCX-164**, **CCX-073**

**Phase B (next — IC APPROVED order):** CCX-163 Daily IC expand · CCX-165–169 pipeline/funnel/capital · CCX-131→135 Belief Review full · CCX-045 calibration · CCX-UX-04 PM strip finish · CCX-006 provenance · CCX-007 CI gate

**DEFERRED (Resolution):** CCX-090 Playwright E2E · CCX-134 Evolution Dashboard · CCX-126 IO migration · CCX-070 Knowledge Graph

---

## Explicitly postponed

| Item                           | Reason                     |
| ------------------------------ | -------------------------- |
| Unlimited new tabs             | Hierarchy discipline       |
| AI as primary ranker           | No calibrated track record |
| Auto bracket submit            | Human confirm required     |
| Enterprise RBAC / multi-tenant | Long-term commercial       |

---

## Test gates (every PR)

```bash
python -m pytest tests/test_operator_state_contract.py tests/test_decision_board_service.py tests/test_decision_board_authority_cache.py -q
bash scripts/verify_10_10.sh
```
