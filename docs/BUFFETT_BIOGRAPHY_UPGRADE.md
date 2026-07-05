# 《巴菲特传》Buffett Biography Upgrade

**Single-book mode:** 《巴菲特传》 — business judgment, owner mindset, and capital allocation only.

Clarity Console shifts from **ticker score theater** to **understand-the-business discipline**: economic quality, moat durability, management/capital allocation, circle of competence, and patience when the board says WAIT.

---

## Deepest value of the book

The biography’s deepest gift is not stock tips but a **lifetime model of rational capital allocation**: treat stocks as fractional businesses, insist on understandable economics, demand honest management, stay inside your circle of competence, and let temperament — patience, independence from crowd noise — do most of the work. For CC, that means **fewer, owner-grade decisions** backed by business judgment, not scanner rank.

---

## Biggest mistake the current system makes

CC still **promotes ranked setups as if momentum and timing scores implied ownability**, blurring the line between “interesting trade” and “business I would hold for years.” That fights Buffett’s core filter: **if you cannot explain the business and trust its economics, you do not have a position — you have a bet.** The platform can show high scores on WAIT days while the honest board correctly says no deploy — creating urgency without owner conviction.

---

## Part 1 — Diagnosis

| Area                          | Buffett fit                   | Gap                     | Remedy                                       |
| ----------------------------- | ----------------------------- | ----------------------- | -------------------------------------------- |
| Playbook rank                 | Rank ≠ ownable business       | Score-led cards         | `buffett_judgment` allocation bands          |
| Dossier                       | Thesis without business frame | Narrative ≠ owner view  | `buffett_owner_view` block                   |
| Dashboard                     | Competing urgency strips      | Attention on noise      | `buffett_clarity` patience/selectivity       |
| Fundamentals panel            | Data present, judgment thin   | No quality/moat summary | Business + moat heuristics                   |
| 巴芒 mode (`value_investing`) | Overlapping vocabulary        | Two value books mixed   | Separate `buffett_*` layer; 巴芒 unchanged   |
| Naval / Turtle books          | Orthogonal                    | Must not mix copy       | Buffett-only labels in `buffett_judgment.py` |

**Demote (label, don’t remove):** TRADE hints when `portfolio_worthiness` is `inferior` or `watch`; momentum tags without `business_quality` ≥ medium.

---

## Part 2 — Product redefinition

**Before:** “What should I trade today?” driven by scanner rank and timing.

**After:** “Would I **own this business** at this price with this understanding?” — capital goes to **ownable** names; others are study, watch, or inferior to cash/index.

**Principles (operator):**

1. Understand the business in plain language before sizing.
2. Economic quality and moat durability beat narrative.
3. Management matters — capital allocation is part of the investment.
4. Stay inside circle of competence; outside = study or pass.
5. Patience when board WAIT — **no action** is often the best allocation.
6. Hold as owner; trim on extension; exit watch when thesis breaks.

---

## Part 3 — Architecture (8 engines)

```
Board gate (L1) — honest tradeability unchanged
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  evaluate_business        → summary, quality, moat  │
│  evaluate_management      → allocation proxy/stub   │
│  evaluate_buffett_competence → circle fit           │
│  evaluate_allocation      → ownable/study/watch/... │
│  evaluate_temperament     → noise, action necessity │
│  evaluate_hold_sell       → hold/trim/exit watch    │
│  build_buffett_owner_view → Dossier block           │
│  buffett_clarity_strip_for_today → /today           │
└─────────────────────────────────────────────────────┘
        │
        ├── tags_for_playbook_row → Playbook pills
        └── build_buffett_owner_view → Dossier
```

**Module:** `src/services/buffett_judgment.py` (consolidated; max one file for ROI pass).

| Engine      | Function                          | Output                                      |
| ----------- | --------------------------------- | ------------------------------------------- |
| Business    | `evaluate_business`               | `business_quality`, `moat`, summary         |
| Management  | `evaluate_management`             | `management_grade`, note                    |
| Competence  | `evaluate_buffett_competence`     | `competence_fit` inside/partial/outside     |
| Allocation  | `evaluate_allocation`             | `allocation_action`, `portfolio_worthiness` |
| Temperament | `evaluate_temperament`            | `noise_high`, `action_necessary`            |
| Hold/sell   | `evaluate_hold_sell`              | `hold_stance`                               |
| Owner view  | `build_buffett_owner_view`        | Dossier `buffett_owner_view`                |
| Today strip | `buffett_clarity_strip_for_today` | `buffett_clarity` on dashboard              |

---

## Part 4 — Page-by-page

| Page                   | Buffett behavior                                                                    |
| ---------------------- | ----------------------------------------------------------------------------------- |
| **Dashboard `/today`** | `buffett_clarity`: patience, selectivity, what matters (ownable names)              |
| **Playbook**           | Pills: `business_quality`, `buffett_competence_fit`, `portfolio_worthiness`         |
| **Dossier**            | `buffett_owner_view`: business summary, quality, moat, mgmt, competence, allocation |
| **Guide**              | One line under Global Principles + link to this doc                                 |
| **Portfolio / Funds**  | Deferred — inherit board gate; owner view on dossier only                           |
| **Ops**                | No change                                                                           |

---

## Part 5 — Fields & scores

| Field                         | Values                                       | Source heuristics                         |
| ----------------------------- | -------------------------------------------- | ----------------------------------------- |
| `business_quality`            | high, medium, low                            | thesis, fundamentals flags, story_broken  |
| `moat`                        | likely, unclear                              | thesis, extension, quality                |
| `management_grade`            | acceptable_proxy, unknown                    | growth/story proxies                      |
| `competence_fit`              | inside, partial, outside                     | sector familiarity, thesis, calibration n |
| `allocation_action`           | ownable, study, watch, inferior              | quality + competence + score + board      |
| `portfolio_worthiness`        | same as allocation_action                    | alias for UI                              |
| `hold_stance`                 | hold_owner, trim_extended, exit_watch, watch | thesis, extension, position               |
| `buffett_clarity.patience`    | bool                                         | WAIT + noise detector                     |
| `buffett_clarity.selectivity` | high, normal                                 | deployable count + board                  |

**No Buffett composite score** — avoids another theater metric.

---

## Part 6 — Copy (calm, owner-tone)

| Context            | Copy                                                                |
| ------------------ | ------------------------------------------------------------------- |
| WAIT + high scores | “Market noise high — action not required”                           |
| Default patience   | “Patience is the position — wait for clarity”                       |
| Ownable            | “Ownable — fits concentrated owner book”                            |
| Study              | “Study pile — not yet ownable”                                      |
| Outside competence | “Outside circle — study or pass”                                    |
| Inferior           | “Inferior use of capital vs cash or index”                          |
| Strip banner       | “Patience and selectivity — understand the business before capital” |

Tone: **understated, owner-long-term**. Never FOMO on WAIT days.

---

## Part 7 — File plan

| File                                   | Role                                            |
| -------------------------------------- | ----------------------------------------------- |
| `docs/BUFFETT_BIOGRAPHY_UPGRADE.md`    | This doc                                        |
| `src/services/buffett_judgment.py`     | All engines + strip + dossier + playbook tags   |
| `src/services/decision_truth_model.py` | `tags_for_playbook_row` hook                    |
| `src/api/routers/decision.py`          | `buffett_clarity` on `/today`                   |
| `src/services/stock_intel.py`          | `buffett_owner_view` on dossier payload         |
| `src/api/templates/index.html`         | Strip, playbook pills, dossier card, guide line |
| `tests/test_buffett_judgment.py`       | Unit tests                                      |

**Coexistence:** `value_investing.py` (巴芒) remains; do not merge book copy.

---

## Part 8 — ROI roadmap

| Phase | Deliverable                                  | Status           |
| ----- | -------------------------------------------- | ---------------- |
| P0    | Doc + `buffett_judgment.py` + tests          | Done (this pass) |
| P0    | Playbook tags + dossier `buffett_owner_view` | Done             |
| P0    | Dashboard `buffett_clarity` strip            | Done             |
| P1    | Guide one-liner                              | Done             |
| P2    | Owner-earnings / filing-backed mgmt grade    | Deferred         |
| P2    | Calibrated ownable hit-rate when n ≥ 30      | Deferred         |
| P3    | Portfolio-level concentration vs owner book  | Deferred         |

---

## Part 9 — Deferred / out of scope

- Full DCF or intrinsic value bands (use fundamentals feed later)
- Automated 10-K management scoring
- Merging with `value_investing.py` or Naval modules
- Heavy new Guide cards (doc link only)

---

## Cross-reference

- `docs/BAMANG_VALUE_INVESTING_UPGRADE.md` — Graham/Munger value band (orthogonal)
- `docs/NAVAL_ALMANAC_UPGRADE.md` — bandwidth / signal-light (orthogonal)
- `docs/PLATFORM_UPGRADE_AUDIT.md` — L1–L5 hierarchy
