# CC X — Engineering Backlog (Single Source of Truth)

**Product:** CC X · `TradingAI_Bot`  
**Version:** 9.0.0 · **Updated:** 2026-08-25  
**Verify:** `bash scripts/verify_10_10.sh`

> All planned work lives here. Reviews update this file only — see [`CC_X_REVIEW_CYCLE.md`](./CC_X_REVIEW_CYCLE.md).

---

## Status legend

| Symbol | Meaning                                          |
| ------ | ------------------------------------------------ |
| ✅     | Shipped (API + UI or API complete)               |
| 🟡     | Partial — payload exists; depth/UI/evidence gaps |
| ❌     | Not started or deferred                          |
| ⬇️     | Keep but demote in UI hierarchy                  |

---

## P0 — Must ship next

| ID    | Item                             | Acceptance                                                              | Modules                                           | Status                |
| ----- | -------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------- | --------------------- |
| B115  | **Decision board SSOT**          | Identical `deploy_open` on Today, Playbook, cc-header                   | `decision_board_service.py`, routers, `cc-app.js` | 🟡 Sprint 115 partial |
| B116  | **Provenance on all prices**     | `source`/`as_of`/`mode` on market fields; CI blocks regression          | `market_data.py`, `brief_data_service.py`, CI     | ❌                    |
| B116b | **Mock factor hide**             | `factor_exposure.py` shows `degraded=true` or hidden on deploy surfaces | `factor_exposure.py`, portfolio router            | ❌                    |
| M9    | **Trigger-based watchlist**      | `POST /api/watchlist/trigger` from near_miss                            | watchlist API                                     | ❌                    |
| N7    | **Command tab best_action sync** | Command strip = Today `best_action`                                     | `index.html`, `cc-app.js`                         | ❌                    |

---

## P1 — High ROI (Sprints 117–122)

| Sprint  | Headline                      | Key deliverables                                           |
| ------- | ----------------------------- | ---------------------------------------------------------- |
| **117** | AlphaObject birth             | Alpha Factory writer; playbook SWR p95 &lt;2s; k6 gate     |
| **118** | Alpha monitor + learning loop | `alpha_monitor.py`, `forward_outcomes.py`, IBKR→JSONL ≥95% |
| **119** | Institutional workspace MVP   | One investment / eleven tabs; Opp Intel v3 embed           |
| **120** | Attribution + E2E             | `attribution_tree.py`; Playwright CI; board export         |
| **121** | Knowledge engine              | `knowledge_graph.py`, `analog_engine.py` MVP               |
| **122** | Capital allocation + EV 3.0   | `ev_ranking.py`; live factor wire; sector cap UI           |

### PM console gaps (from 10/10 roadmap)

| ID  | Item                                      | Status                   |
| --- | ----------------------------------------- | ------------------------ |
| N1  | Single-stock conviction stack (10 layers) | 🟡 `stock-intel` partial |
| N3  | Options intelligence depth                | 🟡                       |
| N4  | Sector rotation explain                   | 🟡                       |
| N6  | Playbook card schema in UI                | 🟡                       |
| N8  | Near-miss → watchlist triggers            | ❌                       |
| R2  | AI Commentary collapsed by default        | 🟡                       |
| R4  | KPI labels link to diagnosis              | 🟡                       |

---

## P2 — Scale & polish (Sprints 123–126)

| Sprint  | Headline                           |
| ------- | ---------------------------------- |
| **123** | Pattern library + failure modes    |
| **124** | Portfolio replacement / sell-first |
| **125** | AlphaObject lifecycle close        |
| **126** | Intelligence Engine CEO dashboard  |

---

## Quick wins (&lt;1 day each)

| Item                                 | Files                                     |
| ------------------------------------ | ----------------------------------------- |
| Thompson/ML hide n&lt;5              | `ml_advisory_summary.py`, `cc-helpers.js` |
| Flow synthetic watermark             | `flow_decision_surface.py`                |
| Telegram dedupe tune                 | `telegram.py`                             |
| Authority label server-render pass 1 | `surface_authority.py`                    |
| gzip dashboard always serve          | `_cc_instant.py`                          |

---

## Explicitly postponed

| Item                           | Reason                      |
| ------------------------------ | --------------------------- |
| Unlimited new tabs             | Hierarchy discipline        |
| AI as primary ranker           | No calibrated track record  |
| Influencer/social main feed    | Institutional positioning   |
| Auto bracket submit            | Requires IB + human confirm |
| Enterprise RBAC / multi-tenant | Long-term commercial        |

---

## Test gates (every PR)

- `pytest tests/test_operator_state_contract.py tests/test_decision_board_service.py -q`
- `bash scripts/verify_10_10.sh`
- Authority cluster must stay green before merge

---

## Archive note

Historical sprint plans, gap lists, and review duplicates live in [`archive/`](./archive/). Do not add new backlog items there.
