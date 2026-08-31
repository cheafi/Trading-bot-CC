# CC X — Decision Log (ADR)

**Product:** CC X · `TradingAI_Bot`  
**Format:** Architecture Decision Records — append-only  
**Architecture SSOT:** [`CC_X_ARCHITECTURE.md`](./CC_X_ARCHITECTURE.md)

---

## ADR-001 — Page Gate beats Card Rank

| Field                     | Detail                                                                                                                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-04 (vNext); reaffirmed 2026-08-25                                                                                                                                                                  |
| **Status**                | Accepted                                                                                                                                                                                                |
| **Decision**              | Deploy authority flows from page-level `SystemState.deploy_open` and regime tradeability. Playbook rank, Discovery score, graph rank, and ML score **never** override WAIT/NO_TRADE/STALE/broker gates. |
| **Alternatives rejected** | Per-card deploy when rank is high; auto-deploy top-N scanner output                                                                                                                                     |
| **Trade-offs**            | Operator may see attractive names blocked by regime — intentional capital preservation                                                                                                                  |
| **Impact**                | `operator_state_contract.py`, Guide Layer 1, Playbook WATCH cap on brief rows, UI deploy strips                                                                                                         |
| **Evidence**              | `tests/test_operator_state_contract.py`, `tests/test_quant_authority_boundaries.py`                                                                                                                     |

---

## ADR-002 — Research ≠ Deploy Permission

| Field                     | Detail                                                                                                                                                                                                      |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-04 (vNext); codified in `surface_authority.py`                                                                                                                                                         |
| **Status**                | Accepted                                                                                                                                                                                                    |
| **Decision**              | Discovery, Dossier, Flow, Agent, Shadow, Reports, Backtest Lab, and Ops surfaces carry `research_only` or `confirmation_only` authority. They inform decisions but cannot authorize sizing or IBKR handoff. |
| **Alternatives rejected** | Discovery deploy buttons; dossier-triggered handoff; backtest pass → live TRADE                                                                                                                             |
| **Trade-offs**            | Extra navigation step for operator; fewer accidental deploys                                                                                                                                                |
| **Impact**                | `TAB_SURFACE_MAP`, API `authority` fields, Telegram/Discord alert gating                                                                                                                                    |
| **Evidence**              | `surface_authority.py`, [`archive/CC_CONSOLIDATED_BRIEFING.md`](./archive/CC_CONSOLIDATED_BRIEFING.md) §2                                                                                                   |

---

## ADR-003 — DecisionBoardService as Deploy Truth SSOT

| Field                     | Detail                                                                                                                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25 (Sprint 115)                                                                                                                                                                                 |
| **Status**                | Accepted (Phase A complete on `59db29f`)                                                                                                                                                              |
| **Decision**              | `build_decision_board()` in `decision_board_service.py` is the single composer for `deploy_open`, gate reasons, and regime block across Today, Playbook, and cc-header. Client reconciles display only. |
| **Alternatives rejected** | Independent payload builders per surface; client-side deploy_open derivation                                                                                                                            |
| **Trade-offs**            | Requires router migration; eliminates drift                                                                                                                                                             |
| **Impact**                | `decision.py`, `playbook.py`, `cc_header.py`, `cc-app.js` poll paths                                                                                                                                    |
| **Evidence**              | `tests/test_decision_board_service.py`; backlog CCX-001                                                                                                                                                 |

---

## ADR-004 — Rank ≠ Quality ≠ Authority

| Field                     | Detail                                                                                                                                                                                                            |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25                                                                                                                                                                                                        |
| **Status**                | Accepted                                                                                                                                                                                                          |
| **Decision**              | Opportunity **rank** (sort order), **quality** (durability/asymmetry/bandwidth classification), and **authority** (deploy permission) are three separate dimensions. Quality informs monitor prioritization only. |
| **Alternatives rejected** | Quality tier unlocking deploy; rank-as-permission on Discovery                                                                                                                                                    |
| **Trade-offs**            | More UI labels; clearer operator mental model                                                                                                                                                                     |
| **Impact**                | `opportunity_quality.py`, `decision_board_service.py` regime block, Playbook chips                                                                                                                                |
| **Evidence**              | Module docstring; `tests/test_opportunity_quality.py`; backlog CCX-UX-02/03                                                                                                                                       |

---

## ADR-005 — Guide (Operator Reference) Mode Default on Guide Tab

| Field                     | Detail                                                                                                                                                                              |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-06 (`surface_authority.py` refactor)                                                                                                                                           |
| **Status**                | Accepted                                                                                                                                                                            |
| **Decision**              | Guide tab suspends active decision language (`AUTHORITY_SUSPENDED`). PM strip must not show deploy chips on non-decision tabs. Each surface owns exactly one header authority copy. |
| **Alternatives rejected** | Global decision hub chips on every tab                                                                                                                                              |
| **Trade-offs**            | Guide is reference-only; decision work happens on Today/Playbook                                                                                                                    |
| **Impact**                | `SURFACE_MODES`, `build_header_summary`, `cc-helpers.js` Guide bindings                                                                                                             |
| **Evidence**              | `docs/SURFACE_AUTHORITY_REFACTOR.md`, `tests/test_surface_ownership.py`                                                                                                             |

---

## ADR-006 — Fail-Closed Regime on Errors

| Field                     | Detail                                                                                                              |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25                                                                                                          |
| **Status**                | Accepted                                                                                                            |
| **Decision**              | Regime router/service failures default to WAIT / `should_trade=false`. Never serve optimistic TRADE on error paths. |
| **Alternatives rejected** | Last-known-good regime on error; fail-open to avoid blocking                                                        |
| **Trade-offs**            | More WAIT days during infra issues — acceptable vs capital risk                                                     |
| **Impact**                | `regime_router.py`, `regime_service.py`, `decision.py`                                                              |
| **Evidence**              | Commit `8b51620`; backlog CCX-003                                                                                   |

---

## ADR-007 — Never Cache deploy_open

| Field                     | Detail                                                                                                                                                                                   |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25                                                                                                                                                                               |
| **Status**                | Accepted                                                                                                                                                                                 |
| **Decision**              | Cached playbook/scan bodies may cache rank and research fields, but `deploy_open` and authoritative gate fields are **recomputed on read**. Performance cache must not cache permission. |
| **Alternatives rejected** | TTL-based deploy_open in snapshot; client-side stale-while-revalidate for gates                                                                                                          |
| **Trade-offs**            | Slightly higher read latency on cache hits — bounded and acceptable                                                                                                                      |
| **Impact**                | `decision.py` cached scan path, `cc_header.py` light mode                                                                                                                                |
| **Evidence**              | Commit `8b51620`; `tests/test_decision_board_authority_cache.py`; backlog CCX-002                                                                                                        |

---

## ADR-008 — TRADE_RR_THRESHOLD Static at 2.5

| Field                     | Detail                                                                                                                                       |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-04 (truth model); permanent policy                                                                                                      |
| **Status**                | Accepted                                                                                                                                     |
| **Decision**              | Minimum R:R for TRADE label remains 2.5 in `decision_truth_model.py`. No auto-loosen after losses. Changes require human-reviewed changelog. |
| **Alternatives rejected** | ML-driven threshold relaxation; regime-adaptive R:R without ops approval                                                                     |
| **Trade-offs**            | Fewer TRADE labels in low-R:R environments                                                                                                   |
| **Impact**                | `decision_truth_model.py`, `playbook_upgrade_ladder.py`, council pipeline                                                                    |
| **Evidence**              | `tests/test_decision_truth_model.py`                                                                                                         |

---

## ADR-009 — ML and Self-Learning Advisory Only

| Field                     | Detail                                                                                                                                                                                |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-04 (vNext)                                                                                                                                                                       |
| **Status**                | Accepted                                                                                                                                                                              |
| **Decision**              | MetaEnsemble, Thompson sizing, self-learning weight updates, and feature IC alerts are advisory. Apply requires Ops toggle, min sample (n≥30), and audit log. Kill switch default ON. |
| **Alternatives rejected** | Auto-apply weights from closed trades; ML multiplier without sample floor                                                                                                             |
| **Trade-offs**            | Slower ML value realization; auditable governance                                                                                                                                     |
| **Impact**                | `self_learning.py`, `ml_advisory_summary.py`, `learning_loop.py`                                                                                                                      |
| **Evidence**              | Authority tests; CCX-043 backlog                                                                                                                                                      |

---

## ADR-010 — InvestmentObject vs AlphaObject Separation

| Field                     | Detail                                                                                                                                                                                                                          |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25 (CC X schema)                                                                                                                                                                                                        |
| **Status**                | Accepted                                                                                                                                                                                                                        |
| **Decision**              | **InvestmentObject** = decision-layer ephemeral active trade (may carry deploy fields through Decision Engine only). **AlphaObject** = permanent knowledge-layer memory (`research_only`, `may_authorize_deploy=false` always). |
| **Alternatives rejected** | Single merged object; AlphaObject granting deploy                                                                                                                                                                               |
| **Trade-offs**            | Two schemas to maintain; clean audit / memory separation                                                                                                                                                                        |
| **Impact**                | `src/core/investment_object.py`, `src/core/alpha_object.py`                                                                                                                                                                     |
| **Evidence**              | Schema defaults; backlog CCX-021, CCX-127                                                                                                                                                                                       |

---

## ADR-011 — Investment-Outcome-First Layer Ordering

| Field                     | Detail                                                                                                                                                                    |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25                                                                                                                                                                |
| **Status**                | Accepted (design direction)                                                                                                                                               |
| **Decision**              | Build and measure in order: Capital → Expected Alpha → Risk Budget → Portfolio → Execution → Measured Alpha → Knowledge. Six engines share one model; UI pages are views. |
| **Alternatives rejected** | Page-first feature roadmap; indicator accumulation without alpha measurement                                                                                              |
| **Trade-offs**            | Slower visible UI churn; higher long-term compounding                                                                                                                     |
| **Impact**                | Sprint 115–126 prioritization; backlog ordering                                                                                                                           |
| **Evidence**              | `CC_X_INSTITUTIONAL_ALPHA_OS.md` (historical roadmap); backlog SSOT                                                                                                       |

---

## ADR-012 — Instant Boot with Honest Degraded Mode

| Field                     | Detail                                                                                                                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-06 (stabilization pass)                                                                                                                                                                            |
| **Status**                | Accepted                                                                                                                                                                                                |
| **Decision**              | `_cc_instant.py` serves shell immediately with explicit loading/degraded banners. Safe actions (monitors, Guide, dossier core-only) available during warmup. No green TRADE pills while `mode=loading`. |
| **Alternatives rejected** | Blank page until full API; fake ready state                                                                                                                                                             |
| **Trade-offs**            | Two-phase UX; operator clarity during boot                                                                                                                                                              |
| **Impact**                | `_cc_instant.py`, warmup strips, soak runbook §1                                                                                                                                                        |
| **Evidence**              | `CC_X_PRODUCTION_READINESS.md` soak §1–2                                                                                                                                                                |

---

## ADR-013 — Living Docs Replace Scored Review Accumulation

| Field                     | Detail                                                                                                                                                                                      |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25                                                                                                                                                                                  |
| **Status**                | Accepted                                                                                                                                                                                    |
| **Decision**              | Maintain four living documents (Architecture, Backlog, Production Readiness, Decision Log) plus Review Cycle process. Historical reviews archived; no new comprehensive scored review docs. |
| **Alternatives rejected** | Fifth-pass / sixth-pass review documents with scorecards                                                                                                                                    |
| **Trade-offs**            | Less narrative history in one file; clearer SSOT for engineering                                                                                                                            |
| **Impact**                | `docs/CC_X_*.md`; `docs/archive/`                                                                                                                                                           |
| **Evidence**              | This decision log; `CC_X_REVIEW_CYCLE.md`                                                                                                                                                   |

---

## ADR-014 — Operator Mode: Mission Brief + Guide as Help

| Field                     | Detail                                                                                                                                                                              |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25                                                                                                                                                                          |
| **Status**                | Accepted                                                                                                                                                                            |
| **Decision**              | Today dashboard uses **Mission Brief** panel with bilingual NOW/BLOCKER/NEXT copy as default operator surface. Guide tab is **Help** — reference-only, no active decision language. |
| **Alternatives rejected** | Guide as primary decision surface; AI commentary as first screen                                                                                                                    |
| **Trade-offs**            | Clearer operator workflow; Guide demoted to manual                                                                                                                                  |
| **Impact**                | `cc-helpers.js` Mission Brief title, `today-mission-panel`, Guide `AUTHORITY_SUSPENDED`                                                                                             |
| **Evidence**              | Commit `4905a4e`, `1802a5f`; backlog CCX-UX-01, CCX-UX-05                                                                                                                             |

---

## ADR-015 — Deploy SSOT UI: deployOpen() Only

| Field                     | Detail                                                                                                                                                          |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25                                                                                                                                                      |
| **Status**                | Accepted                                                                                                                                                        |
| **Decision**              | Client deploy permission reads `system_state.deploy_open` via `deployOpen()` / `deployOpenFromSystemState()` only. Remove parallel `can_deploy_today` UI paths. |
| **Alternatives rejected** | Client-side deploy derivation from rank or brief rows; dual deploy signals                                                                                     |
| **Trade-offs**            | Single source reduces authority drift; requires board poll freshness                                                                                            |
| **Impact**                | `cc-app.js`, `cc-helpers.js`; `tests/test_operator_mode_ux.py`                                                                                                  |
| **Evidence**              | Phase A `59db29f`; backlog CCX-001; `test_deploy_ssot_no_can_deploy_today_in_cc_app`                                                                            |

---

## ADR-016 — Shared Opportunity Pipeline (Today + Playbook)

| Field                     | Detail                                                                                                                                       |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25                                                                                                                                   |
| **Status**                | Accepted                                                                                                                                     |
| **Decision**              | Both Today and Playbook ranked paths call `finalize_opportunity_pipeline()` for quality attach, IO/Alpha enrich, and opportunity verdict.   |
| **Alternatives rejected** | Divergent enrichment in `decision.py` vs `playbook.py`; rank-only Playbook without quality parity                                            |
| **Trade-offs**            | Shared module coupling; consistent operator truth across surfaces                                                                            |
| **Impact**                | `opportunity_pipeline.py`, `cost_adjusted_ranker.py`, `decision.py`, `playbook.py`                                                           |
| **Evidence**              | `tests/test_opportunity_pipeline.py`; backlog CCX-001b                                                                                       |

---

## ADR-017 — Forward Outcomes Loop (T+0 + Scheduled Marks)

| Field                     | Detail                                                                                                                                              |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25                                                                                                                                          |
| **Status**                | Accepted                                                                                                                                            |
| **Decision**              | On trade close, `learning_loop.py` records T+0 forward outcome stub. Scheduler runs `run_forward_outcome_marks()` at 4:45 PM ET weekdays for T+1/5/20. |
| **Alternatives rejected** | Batch-only EOD without close hook; deploy-gated outcome marks                                                                                       |
| **Trade-offs**            | Marks are `research_only`; calibration data may be sparse early                                                                                     |
| **Impact**                | `forward_outcomes.py`, `learning_loop.py`, `scheduler/main.py`, `data/forward_outcomes.jsonl`                                                       |
| **Evidence**              | `tests/test_forward_outcomes_hook.py`; backlog CCX-041                                                                                              |

---

## ADR-018 — Meta Intelligence Engine v15 Design Adoption

| Field                     | Detail                                                                                                                                                         |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25                                                                                                                                                     |
| **Status**                | Accepted (design + Phase 1 stubs)                                                                                                                              |
| **Decision**              | Adopt MIE as monthly **System Evolution Review** layer: Trust, Curiosity, Silence, Attention Cost engines. All outputs `research_only`; never grant deploy.    |
| **Alternatives rejected** | New scored review docs; MIE as auto-apply optimizer                                                                                                            |
| **Trade-offs**            | Telemetry + review UI before full automation; human CIO cadence preserved                                                                                      |
| **Impact**                | `CC_X_META_INTELLIGENCE.md`, backlog CCX-132–140, monthly review in `CC_X_REVIEW_CYCLE.md`                                                                     |
| **Evidence**              | Design doc; Phase 1 items tracked in backlog                                                                                                                   |

---

## ADR-019 — Belief Review Stub (Research-Only Calibration UI)

| Field                     | Detail                                                                                                                                  |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25 (Phase B stub)                                                                                                               |
| **Status**                | Accepted (stub); full items todo (CCX-135)                                                                                              |
| **Decision**              | Expose `/api/v7/belief-review/summary` and Ops `[data-cc="belief-review-panel"]` as research-only calibration surface linked to forward outcomes. |
| **Alternatives rejected** | Belief review on deploy surfaces; auto-conviction updates from marks                                                                    |
| **Trade-offs**            | Stub returns empty items until CCX-135; establishes API contract early                                                                  |
| **Impact**                | `decision.py`, `index.html`, `cc-app.js`; feeds MIE Belief Review loop                                                                  |
| **Evidence**              | `tests/test_operator_mode_ux.py`; backlog CCX-131                                                                                       |

---

## ADR-025 — CTO Self-Critique: Loops Before Engines

| Field                     | Detail                                                                                                                                  |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25                                                                                                                              |
| **Status**                | Accepted (priorities reshaped)                                                                                                          |
| **Decision**              | CC X is a strong **authority system** wearing an incomplete **compounding system**. Prioritize closing four loops — Belief, Capital, Learning, Knowledge — and **deleting attention-tax surfaces** before new engines, tabs, or narrative blocks. Engineering capital: Belief loop 20%, Marginal ROC 18%, Deletions 15%, Portfolio SSOT 10%; **zero** for new feeds/ranks/AI narrative unless tied to a loop. |
| **Alternatives rejected** | More sprint modules; Meta Intelligence dashboard before usage logging; Discovery as equal nav peer; rank-first UX on WAIT days          |
| **Trade-offs**            | Slower feature count; faster decision-quality compounding; docs must track uncommitted Phase B to prevent drift                       |
| **Impact**                | Backlog P0 reorder (`CC_X_ENGINEERING_BACKLOG.md` § Decision Quality Audit); deletion batch 1; Belief Review Phase 2; marginal ROC stub; firm cadence stubs without CC_X_INVESTMENT_FIRM.md (deferred — Constitution + Meta + Backlog suffice) |
| **Evidence**              | Decision Quality Audit + CTO Self-Critique (2026-08-25 conversation); Phase B implementation on branch `cc/upgrade-regime-tracking`     |

---

## ADR-020 — Investment Firm OS v16 Adoption

| Field                     | Detail                                                                                                                                  |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25 (Phase B cadence stubs)                                                                                                      |
| **Status**                | Accepted (design + Phase 1 stubs)                                                                                                       |
| **Decision**              | Adopt v16 as governance overlay: committees, cadences, lifecycle, culture. CC simulates institutional discipline; one human remains PM. |
| **Alternatives rejected** | v16 as deploy layer; auto-committee decisions; new scored review docs                                                                  |
| **Trade-offs**            | Templates and checklists before full automation; all surfaces `research_only`                                                           |
| **Impact**                | `CC_X_INVESTMENT_FIRM.md`, backlog CCX-141–155, `/api/v7/firm-cadence/summary`, Ops + Mission Control strips                            |
| **Evidence**              | Firm doc; `tests/test_operator_mode_ux.py` firm cadence tests; ADR-011–019 authority preserved                                          |

---

## ADR-021 — Investment Committee Resolution Adopted

| Field                     | Detail                                                                                                                                                                                                 |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Date**                  | 2026-08-25                                                                                                                                                                                             |
| **Status**                | Accepted                                                                                                                                                                                               |
| **Decision**              | Adopt [`CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md`](./CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md) as the binding engineering capital allocation document. Supersedes CC X Self-Critique. Every major recommendation is **APPROVED**, **DEFERRED**, or **REJECTED** — no "interesting." Backlog P0 reordered to APPROVED portfolio items only. |
| **Alternatives rejected** | Continuing Self-Critique as advisory diagnosis; building without IC decision table; P0 backlog including REJECTED/DEFERRED items                                                                        |
| **Trade-offs**            | Fewer parallel features; deferred Meta dashboard and E2E breadth; explicit rejection of AI narrative and Discovery filter expansion                                                                  |
| **Impact**                | Backlog P0 order; quarterly Engineering IC ritual in `CC_X_REVIEW_CYCLE.md`; 100-point capital allocation; kill criteria on all APPROVED features                                                     |
| **Evidence**              | Resolution doc §2 decision table (18 APPROVED · 10 DEFERRED · 10 REJECTED); portfolio P-001–P-020                                                                                                      |

---

## ADR-022 — Four Questions Law + IDOS Reframe

| Field                     | Detail                                                                                                                                                                                                 |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Date**                  | 2026-08-25                                                                                                                                                                                             |
| **Status**                | Accepted                                                                                                                                                                                               |
| **Decision**              | Adopt **Investment Decision Operating System (IDOS)** reframe (from IOS). **The Four Questions** (Know / Believe / Doubt / Act) are immutable law immediately after Constitution in all relevant docs. Operator mental model is KNOW → BELIEVE → DOUBT → ACT, not engines/tabs. Seven engines demoted to internal implementation appendix. Meta Intelligence scores **which question became easier to answer**, not which engine improved. PR/proposal gate requires Four Questions justification. |
| **Alternatives rejected** | Continued IOS framing; engine-first operator philosophy; score-first screens; new philosophy version docs instead of updating living docs                                                             |
| **Trade-offs**            | Requires UI copy and review format migration; clearer rejection criteria for low-value features                                                                                                      |
| **Impact**                | `CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md`, `CC_X_ARCHITECTURE.md`, `CC_X_META_INTELLIGENCE.md`, `CC_X_INVESTMENT_FIRM.md`, `CC_X_ENGINEERING_BACKLOG.md`, `.github/pull_request_template.md`, `AGENTS.md` |
| **Evidence**              | Investment Committee Resolution; ADR-013 living docs policy preserved                                                                                                                                  |

---

## ADR-023 — Five IDOS Capabilities (final conceptual layer)

| Field                     | Detail                                                                                                                                                                                                 |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Date**                  | 2026-08-25                                                                                                                                                                                             |
| **Status**                | Accepted (Phase 1 Decision Journal + stubs 2–5)                                                                                                                                                        |
| **Decision**              | Adopt five **capabilities** (not features) as institutional decision process: (1) **Decision Journal** — pre-outcome records for deploy AND explicit wait; (2) **Red Team** — structured challenge; (3) **Outside View** — class base rates; (4) **Decision Committee** — virtual member debate; (5) **Decision Health** — calibration inputs (non-blocking). Extend Decision Quality Pyramid to **Wisdom**. Optimize Decision Quality → Decision Process → **Investor Character**. |
| **Alternatives rejected** | Post-hoc outcome narratives; AI theater without checklist; blocking deploy on health inputs; new philosophy sprawl beyond living doc merges                                                                 |
| **Trade-offs**            | Journal Phase 1 minimal JSONL before full UI authoring; stubs 2–5 API-only; CCX-044 legacy journal merge deferred                                                                                      |
| **Impact**                | `src/services/decision_journal.py`, stubs, `/api/v7/decision-journal/*`, challenge APIs, Ops panel, backlog CCX-156–161, Resolution maturity table, IBKR bracket `decision_id` hook                   |
| **Evidence**              | `tests/test_decision_journal.py`; ADR-022 authority preserved (`research_only` on all surfaces)                                                                                                        |

---

## ADR-024 — Workflow-First IDOS

| Field                     | Detail                                                                                                                                                                                                 |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Date**                  | 2026-08-25                                                                                                                                                                                             |
| **Status**                | Accepted (design + Phase 1 stubs)                                                                                                                                                                      |
| **Decision**              | Adopt **workflow-first navigation** over tab-first mental model. Eight workflow loops + Decision Cooling + Research Queue are the operator operating system. Stage chain: Mission → Attention → Research → Belief → Counterargument → Quality → Authority → Capital → Execution → Stewardship → Review → Knowledge → Tomorrow. Discovery/Playbook/Portfolio/Flow/RS/News remain **supporting evidence**, not workflow nav. Phase 1 stubs: pre-decision checklist (CCX-162), research queue (CCX-171), decision cooling (CCX-170) — all `research_only`; human deploy authority unchanged. |
| **Alternatives rejected** | Equal-weight tab nav; watchlist-as-research-queue; auto-deploy after checklist; cooling window granting deploy authority                                                                              |
| **Trade-offs**            | Tabs demoted to evidence surfaces; workflow docs merged into existing firm/architecture/backlog — no new philosophy sprawl                                                                              |
| **Impact**                | `CC_X_INVESTMENT_FIRM.md` § Workflow OS · `CC_X_ARCHITECTURE.md` stage-nav + funnel/lifecycle diagrams · `CC_X_ENGINEERING_BACKLOG.md` CCX-162–172 · `CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md` P-021–P-031 · `decision_readiness.py`, `research_queue.py`, `decision_cooling.py` |
| **Evidence**              | `tests/test_workflow_loops.py`; Mission Control pre-decision strip; Ops research-queue panel; decision journal workflow hooks                                                                          |

---

## ADR-026 — Project Review 2026-08-31

| Field                     | Detail                                                                                                                                  |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-31                                                                                                                              |
| **Status**                | Accepted                                                                                                                                |
| **Decision**              | Phase B review: enforce Portfolio SSOT on client read paths (server `portfolio_local_holdings.json` only); attach `decision_id` + `attribution_root_ref` in shared opportunity pipeline; improve Four Questions WAIT-day fallbacks. Pytest collection blocked on iCloud path — file-based + direct import tests used. |
| **Impact**                | `cc-helpers.js`, `cc-app.js`, `opportunity_pipeline.py`, backlog CCX-005/P-004 partial                                                   |
| **Evidence**              | `tests/test_operator_mode_ux.py` portfolio SSOT · `tests/test_opportunity_pipeline.py` attribution                                      |

---

## Template (for new ADRs)

```markdown
## ADR-NNN — Title

| Field                     | Detail                           |
| ------------------------- | -------------------------------- |
| **Date**                  | YYYY-MM-DD                       |
| **Status**                | Proposed / Accepted / Superseded |
| **Decision**              | What we decided                  |
| **Alternatives rejected** | What we did not do               |
| **Trade-offs**            | Costs and benefits               |
| **Impact**                | Modules, surfaces, backlog IDs   |
| **Evidence**              | Tests, commits, PRs              |
```
