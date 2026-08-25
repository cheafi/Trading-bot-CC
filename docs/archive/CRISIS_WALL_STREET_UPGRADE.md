# 《乱世华尔街》Crisis / Hostile Regime Upgrade

**Single-book mode:** 《乱世华尔街》only — survival, liquidity, funding, correlation, and execution plumbing. No Turtle / Nison / 巴芒 / Random Walk mixing in this pass.

---

## Deepest value of the book

《乱世华尔街》teaches that **markets have states**, not just prices: calm, fragile, liquidity stress, funding stress, cascade, rescue, and stabilization. The deepest value is **operational humility** — when the system is broken, the job is to preserve capital and optionality, not to prove a setup. Cash, de-grossing, and smaller size are active decisions; hero trades are a luxury of calm regimes.

## Biggest mistake the current system makes

CC still **ranks and surfaces TRADE-grade cards** when VIX, breadth, or macro gates say hostile — implying that isolated technical quality overrides **regime and plumbing**. A connected IBKR session is treated as deploy permission. Flow and fund backtests read as conviction. The fix: **regime and plumbing first**; cards are research unless crisis bundle clears attack posture.

---

## Part 1 — Product diagnosis

### Already aligned (keep)

| Area                       | Why it fits 乱世              |
| -------------------------- | ----------------------------- |
| `decision_hierarchy` L1    | Page gate blocks deploy       |
| NO_TRADE / WAIT copy       | Cash is valid                 |
| `restraint` governor       | Anti-overtrading in stress    |
| IBKR critical checks       | Execution blocked when unsafe |
| Portfolio heat post-breach | Risk reduction                |

### Violates or conflicts (fix)

| Area                           | Gap                | Remedy                                        |
| ------------------------------ | ------------------ | --------------------------------------------- |
| TRADE cards in VIX spike       | Ignores stress     | `deploy_blocked` + `attack_permission`        |
| Flow as trigger                | Narrative in panic | `dislocation_opportunity` + confirmation copy |
| Funds backtest as deploy proof | False confidence   | Research authority label                      |
| Connected = safe               | Ops ≠ permission   | `counterparty_trust` + L1 plumbing            |

---

## Part 2 — Product redefinition

**Clarity Console in crisis mode** is a **survival console**, not a signal board:

1. **Regime state** — calm → cascade (single headline).
2. **Liquidity / funding** — size multiplier and exit realism.
3. **Posture** — preservation vs selective attack vs balanced.
4. **Plumbing** — broker trust before handoff.
5. **Portfolio survival** — score, optionality, crowding.
6. **Name-level** — dislocation class (panic / repair / dead-cat).

Deploy surfaces honor `capital_preservation_priority` and `attack_permission` on playbook rows.

---

## Part 3 — Architecture

```
market_regime + decision_model + execution_readiness
        │
        ├─ crisis_regime.classify / evaluate
        ├─ liquidity_funding_stress
        ├─ leverage_fragility
        ├─ counterparty_trust (IBKR health)
        ├─ dislocation_opportunity
        └─ crisis_portfolio_survival
        │
        ▼
build_crisis_bundle() / crisis_strip_for_today()
        │
        ├─ /api/v7/today → crisis_regime (strip)
        ├─ decision_hierarchy L1 (regime + plumbing)
        ├─ Playbook enrich → regime_fit, attack_permission, preservation
        ├─ stock_intel → crisis_context
        └─ portfolio_decision_console → crisis_survival
```

---

## Part 4 — Page-by-page

| Page                  | Crisis behavior                                                                         |
| --------------------- | --------------------------------------------------------------------------------------- |
| **Dashboard / Today** | Strip: `regime_state`, `liquidity_state`, `preservation_vs_attack`, banner              |
| **Playbook**          | Rows: `regime_fit`, `attack_permission`, `capital_preservation_priority`, `crisis_hint` |
| **Dossier**           | Block: `crisis_context` — summary, liquidity exposure, dislocation                      |
| **Portfolio**         | Section: `crisis_survival` — score, optionality, crowding, section_copy                 |
| **Flow / Funds**      | Unchanged authority — confirmation / research only under stress                         |

---

## Part 5 — Fields & scores

| Field              | Source                                     | Meaning                    |
| ------------------ | ------------------------------------------ | -------------------------- |
| `state`            | `classify_crisis_state`                    | calm … cascade             |
| `level`            | mapped                                     | normal / elevated / crisis |
| `deploy_blocked`   | regime + hostile                           | No new hero risk           |
| `posture`          | preservation / balanced / selective_attack | Operator stance            |
| `liquidity_state`  | `liquidity_funding_stress`                 | calm … liquidity_trap      |
| `regime_fit`       | 0–100 crisis-aware                         | Playbook / bundle          |
| `survival_score`   | portfolio module                           | Book resilience            |
| `dislocation_kind` | panic / repair / dead_cat / none           | Ticker context             |

---

## Part 6 — Copy (survival-first)

| Situation    | Copy                                                        |
| ------------ | ----------------------------------------------------------- |
| Crisis strip | 乱世模式 · Capital preservation — no new hero trades        |
| L1 blocked   | Crisis regime — preservation overrides setups               |
| Plumbing     | Broker plumbing not trusted — no new risk                   |
| Portfolio    | Survival first — reduce heat and raise cash before new risk |
| Playbook     | `crisis_hint` from evaluate_crisis_regime headline          |
| Dossier      | `{ticker}: {regime headline} · {liquidity headline}`        |

---

## Part 7 — File plan

| File                                         | Role                                                  |
| -------------------------------------------- | ----------------------------------------------------- |
| `docs/CRISIS_WALL_STREET_UPGRADE.md`         | This doc                                              |
| `src/services/crisis_regime.py`              | States, bundle, strip, playbook tags, dossier context |
| `src/services/liquidity_funding_stress.py`   | Liquidity/funding outputs                             |
| `src/services/leverage_fragility.py`         | Correlation / concentration fragility                 |
| `src/services/counterparty_trust.py`         | IBKR health → trust                                   |
| `src/services/dislocation_opportunity.py`    | Panic / repair / dead-cat                             |
| `src/services/crisis_portfolio_survival.py`  | Survival score, optionality                           |
| `src/services/decision_hierarchy.py`         | L1 regime + plumbing                                  |
| `src/api/routers/decision.py`                | Today wiring                                          |
| `src/services/decision_truth_model.py`       | Playbook enrich                                       |
| `src/services/stock_intel.py`                | `crisis_context`                                      |
| `src/services/portfolio_decision_console.py` | `crisis_survival`                                     |
| `tests/test_crisis_regime.py`                | Classification tests                                  |

---

## Part 8 — ROI roadmap

| Priority | Item                                         | Status               |
| -------- | -------------------------------------------- | -------------------- |
| P0       | Doc + crisis modules + tests                 | Done (this pass)     |
| P0       | `/today` crisis strip + hierarchy L1         | Done                 |
| P1       | Playbook + dossier + portfolio fields        | Done                 |
| P2       | UI strip component (consume `crisis_regime`) | Deferred — API ready |
| P2       | Correlation matrix → `correlation_spike`     | Deferred             |
| P3       | Auto de-risk suggestions on portfolio        | Deferred             |
| P3       | Crisis-only defensive sleeve playbook        | Deferred             |

---

## Cross-reference

- `docs/PLATFORM_UPGRADE_AUDIT.md` — authority stack
- `docs/TURTLE_TRADING_UPGRADE.md` — entries blocked when `deploy_blocked`
- `docs/BAMANG_VALUE_INVESTING_UPGRADE.md` — patience overlaps preservation
