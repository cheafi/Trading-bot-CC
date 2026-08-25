# CC X — Engineering Backlog (Living SSOT)

**Product:** CC X · `TradingAI_Bot`  
**Last updated:** 2026-08-25  
**Architecture:** [`CC_X_ARCHITECTURE.md`](./CC_X_ARCHITECTURE.md)  
**Sprint reference:** [`archive/CC_VNEXT_SPRINT_PLAN.md`](./archive/CC_VNEXT_SPRINT_PLAN.md), [`archive/CC_X_INSTITUTIONAL_ALPHA_OS.md`](./archive/CC_X_INSTITUTIONAL_ALPHA_OS.md)

> Single backlog for all CC X work. Future reviews add rows here — no new scored review docs. See [`CC_X_REVIEW_CYCLE.md`](./CC_X_REVIEW_CYCLE.md).

---

## In-flight UX (current sprint)

| ID        | Item                                                        | Priority | Status      | Owner   | Sprint | Acceptance criteria                                                                           | Evidence/PR                                                   |
| --------- | ----------------------------------------------------------- | -------- | ----------- | ------- | ------ | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| CCX-UX-01 | Mission Brief panel — bilingual NOW/BLOCKER/NEXT            | P1       | in-progress | CC Core | 115    | `[data-cc="today-mission-panel"]`; title "TODAY · Mission Brief · 今日任務"; WAIT copy honest | `4905a4e`, `cc-helpers.js`                                    |
| CCX-UX-02 | Opportunity quality on decision board regime block          | P1       | in-progress | CC Core | 115    | `opportunity_quality` in board regime; Hostile macro consistency                              | `decision_board_service.py`                                   |
| CCX-UX-03 | Opportunity quality chips on Playbook monitor cards         | P1       | in-progress | CC Core | 115    | Quality tier visible; never implies deploy                                                    | `opportunity_quality.py`, `tests/test_opportunity_quality.py` |
| CCX-UX-04 | Today PM strip — best action, near-miss, sleeve gate_status | P1       | in-progress | CC Core | 115    | 5-second deploy/wait/monitor answers                                                          | `today_insights.py`, `decision.py`                            |
| CCX-UX-05 | Guide tab as Help — suspended decision language             | P1       | in-progress | CC Core | 115    | Guide shows reference-only; no deploy chips                                                   | `4905a4e`, `surface_authority.py`                             |
| CCX-UX-06 | Provenance strip on price fields                            | P0       | todo        | CC Core | 116    | source/as_of/mode on prices; STALE hides deploy CTAs                                          | Sprint 116                                                    |

---

## Authority & decision

| ID      | Item                                            | Priority | Status      | Owner   | Sprint | Acceptance criteria                                 | Evidence/PR                                                   |
| ------- | ----------------------------------------------- | -------- | ----------- | ------- | ------ | --------------------------------------------------- | ------------------------------------------------------------- |
| CCX-001 | DecisionBoardService SSOT — all deploy surfaces | P0       | in-progress | CC Core | 115    | Today, Playbook, cc-header identical `deploy_open`  | `decision_board_service.py`, `test_decision_board_service.py` |
| CCX-002 | Never cache `deploy_open` on cached scan read   | P0       | done        | CC Core | 115    | Authority fields recomputed on read                 | `8b51620`, `test_decision_board_authority_cache.py`           |
| CCX-003 | Fail-closed regime on router/service errors     | P0       | done        | CC Core | 115    | Errors → WAIT; no optimistic TRADE                  | `8b51620`                                                     |
| CCX-004 | cc-header light mode honest deploy/regime       | P0       | done        | CC Core | 115    | Header poll matches board                           | `8b51620`, `test_cc_header_light.py`                          |
| CCX-005 | Attribution root ref on all board rows          | P0       | todo        | CC Core | 115    | Each row has `attribution_root_ref` / `decision_id` | Sprint 115                                                    |
| CCX-006 | Mandatory provenance on all prices              | P0       | todo        | CC Core | 116    | 100% price fields labeled; CI contract              | Sprint 116                                                    |
| CCX-007 | CI blocks authority regressions                 | P0       | todo        | CC Core | 116    | `verify_10_10.sh` on every PR                       | Sprint 116                                                    |
| CCX-008 | Hide mock factor on deploy surfaces             | P0       | todo        | CC Core | 116    | degraded or hidden on Portfolio deploy              | Sprint 116                                                    |
| CCX-009 | Extract 25 largest main.py handlers             | P1       | todo        | CC Core | 116    | Routes moved to routers                             | Sprint 116                                                    |
| CCX-010 | Unified header poll                             | P1       | todo        | CC Core | 116    | −40% API QPS                                        | Sprint 116                                                    |
| CCX-011 | Server-render authority labels                  | P2       | todo        | CC Core | 116    | Authority chip from API                             | Sprint 116                                                    |
| CCX-012 | Near-miss consolidate in contract               | P2       | todo        | CC Core | 115    | Single near_miss source                             | Sprint 115                                                    |
| CCX-013 | Shared \_norm_action utility                    | P2       | todo        | CC Core | 115    | Dedupe action normalization                         | Sprint 115                                                    |
| CCX-014 | Decision hub monitor payload unify              | P2       | todo        | CC Core | 115    | One monitor poll path                               | Sprint 115                                                    |

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

| ID      | Item                              | Priority | Status | Owner   | Sprint | Acceptance criteria                        | Evidence/PR |
| ------- | --------------------------------- | -------- | ------ | ------- | ------ | ------------------------------------------ | ----------- |
| CCX-040 | IBKR → closed_trades.jsonl ≥95%   | P1       | todo   | CC Core | 118    | Nightly capture job                        | Sprint 118  |
| CCX-041 | Forward outcomes T+1/T+5/T+20     | P1       | todo   | CC Core | 118    | `forward_outcomes.py` service              | Sprint 118  |
| CCX-042 | Real-Time Alpha Monitor (6 KPIs)  | P1       | todo   | CC Core | 118    | Produced/Lost/Preserved in Ops             | Sprint 118  |
| CCX-043 | Thompson/ML hidden n<5 / n<30     | P1       | todo   | CC Core | 118    | Insufficient sample not shown as precision | Sprint 118  |
| CCX-044 | Merge decision journal SSOT       | P2       | todo   | CC Core | 118    | Single journal path                        | Sprint 118  |
| CCX-045 | Ops Alpha QA panel                | P2       | todo   | CC Core | 118    | IC decay, Brier visible                    | Sprint 118  |
| CCX-046 | Self-learning audit log UI        | P3       | todo   | CC Core | 118    | Apply rate visible; default 0              | Sprint 118  |
| CCX-047 | Regime params versioned changelog | P3       | todo   | CC Core | 118    | Threshold changes human-reviewed           | Sprint 118  |
| CCX-048 | Council outcome tracking          | P2       | todo   | CC Core | 118    | Council vs outcome calibration             | Sprint 118  |

---

## Portfolio & capital

| ID      | Item                                   | Priority | Status | Owner   | Sprint | Acceptance criteria              | Evidence/PR |
| ------- | -------------------------------------- | -------- | ------ | ------- | ------ | -------------------------------- | ----------- |
| CCX-050 | EV Ranking 3.0 decomposition           | P1       | todo   | CC Core | 122    | `ev_ranking.py`; research_only   | Sprint 122  |
| CCX-051 | Capital Allocation panel               | P1       | todo   | CC Core | 122    | Next $10K ranked; no gate bypass | Sprint 122  |
| CCX-052 | Live factor wire (remove mock)         | P1       | todo   | CC Core | 122    | Real factor or explicit degraded | Sprint 122  |
| CCX-053 | marginal_return_on_capital on IO       | P1       | todo   | CC Core | 122    | Field on IO / AlphaObject        | Sprint 122  |
| CCX-054 | Sector cap blocks portfolio quick-add  | P1       | todo   | CC Core | 122    | max_sector_pct enforced in UI    | Sprint 122  |
| CCX-055 | Portfolio replacement rank             | P2       | todo   | CC Core | 124    | Sell-first ranked; human confirm | Sprint 124  |
| CCX-056 | sell_first_candidates[] on AlphaObject | P2       | todo   | CC Core | 124    | Swap discipline on IO            | Sprint 124  |
| CCX-057 | Portfolio brain IO consumer            | P2       | todo   | CC Core | 122    | Fit-delta sim uses IO            | Sprint 122  |
| CCX-058 | Crisis stress on portfolio tab         | P3       | todo   | CC Core | 122    | Regime stress visible            | Sprint 122  |
| CCX-059 | Drawdown sizer live wire               | P2       | todo   | CC Core | 122    | Sizing discipline in UI          | Sprint 122  |
| CCX-060 | Book-level capacity rollup             | P2       | todo   | CC Core | 122    | Aggregate capacity on book       | Sprint 122  |
| CCX-061 | Rebalance sim portfolio embed          | P3       | todo   | CC Core | 122    | What-if in Portfolio tab         | Sprint 122  |

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

| ID      | Item                                  | Priority | Status      | Owner   | Sprint | Acceptance criteria               | Evidence/PR   |
| ------- | ------------------------------------- | -------- | ----------- | ------- | ------ | --------------------------------- | ------------- |
| CCX-100 | Command palette ⌘K v0                 | P2       | todo        | CC Core | 120    | Launcher for surfaces             | Sprint 120    |
| CCX-101 | Keyboard shortcuts G T/P/D            | P3       | todo        | CC Core | 120    | Power-user nav                    | Sprint 120    |
| CCX-102 | Command tab best_action sync          | P1       | todo        | CC Core | 115    | Command strip = Today best_action | Backlog N7    |
| CCX-103 | Near-miss → watchlist triggers        | P1       | todo        | CC Core | 115    | POST /api/watchlist/trigger       | Backlog M9/N8 |
| CCX-104 | i18n Ops remaining strings            | P2       | todo        | CC Core | —      | HK operator UX                    | Tier 3        |
| CCX-105 | i18n completion all tabs              | P3       | todo        | CC Core | —      | Bilingual all surfaces            | Tier 3        |
| CCX-106 | Template partial split Today/Playbook | P2       | todo        | CC Core | —      | build-cc-template.mjs             | Tier 3        |
| CCX-107 | Flow synthetic watermark persistent   | P2       | todo        | CC Core | 116    | Synthetic flow labeled            | Sprint 116    |
| CCX-108 | AI Commentary collapsed by default    | P2       | in-progress | CC Core | 115    | Non-decision AI demoted           | Backlog R2    |

---

## Notifications & ops

| ID      | Item                              | Priority | Status | Owner   | Sprint | Acceptance criteria    | Evidence/PR   |
| ------- | --------------------------------- | -------- | ------ | ------- | ------ | ---------------------- | ------------- |
| CCX-110 | System Telegram BDR/regime alerts | P2       | done   | CC Core | 114    | Deploy-gate aware      | `telegram.py` |
| CCX-111 | Discord research mute default     | P2       | done   | CC Core | —      | Alert noise controlled | Observed      |
| CCX-112 | Telegram deploy-gate hardening    | P2       | todo   | CC Core | 116    | Token hygiene          | Sprint 116    |
| CCX-113 | Platform error log → Ops digest   | P3       | todo   | CC Core | 116    | Reliability digest     | Sprint 116    |

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

## Summary

| Metric                  |   Count |
| ----------------------- | ------: |
| **Total backlog items** | **108** |
| done                    |       6 |
| in-progress             |       9 |
| todo                    |      93 |
| blocked                 |       0 |

**Done:** CCX-002, CCX-003, CCX-004, CCX-110, CCX-111, CCX-128

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
