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
| **Evidence**              | `surface_authority.py`, `CC_CONSOLIDATED_BRIEFING.md` §2                                                                                                                                                    |

---

## ADR-003 — DecisionBoardService as Deploy Truth SSOT

| Field                     | Detail                                                                                                                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Date**                  | 2026-08-25 (Sprint 115)                                                                                                                                                                                 |
| **Status**                | Accepted (partial rollout)                                                                                                                                                                              |
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
