# 《乱世华尔街》Crisis / Hostile Regime Upgrade

**Single-book mode:** 《乱世华尔街》 — survival, liquidity, and correlation stress only.

When markets turn hostile, **capital preservation** overrides isolated setups. Hero trades are demoted; cash and de-risking are active decisions.

---

## 1. Product diagnosis

### Already aligned (keep)

| Area                            | Why it fits 乱世              |
| ------------------------------- | ----------------------------- |
| `decision_hierarchy` L1 hostile | Macro hostile blocks deploy   |
| NO_TRADE / WAIT copy            | Cash is valid                 |
| `restraint` governor            | Anti-overtrading in stress    |
| IBKR critical checks            | Execution blocked when unsafe |
| Portfolio heat post-breach      | Risk reduction                |

### Violates or conflicts (fix)

| Area                           | Gap                | Remedy                           |
| ------------------------------ | ------------------ | -------------------------------- |
| TRADE cards in VIX spike       | Ignores stress     | `crisis_regime.deploy_blocked`   |
| Flow as trigger                | Narrative in panic | Confirmation only + crisis strip |
| Funds backtest as deploy proof | False confidence   | Research authority label         |
| "Connected" = safe to trade    | Ops ≠ permission   | Surface authority BLOCKED        |

---

## 2. Crisis levels

| Level      | Triggers (heuristic)                 | Operator stance      |
| ---------- | ------------------------------------ | -------------------- |
| `normal`   | VIX < 22, board not hostile          | Monitor only         |
| `elevated` | VIX ≥ 22 or breadth < 35%            | Size down, no heroes |
| `crisis`   | VIX ≥ 28, NO_TRADE, or hostile macro | Preservation mode    |

**Module:** `src/services/crisis_regime.py`

**Labels:** `CRISIS_LABELS` — hostile regime, liquidity stress, vol crisis, cash is the position.

---

## 3. Architecture

```
market_regime + decision_model
        │
        ▼
crisis_regime.crisis_strip_for_today()
        │ level, deploy_blocked, banner
        ▼
Dashboard crisis strip (all tabs via /today cache)
        │
        ▼
Playbook / portfolio — respect deploy_blocked
```

---

## 4. UI wiring (minimal pass)

| Surface      | Change                                             |
| ------------ | -------------------------------------------------- |
| Dashboard    | Amber/red crisis strip when `today7.crisis_regime` |
| PM strip     | Crisis banner when `deploy_blocked`                |
| Flow / Funds | Existing "confirmation / research only" copy       |

---

## 5. Roadmap

- [x] Doc + `crisis_regime.py` stubs
- [x] `/api/v7/today` → `crisis_regime` payload
- [x] Dashboard strip
- [ ] Correlation matrix feed into `correlation_spike`
- [ ] Auto de-risk suggestions on portfolio tab
- [ ] Crisis playbook (defensive sleeve only)

---

## Cross-reference

- `docs/PLATFORM_UPGRADE_AUDIT.md` — authority stack
- `docs/TURTLE_TRADING_UPGRADE.md` — entries blocked in crisis
- `docs/BAMANG_VALUE_INVESTING_UPGRADE.md` — patience overlaps preservation
