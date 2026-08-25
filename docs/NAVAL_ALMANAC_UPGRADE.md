# 《纳瓦尔宝典》Naval Almanac Upgrade

**Single-book mode:** 《纳瓦尔宝典》 (Naval Ravikant) — judgment-first, leverage-aware, signal-light only.

Clarity Console shifts from **scanner urgency theater** to **specific knowledge, mental bandwidth discipline, and calm compounding**: act rarely, think deeply when edge is asymmetric, ignore noise when the board says WAIT.

---

## Deepest value of the book

Naval’s core gift is not stock-picking tips but an **operating system for wealth and peace**: build specific knowledge you cannot outsource, apply leverage (code, media, capital, judgment) instead of trading time for money, and treat happiness as the absence of false urgency. For CC, that translates into **fewer, stronger decisions** — the platform should protect the operator’s attention, not manufacture reasons to click.

---

## Biggest mistake the current system makes

CC still **ranks and surfaces too many “interesting” names as if rank implied action**, creating borrowed conviction from scores, narratives, and color-coded cards. That contradicts Naval’s bandwidth ethic and fights honest gates (WAIT, research-only): the UI can feel urgent while the board correctly says **no action required**. This upgrade adds a **signal-light layer** that demotes noise, flags false urgency, and names competence fit before any deploy hint.

---

## Part 1 — Diagnosis

| Area                  | Naval fit                          | Gap                                    | Remedy                                       |
| --------------------- | ---------------------------------- | -------------------------------------- | -------------------------------------------- |
| Board WAIT / NO_TRADE | Peace is a position                | High-score cards still feel actionable | `calm_reactive_mode` false-urgency strip     |
| Playbook rank         | Not all ranked rows earn bandwidth | Score ≠ specific knowledge             | `signal_to_noise`, `specific_knowledge` tags |
| Dossier narrative     | Story ≠ owned edge                 | Long why_now, weak data                | `borrowed_conviction_risk`                   |
| Dashboard strips      | Too many competing banners         | Attention fragmentation                | Single `naval_clarity` strip                 |
| Turnover / monitoring | Activity ≠ edge                    | Long watch lists                       | `compounding_priority`                       |
| Leverage              | Manual churn                       | Discretionary heroics                  | `leverage_engine` labels                     |
| Honest gates          | Already correct                    | Naval must align, not override         | Authority stays research/supportive          |

**Demote (label, don’t remove):** momentum tags without competence fit; deploy hints when `signal_to_noise` is `ignore` or `noise`; any copy that sounds like “act now” on WAIT days.

---

## Part 2 — Product redefinition

**Before:** “What should I trade today?” driven by ranked scanner output.

**After:** “What deserves my judgment bandwidth today?” — at most one or two names under `act_now` / `think_deeply`; everything else is monitor lightly, ignore, or noise.

**Principles (operator):**

1. Specific knowledge > borrowed conviction (scores, influencers, AI narrative).
2. Leverage process and judgment; avoid labor-style screen churn.
3. False urgency is expensive (peace cost).
4. Compounding patience when deploy path is closed.
5. Align with WAIT — **no action required** is success, not failure.

---

## Part 3 — Architecture (7 engines)

```
Board gate (L1) — unchanged honest tradeability
        │
        ▼
┌───────────────────────────────────────────────────┐
│  signal_to_noise        → act / think / monitor / │
│  specific_knowledge     → competence, borrowed    │
│  opportunity_quality_naval → durability, asymmetry│
│  decision_quality_naval → clarity, known unknowns │
│  leverage_engine        → process/automation/judg.│
│  calm_reactive_mode     → peace cost, false urg.  │
│  compounding_priority   → compound vs turnover    │
└───────────────────────────────────────────────────┘
        │
        ├── naval_clarity_strip_for_today → /today
        ├── tags_for_playbook_row (×3) → Playbook rows
        └── build_naval_thinking → Dossier naval_thinking
```

| Engine              | Module                         | Output                                 |
| ------------------- | ------------------------------ | -------------------------------------- |
| Signal / noise      | `signal_to_noise.py`           | 5-band classification                  |
| Specific knowledge  | `specific_knowledge.py`        | `competence_fit`, borrowed risk        |
| Opportunity quality | `opportunity_quality_naval.py` | durability, asymmetry, bandwidth       |
| Decision quality    | `decision_quality_naval.py`    | clarity, known unknowns, strip/dossier |
| Leverage            | `leverage_engine.py`           | process / automation / judgment        |
| Calm vs reactive    | `calm_reactive_mode.py`        | false urgency, preserve focus          |
| Compounding         | `compounding_priority.py`      | patience vs turnover noise             |

---

## Part 4 — Page-by-page

| Page                   | Naval behavior                                                                          |
| ---------------------- | --------------------------------------------------------------------------------------- |
| **Dashboard `/today`** | `naval_clarity` strip: what matters, action necessity, preserve focus, compounding note |
| **Playbook**           | Pills: `signal_to_noise`, `competence_fit`, `mental_bandwidth_worthy`                   |
| **Dossier**            | `naval_thinking` block: 30s summary, signal, competence, known unknowns                 |
| **Guide**              | One line under Global Principles + doc link — no new heavy card                         |
| **Portfolio / Funds**  | Deferred — inherit board gate only                                                      |
| **Ops**                | No change                                                                               |

---

## Part 5 — Fields & scores

| Field                      | Values                                                | Source heuristics                          |
| -------------------------- | ----------------------------------------------------- | ------------------------------------------ |
| `signal_to_noise`          | act_now, think_deeply, monitor_lightly, ignore, noise | action, exec_ready, thesis, board          |
| `competence_fit`           | strong_fit, partial_fit, borrowed, outside            | thesis, data_conf, calibration_n           |
| `borrowed_conviction_risk` | low, medium, high                                     | narrative length vs thesis                 |
| `mental_bandwidth_worthy`  | bool                                                  | thesis + R:R or timing                     |
| `naval_durability`         | durable, fragile                                      | thesis + extension                         |
| `naval_asymmetry`          | asymmetric, symmetric                                 | R:R threshold                              |
| `decision_clarity`         | high, medium, low                                     | confidence spread                          |
| `known_unknowns`           | string[]                                              | timing gap, data gap, missing invalidation |
| `leverage_type`            | process, automation, judgment, labor                  | surface + action                           |
| `peace_cost`               | low, medium, high                                     | false urgency detector                     |
| `compounding_vs_noise`     | compound, turnover_noise, mixed                       | board + deployable count                   |

**No new numeric “Naval score”** — avoids another theater metric.

---

## Part 6 — Copy (calm, anti-hype)

| Context            | Copy                                                           |
| ------------------ | -------------------------------------------------------------- |
| WAIT + high scores | “False urgency detected — high scores without deploy path”     |
| Default calm       | “Peace is the position. No action required until board opens.” |
| Bandwidth          | “Defer bandwidth” / “worth mental bandwidth today”             |
| Competence         | “borrowed conviction — verify before acting”                   |
| Compounding        | “Patience compounds — cash and focus are positions”            |
| Strip banner       | “Monitor lightly. Reacting to noise has a peace cost.”         |

Tone: **understated, never FOMO**. Suppress “act now” unless `act_now` band AND board TRADE.

---

## Part 7 — File plan

| File                                        | Role                                       |
| ------------------------------------------- | ------------------------------------------ |
| `docs/NAVAL_ALMANAC_UPGRADE.md`             | This doc                                   |
| `src/services/signal_to_noise.py`           | 5-band classifier                          |
| `src/services/specific_knowledge.py`        | Competence fit                             |
| `src/services/opportunity_quality_naval.py` | Durability / asymmetry / bandwidth         |
| `src/services/decision_quality_naval.py`    | Clarity, strip, dossier builder            |
| `src/services/leverage_engine.py`           | Leverage labels                            |
| `src/services/calm_reactive_mode.py`        | False urgency                              |
| `src/services/compounding_priority.py`      | Compound vs churn                          |
| `src/services/decision_truth_model.py`      | Playbook enrich hooks                      |
| `src/api/routers/decision.py`               | `naval_clarity` on `/today`                |
| `src/services/stock_intel.py`               | `naval_thinking` on dossier                |
| `src/api/templates/index.html`              | Strip, playbook pills, dossier, guide line |
| `tests/test_naval_modules.py`               | Unit tests                                 |

---

## Part 8 — ROI roadmap

| Phase | Item                                                | Status   |
| ----- | --------------------------------------------------- | -------- |
| P0    | 7 engines + doc + tests                             | Done     |
| P0    | Dashboard `naval_clarity` strip                     | Done     |
| P0    | Playbook tags (3 fields)                            | Done     |
| P0    | Dossier `naval_thinking`                            | Done     |
| P1    | Guide one-liner under Global Principles             | Done     |
| P2    | User-declared circle of competence (settings)       | Deferred |
| P2    | Bandwidth budget (# tickers/day cap)                | Deferred |
| P3    | Calibrated “borrowed conviction” from outcome audit | Deferred |

---

## Part 9 — Authority & gates

- Naval layer is **supportive** — never overrides L1 board WAIT / NO_TRADE.
- `act_now` band still requires existing execution_ready + TRADE path.
- Dossier `authority`: `research_only` when signal is ignore/noise.
- Do **not** mix Turtle, 巴芒, 乱世, Nison, Random Walk logic into Naval modules (orthogonal book modes).

---

## Part 10 — Cross-reference

- `docs/PLATFORM_UPGRADE_AUDIT.md` — L1–L5 hierarchy
- `docs/RANDOM_WALK_PLATFORM_PROMPT.md` — humility vocabulary (complementary, not merged)
- `src/services/anti_overtrading.py` — restraint banner (align copy)
- `src/services/humility_labels.py` — shared guardrail labels on playbook rows

---

## Deferred (explicit)

- Settings-backed circle of competence per user
- Daily mental bandwidth quota UI
- Naval-specific outcome calibration
- Portfolio/Funds Naval panels
