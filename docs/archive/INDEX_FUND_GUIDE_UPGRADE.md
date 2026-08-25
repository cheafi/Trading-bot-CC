# 《指数基金投资指南》Index Fund Investment Guide Upgrade

**Single-book mode:** 《指数基金投资指南》 — index valuation, 定投 discipline, and core allocation only.

Clarity Console shifts from **tactical sleeve theater** to **ordinary-investor index posture**: broad-market core, PE-percentile valuation zones (cheap/fair/expensive), calm 定投 / hold / pause — not stock-picking urgency.

---

## Deepest value of the book

The guide’s deepest gift is **permission to do less and win slowly**: hold broad, low-cost index funds as the default wealth engine, use valuation history (not headlines) to modulate 定投 intensity, keep satellite bets small, and accept that most investors fail by trading too much. For CC, that means **core index posture leads the Funds tab and dashboard** — tactical sleeves and playbook ranks are supporting context, not deploy authority.

---

## Biggest mistake the current system makes

CC still **elevates tactical fund sleeves and stock-trading playbook language on the Funds surface**, implying regime-fit momentum sleeves deserve the same urgency as a passive investor’s core index book. That fights the book’s message: **for ordinary investors, broad index + steady 定投 beats timing and sector rotation**. The platform can show ACTIVE tactical sleeves while the honest index posture correctly says continue 定投 or pause — creating false urgency without valuation discipline.

---

## Part 1 — Diagnosis

| Area                     | Index-fund fit              | Gap                             | Remedy                                             |
| ------------------------ | --------------------------- | ------------------------------- | -------------------------------------------------- |
| Funds tab                | Tactical sleeve rank first  | PM/trading copy dominates       | `index_fund_posture` + per-card `index_fund_layer` |
| Dashboard `/today`       | No index valuation strip    | Stock urgency strips compete    | `index_fund_posture_strip_for_today`               |
| Playbook                 | Stock scores on all rows    | Index ETFs mixed with trades    | `tags_for_playbook_row` only for ETF/index symbols |
| Portfolio core/satellite | Role tags without valuation | Core band lacks 定投 guidance   | `index_fund_alignment_for_core_satellite`          |
| PE / valuation           | Raw PE without zone         | No cheap/fair/expensive frame   | PE percentile proxy in `evaluate_valuation_zone`   |
| Ordinary investor        | Implicit pro-trader UX      | Narrow/sector treated like core | `evaluate_ordinary_investor_suitability`           |

**Demote (label, don’t remove):** tactical sleeve DEPLOY/ADD as primary Funds headline; stock-trading playbook as index path; regime-fit urgency when valuation zone is fair.

---

## Part 2 — Product redefinition

**Before:** “Which sleeve should I deploy today?” driven by backtest regime fit.

**After:** “What is my **index core posture** at this valuation — continue 定投, hold, or pause?” — capital discipline for passive book; sleeves are research only.

**Principles (operator):**

1. Broad market index is the default core — narrow/sector is satellite only.
2. Valuation zones (cheap/fair/expensive) modulate 定投 — not panic trading.
3. Expensive zone → pause new 定投, hold existing; cheap zone → steady or lump-sum adds (sized calmly).
4. No urgent action is often correct — index investing rewards patience.
5. Ordinary-investor suitability beats tactical complexity.
6. All PE/scope labels are **proxy** — external index history is ground truth.

---

## Part 3 — Architecture (7 engines)

```
Board gate (L1) — honest tradeability unchanged
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  classify_index_fund      → broad / narrow / not    │
│  evaluate_valuation_zone  → cheap / fair / expensive│
│  evaluate_investment_mode → 定投 / hold / pause       │
│  evaluate_core_satellite_role → core / satellite    │
│  evaluate_ordinary_investor_suitability             │
│  evaluate_allocation_decision → full bundle           │
│  index_fund_posture_strip_for_today → /today        │
└─────────────────────────────────────────────────────┘
        │
        ├── enrich_funds_console_index_layer → Funds tab
        ├── tags_for_playbook_row → ETF/index rows only
        └── index_fund_alignment_for_core_satellite → Portfolio
```

**Module:** `src/services/index_fund_judgment.py` (consolidated; single file for ROI pass).

| Engine          | Function                                 | Output                                         |
| --------------- | ---------------------------------------- | ---------------------------------------------- |
| Classification  | `classify_index_fund`                    | `classification`, `scope`, `is_index`          |
| Valuation       | `evaluate_valuation_zone`                | `valuation_zone`, `pe_percentile_proxy`        |
| Investment mode | `evaluate_investment_mode`               | `action`: continue_dca / hold_core / pause_dca |
| Core/satellite  | `evaluate_core_satellite_role`           | `core_satellite_role`                          |
| Suitability     | `evaluate_ordinary_investor_suitability` | `suitability`                                  |
| Allocation      | `evaluate_allocation_decision`           | Full bundle + headline                         |
| Today strip     | `index_fund_posture_strip_for_today`     | `index_fund_posture` on dashboard              |

---

## Part 4 — Page-by-page

| Page                   | Index-fund behavior                                                             |
| ---------------------- | ------------------------------------------------------------------------------- |
| **Dashboard `/today`** | `index_fund_posture`: core priority, valuation summary, no urgent action        |
| **Funds**              | Top strip: benchmark zone + action; cards: `index_fund_layer`; tactical demoted |
| **Playbook**           | Pills only on ETF/index rows: scope, zone, action                               |
| **Portfolio**          | `core_satellite.index_fund_alignment` on core passive band                      |
| **Dossier**            | Deferred — index tags via playbook row hook only                                |
| **Guide**              | Deferred one-liner — doc link                                                   |

---

## Part 5 — Fields & scores

| Field                                       | Values                                | Source heuristics              |
| ------------------------------------------- | ------------------------------------- | ------------------------------ |
| `classification`                            | broad, narrow, not_index              | ticker set, name/sector tags   |
| `valuation_zone`                            | cheap, fair, expensive, unknown       | PE percentile proxy            |
| `pe_percentile_proxy`                       | 0–100                                 | row metadata or raw PE mapping |
| `action`                                    | continue_dca, hold_core, pause_dca    | zone → mode table              |
| `investment_mode`                           | dca, dca_and_lump_sum, hold           | alias bundle                   |
| `core_satellite_role`                       | core, satellite, none                 | broad vs narrow                |
| `suitability`                               | highly_suitable, caution, not_primary | scope + sleeve type            |
| `index_fund_posture.urgent_action_required` | always false                          | calm copy policy               |

**No index composite score** — avoids another theater metric. All fields carry `proxy: true` where applicable.

---

## Part 6 — Copy (calm, ordinary-investor tone)

| Context          | Copy                                                                          |
| ---------------- | ----------------------------------------------------------------------------- |
| Default headline | “no urgent action — index investing rewards patience”                         |
| Banner           | “core index priority over stock picking today”                                |
| Cheap zone       | “valuation cheap zone — favor steady 定投 (PE percentile proxy)”              |
| Fair zone        | “valuation fair zone — continue 定投, no urgency”                             |
| Expensive zone   | “pause new 定投 — expensive zone proxy; hold existing”                        |
| Broad index      | “broad market index — core book candidate (proxy)”                            |
| Narrow index     | “narrow/sector index — satellite only (proxy)”                                |
| Funds note       | “Index posture (定投/hold/pause) takes priority over tactical sleeve signals” |

Tone: **understated, long-horizon**. Never FOMO on fair/expensive zones.

---

## Part 7 — File plan

| File                                   | Role                                               |
| -------------------------------------- | -------------------------------------------------- |
| `docs/INDEX_FUND_GUIDE_UPGRADE.md`     | This doc                                           |
| `src/services/index_fund_judgment.py`  | All engines + strip + funds enrich + playbook tags |
| `src/services/fund_manager_console.py` | Calls `enrich_funds_console_index_layer`           |
| `src/api/routers/decision.py`          | `index_fund_posture` on `/today`                   |
| `src/services/decision_truth_model.py` | Optional `tags_for_playbook_row` hook              |
| `src/services/core_satellite.py`       | `index_fund_alignment` on summary                  |
| `src/api/templates/index.html`         | Dashboard strip + Funds index layer UI             |
| `tests/test_index_fund_judgment.py`    | Unit tests                                         |

**Coexistence:** `fund_manager_console` tactical sleeves remain research-only; index layer sits above Zone A.

---

## Part 8 — ROI roadmap

| Phase | Deliverable                                           | Status           |
| ----- | ----------------------------------------------------- | ---------------- |
| P0    | Doc + `index_fund_judgment.py` + tests                | Done (this pass) |
| P0    | Funds tab index layer + demoted tactical framing      | Done             |
| P0    | Dashboard `index_fund_posture` strip                  | Done             |
| P0    | Playbook ETF-only tags                                | Done             |
| P1    | Portfolio `index_fund_alignment` on core_satellite    | Done             |
| P2    | Live index PE percentile feed (CSI 300 / SPY history) | Deferred         |
| P2    | Per-fund factsheet cost/expense overlay               | Deferred         |
| P3    | Dossier block for held index ETFs                     | Deferred         |

---

## Part 9 — Deferred / out of scope

- Live historical PE percentile API (CSI 300, S&P 500 full series)
- Automatic 定投 scheduler / broker 定投 integration
- Merging with `passive_baseline.py` or Buffett/Naval modules
- Replacing fund-lab backtest sleeves — demoted, not removed
- Heavy new Guide cards (doc link only in P1)

---

## Cross-reference

- `docs/BUFFETT_BIOGRAPHY_UPGRADE.md` — owner stock judgment (orthogonal)
- `docs/BAMANG_VALUE_INVESTING_UPGRADE.md` — single-stock value (orthogonal)
- `src/services/passive_baseline.py` — SPY/QQQ humility strip (complementary)
- `src/services/core_satellite.py` — sleeve role architecture (linked)
