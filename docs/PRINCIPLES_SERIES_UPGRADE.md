# 《原则系列（共2册）》Principles Series Upgrade

**Single-book mode:** 《原则系列（共2册）》 (Ray Dalio — _Principles_) — radical transparency, believability-weighted decisions, machine-like process, pain-plus-reflection learning.

Clarity Console shifts from **outcome-chasing and narrative conviction** to **truth integrity, process quality independent of P&L, and a machine-of-machines decision OS**: act only when facts, evidence, and principles align — and when honest gates already permit.

---

## Deepest value of the book

Dalio’s gift is not a trading tactic but a **repeatable decision machine**: separate what you know from what you guess, weight evidence by believability, run decisions through explicit principles, and treat pain as data that updates the machine. For CC, that means **transparency over theater** — the platform should show fact vs stale vs unknown, grade the _process_ of each decision, and block action when principles fail even if scores look attractive.

---

## Biggest mistake the current system makes

CC still **treats ranked output and high scores as implicit permission to act**, blending estimated model priors with verified facts and rarely naming what is unknown before sizing. That contradicts radical transparency and fights honest gates (WAIT, research-only): the UI can show deploy hints while the board correctly says **no action required**. This upgrade adds a **Principles layer above gates** — it never overrides WAIT, but makes deferral explicit with governing principles, evidence grades, and machine health.

---

## Part 1 — Diagnosis

| Area                  | Principles fit         | Gap                                  | Remedy                                                    |
| --------------------- | ---------------------- | ------------------------------------ | --------------------------------------------------------- |
| Board WAIT / NO_TRADE | Process over outcome   | Scores still feel actionable         | `principles_posture` — action blocked by principle        |
| Playbook rank         | Believability-weighted | Rank ≠ evidence quality              | `principle_support`, `evidence_quality`, `decision_grade` |
| Dossier narrative     | Radical transparency   | Long why_now, weak fact labels       | `principles_memo` — known facts vs unknowns               |
| Ops / infra           | Machine consistency    | Component probes ≠ decision machines | `decision_machines` health panel                          |
| Error log             | Pain + reflection      | Events without root cause or lesson  | `root_cause` + `lesson` on platform_error_log             |
| Honest gates          | Already correct        | Principles must align, not override  | Authority stays research/supportive; L1 gate binds        |

**Demote (label, don’t remove):** deploy hints when `decision_grade` is C/D; full-size language when `truth_integrity` is stale/unknown; any copy that treats rank as conviction without evidence tier.

---

## Part 2 — Product redefinition

**Before:** “What should I trade today?” driven by ranked scanner output and outcome anxiety.

**After:** “What does the decision machine allow today?” — facts verified, evidence believable, process graded, machines healthy; deferral is success when gates or principles block.

**Principles (operator):**

1. Radical transparency — label fact / stale / estimated / unknown before acting.
2. Believability-weighted evidence — calibration and sample size matter more than narrative.
3. Process over outcome — grade the decision process, not yesterday’s P&L.
4. Machine consistency — eight decision machines with explicit constraints.
5. Pain plus reflection — every failure logs root cause and a lesson.
6. Align with WAIT — **no action required** is correct when principles or gates block.

---

## Part 3 — Architecture (9 engines + machine-of-machines)

```
Board gate (L1) — unchanged honest tradeability
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│  truth_integrity          → fact / stale / estimated / unk │
│  evidence_weighting       → high / medium / low / insuff.  │
│  decision_quality         → grade A–D (process, not P&L)   │
│  principles_engine        → allowed / deferred / blocked   │
│  root_cause_analysis      → classify failure modes         │
│  principles_learning      → pain log + lesson encoding     │
└────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────── Machine-of-machines ────────────────────────┐
│ Data Integrity │ Regime │ Playbook │ Dossier │ Portfolio   │
│ Execution │ Review │ Learning                                 │
│  each: health + constraint                                   │
└────────────────────────────────────────────────────────────┘
        │
        ├── principles_posture → /today
        ├── tags_for_playbook_row → Playbook rows
        ├── build_principles_memo → Dossier
        └── machines_health → Ops console
```

| Engine             | Module                                                           | Output                             |
| ------------------ | ---------------------------------------------------------------- | ---------------------------------- |
| Truth integrity    | `principles_engine.classify_truth_integrity`                     | fact / stale / estimated / unknown |
| Evidence weighting | `principles_engine.score_evidence_weight`                        | believability tier                 |
| Decision quality   | `principles_engine.evaluate_decision_quality_principles`         | grade A–D                          |
| Decision posture   | `principles_engine.evaluate_decision_posture`                    | allowed / deferred / blocked       |
| Root cause         | `principles_engine.classify_root_cause`                          | failure class + lesson             |
| Learning loop      | `principles_engine.log_principles_lesson` + `platform_error_log` | persisted pain log                 |
| Principles strip   | `principles_engine.principles_posture_for_today`                 | dashboard posture                  |
| Dossier memo       | `principles_engine.build_principles_memo`                        | 30s principles block               |
| Machine registry   | `decision_machines.py`                                           | 8 machines, health + constraint    |

---

## Part 4 — Page-by-page

| Page                   | Principles behavior                                                                    |
| ---------------------- | -------------------------------------------------------------------------------------- |
| **Dashboard `/today`** | `principles_posture`: governing principle, fact integrity, action blocked by principle |
| **Playbook**           | Pills: `principle_support`, `evidence_quality`, `decision_grade`                       |
| **Dossier**            | `principles_memo`: known facts, unknowns, evidence weight, principle-based decision    |
| **Ops**                | `machines_health` panel — 8 machines with health + constraint                          |
| **Ops → Error Log**    | `root_cause` + `lesson` on each entry when logged via principles path                  |
| **Guide**              | One line under Global Principles + doc link — deferred                                 |
| **Portfolio / Funds**  | Deferred — inherit board gate + machine constraints only                               |

---

## Part 5 — Fields & scores

| Field                 | Values                               | Source heuristics                                      |
| --------------------- | ------------------------------------ | ------------------------------------------------------ |
| `truth_integrity`     | fact, stale, estimated, unknown      | data_conf, freshness, levels                           |
| `evidence_quality`    | high, medium, low, insufficient      | thesis/timing/data + calibration_n                     |
| `decision_grade`      | A, B, C, D                           | process checklist (invalidation, unknowns, objections) |
| `principles_posture`  | allowed, deferred, blocked           | gate + truth + evidence + grade                        |
| `principle_support`   | strong, partial, weak                | maps from posture                                      |
| `governing_principle` | tag from tradeability                | WAIT → process_over_outcome                            |
| `root_cause`          | data_failure, process_gap, …         | text classification on log                             |
| `lesson`              | string                               | pain-plus-reflection copy                              |
| Machine `health`      | healthy, degraded, blocked, inactive | ops + today + error log signals                        |

**No new numeric “Principles score”** — avoids another theater metric.

---

## Part 6 — Copy (calm, anti-hype)

| Context            | Copy                                                                  |
| ------------------ | --------------------------------------------------------------------- |
| WAIT + high scores | “Action blocked by principle — board says WAIT; process over outcome” |
| Stale data         | “Radical transparency: refresh facts before sizing”                   |
| Grade C/D          | “Process thin — research only until gaps close”                       |
| Allowed path       | “Principle path open — process and evidence align with gate”          |
| Machine blocked    | “Respect machine constraint — fix upstream before deploy”             |
| Error lesson       | “Encode this failure in the decision machine — pain plus reflection”  |

Tone: **understated, never FOMO**. Suppress “act now” unless posture is `allowed` AND board TRADE.

---

## Part 7 — File plan

| File                                   | Role                                                    |
| -------------------------------------- | ------------------------------------------------------- |
| `docs/PRINCIPLES_SERIES_UPGRADE.md`    | This doc                                                |
| `src/services/principles_engine.py`    | Truth, evidence, quality, posture, memo, learning hooks |
| `src/services/decision_machines.py`    | 8-machine registry + Ops health panel                   |
| `src/services/platform_error_log.py`   | `root_cause` + `lesson` fields                          |
| `src/services/decision_truth_model.py` | Playbook enrich hooks                                   |
| `src/api/routers/decision.py`          | `principles_posture` on `/today`                        |
| `src/services/stock_intel.py`          | `principles_memo` on dossier                            |
| `src/services/ops_operator_console.py` | `machines_health` on ops console                        |
| `src/api/templates/index.html`         | Strip, playbook pills, dossier, ops panel, error log    |
| `tests/test_principles_engine.py`      | Unit tests                                              |

Consolidated from six planned modules into **two service files** (`principles_engine.py`, `decision_machines.py`) plus `platform_error_log` extension.

---

## Part 8 — ROI & rollout

| Surface                                     | ROI                                                          | Status       |
| ------------------------------------------- | ------------------------------------------------------------ | ------------ |
| `/today` principles_posture                 | High — single strip names governing principle + block reason | **Wired**    |
| Playbook tags                               | High — demotes rank-as-conviction on every row               | **Wired**    |
| Dossier principles_memo                     | High — 30s fact/unknown/evidence before sizing               | **Wired**    |
| Ops machines health                         | Medium — operator sees machine constraints at a glance       | **Wired**    |
| Error log lessons                           | Medium — closes pain-plus-reflection loop                    | **Wired**    |
| Guide card                                  | Low                                                          | **Deferred** |
| Portfolio machine deep-dive                 | Medium                                                       | **Deferred** |
| Review machine post-trade UI                | Medium                                                       | **Deferred** |
| Automated machine rule updates from lessons | High long-term                                               | **Deferred** |

**Alignment with honest gates:** Principles layer sits **above** L1 tradeability — when `honest_tradeability` is WAIT, posture is always `blocked` with reason “board gate”. Naval/Buffett/Turtle modules remain separate; no cross-book copy in Principles modules.

---

## Part 9 — Machine-of-machines map

| Machine            | Role                         | Constraint                     |
| ------------------ | ---------------------------- | ------------------------------ |
| **Data Integrity** | Facts vs stale vs estimated  | No action on unknown/stale     |
| **Regime**         | Macro gate, tradeability     | WAIT binds all downstream      |
| **Playbook**       | Ranked opps + principle tags | Rank ≠ permission              |
| **Dossier**        | Single-name memo             | Grade C/D → research only      |
| **Portfolio**      | Fit and sizing               | Cannot override regime         |
| **Execution**      | Broker handoff               | No live without tested path    |
| **Review**         | Process vs outcome audit     | Judge process, not P&L         |
| **Learning**       | Pain log + lessons           | Every failure → machine update |

Registry: `src/services/decision_machines.py` — `MACHINE_CATALOG`, `evaluate_machine_health`, `build_machines_health_panel`.

---

## Test plan

```bash
pytest tests/test_principles_engine.py -q
```

Coverage: truth integrity, evidence tiers, process grades, posture on WAIT vs TRADE, playbook tags, today strip, dossier memo, root cause logging, eight-machine panel.
