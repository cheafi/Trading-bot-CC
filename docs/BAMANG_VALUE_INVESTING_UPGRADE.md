# 《巴芒演义》Value Investing Upgrade

**Single-book mode:** 《巴芒演义》 — Buffett / Munger / Graham lineage only.

Clarity Console shifts from **momentum score theater** to **business-owner discipline**: quality, valuation band, margin of safety, and patience when the board says WAIT.

---

## 1. Product diagnosis

### Already aligned (keep)

| Area                           | Why it fits 巴芒                               |
| ------------------------------ | ---------------------------------------------- |
| `passive_baseline` strip       | Active must beat SPY/QQQ or justify complexity |
| `anti_overtrading` / restraint | Cash is a valid allocation                     |
| `humility_labels`              | "likely priced in", "research signal only"     |
| Dossier thesis + invalidation  | Owner mindset — what breaks the thesis         |
| Board WAIT / NO_TRADE          | Patience when edge is thin                     |

### Violates or conflicts (fix)

| Area                         | Gap                     | Remedy                                   |
| ---------------------------- | ----------------------- | ---------------------------------------- |
| Scanner rank as buy signal   | Score ≠ intrinsic value | `value_investing.evaluate_value_posture` |
| Playbook TRADE on extension  | Price above value band  | Demote to WATCH / PILOT                  |
| Short-horizon catalyst chase | Not owner horizon       | Value tags + research authority          |
| AI hype narrative            | Story ≠ moat            | `bamang_labels` on rows                  |

### Demote (label, don't remove)

- Breakout / momentum tags without thesis_conf ≥ 0.65
- High PE growth names without owner-earnings note
- Pilot sizing without margin-of-safety flag

---

## 2. Parts 1–10 framework (operator map)

| Part | Theme                   | CC surface                        |
| ---- | ----------------------- | --------------------------------- |
| 1    | Graham — price vs value | Passive baseline, net edge        |
| 2    | Buffett — quality       | Thesis quality in score_card      |
| 3    | Munger — checklists     | Dossier why-not, guardrails       |
| 4    | Moat / franchise        | `thesis_conf`, sector leadership  |
| 5    | Capital allocation      | Sleeve / fund evidence (research) |
| 6    | Owner earnings          | Evidence quality, calibration n   |
| 7    | Psychology              | Restraint banner, WAIT copy       |
| 8    | Concentration           | Portfolio overlap governor        |
| 9    | Patience & cash         | `restraint`, NO_TRADE stance      |
| 10   | Process                 | L1–L5 hierarchy, audit trail      |

---

## 3. Architecture

```
Macro / board gate (L1)
        │
        ▼
value_investing.evaluate_value_posture(row)
        │ margin_of_safety_ok, bamang_labels
        ▼
Playbook row tags (value_tag, value_action_hint)
        │
        ▼
Dossier — research depth, never standalone TRADE
```

**Module:** `src/services/value_investing.py`

**Labels:** `BAMANG_LABELS` — moat unclear, price above value, margin of safety OK, etc.

---

## 4. UI wiring (minimal pass)

| Surface        | Change                                    |
| -------------- | ----------------------------------------- |
| Playbook cards | `value_tag`, `bamang_labels` when present |
| Dashboard      | Inherits board gate + passive baseline    |
| Guide          | Link this doc under book modes            |

**Authority:** Always `research_only` unless board TRADE + `margin_of_safety_ok`.

---

## 5. Roadmap

- [x] Parts 1–10 doc + `value_investing.py` stubs
- [x] Playbook row tags via `enrich_opportunity_row`
- [ ] Owner-earnings / DCF band from fundamentals feed
- [ ] Dossier "Value & Moat" panel
- [ ] Calibrated hit rates when n ≥ 30

---

## Cross-reference

- `docs/PLATFORM_UPGRADE_AUDIT.md` — L1–L5, passive baseline
- `docs/RANDOM_WALK_PLATFORM_PROMPT.md` — humility vocabulary
- `docs/NISON_CANDLESTICK_UPGRADE.md` — orthogonal book mode (pattern context)
