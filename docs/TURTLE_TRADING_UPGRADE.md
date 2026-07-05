# 《海龟交易法则》Turtle Trading Upgrade

**Single-book mode:** 《海龟交易法则》 — systematic trend following only.

Rules beat discretion: breakouts, ATR-based risk, unit sizing, pyramiding limits, and honor exits.

---

## 1. Product diagnosis

### Already aligned (keep)

| Area                              | Why it fits Turtle           |
| --------------------------------- | ---------------------------- |
| `trade_plan` stop / R:R           | Risk unit geometry           |
| `execution_readiness`             | Broker + bracket before size |
| Portfolio heat                    | Caps total risk              |
| `decision_hierarchy` L4 execution | No stop = no trade at L4     |

### Violates or conflicts (fix)

| Area                                 | Gap               | Remedy                                |
| ------------------------------------ | ----------------- | ------------------------------------- |
| Discretionary TRADE without breakout | No Donchian proxy | `turtle_system.evaluate_turtle_setup` |
| Full size without ATR stop           | Unit math missing | `atr_stop_required` label             |
| Mean-reversion scanner wins          | Anti-turtle       | Demote on playbook                    |
| Pyramiding without heat check        | One bet           | `unit_size_capped`                    |

---

## 2. Turtle system rules (operator)

| Rule                   | Implementation stub                                  |
| ---------------------- | ---------------------------------------------------- |
| Entry                  | 20/55-day breakout proxy: above SMA20+50, vol ≥ 1.1× |
| Stop                   | ATR / structure stop required                        |
| N sizing               | `system_n=20`, `atr_pct_proxy` from structure        |
| Units                  | Max 4 units; `units_allowed` heuristic               |
| Exit                   | Channel / trailing — `exit_trailing` label           |
| Flat in hostile regime | Crisis strip blocks new risk                         |

**Module:** `src/services/turtle_system.py`

---

## 3. Architecture

```
Regime gate (not hostile)
        │
        ▼
turtle_system.evaluate_turtle_setup(row)
        │ entry_ok, turtle_labels
        ▼
Playbook: turtle_tag, turtle_entry_ok, turtle_units_allowed
        │
        ▼
IBKR bracket + pilot size only when entry_ok
```

---

## 4. UI wiring (minimal pass)

| Surface   | Change                                        |
| --------- | --------------------------------------------- |
| Playbook  | Show `turtle_tag` pill; entry_ok → pilot hint |
| Dossier   | Future: ATR stop calculator                   |
| Portfolio | Heat must respect max units                   |

**Authority:** `pilot_only` when `entry_ok`; else `research_only`.

---

## 5. Roadmap

- [x] Doc + `turtle_system.py` stubs
- [x] Playbook tags in `enrich_opportunity_row`
- [ ] Full Donchian channel from OHLC store
- [ ] Live ATR(N) and unit calculator in dossier
- [ ] Trade memory for pyramid count per symbol

---

## Cross-reference

- `docs/CRISIS_WALLSTREET_UPGRADE.md` — blocks new turtle entries in crisis
- `docs/NISON_CANDLESTICK_UPGRADE.md` — pattern context vs breakout system
