# Fund · Clarity Console — Developer / AI Coder Spec

**Target:** Upgrade from fund sleeve **summary cards** → **PM fund operating console**  
**API:** `GET /api/fund-lab/live` · `GET /api/fund-lab/console`  
**UI:** `tab==='funds'` in `src/api/templates/index.html`

---

## Problem (user review 6/10)

- Static cards: mandate + return + alpha + Sharpe + holdings only
- Alpha = return when `benchmark_return_pct` missing (fixed in `fund_lab_service.run`)
- Regime `unknown` while header shows UPTREND (fixed via `regime_display` from regime cache)
- No curve, no why paused, no execution layer, no monitor, no drilldown

---

## Must-have layers (implemented)

| Layer | Backend | UI |
|-------|---------|-----|
| Active manager state | `enrich_fund_card`: stance, mode, deployability, status_reason, controls_capital | Card header + reason box |
| Curve / DD | `equity_curve_20/60`, `max_drawdown_pct`, spark SVG | Per-card curve |
| IB / execution | `build_execution_readiness` on fund payload | Execution readiness card |
| Monitor | `build_fund_monitor_triggers` | Monitor now block |
| Why paused/reduced | `status_reason`, `regime_fit_explanation`, `next_trigger` | Amber + blue lines |
| Allocation | `build_allocation_recommendation` | Green allocation strip |
| Comparison table | `build_comparison_table` | Table row scan |
| Holdings drilldown | — | `@click openDossier(ticker)` pills |
| Evidence | `evidence_quality` per card | Footer label + trust strip |

---

## API shape (`console` object)

```json
{
  "regime": "bull_trending",
  "regime_display": "UPTREND · WAIT",
  "benchmark": "SPY",
  "benchmark_return_pct": 12.4,
  "cards": [{ "...enriched card..." }],
  "allocation": { "headline": "Tactical 60% · Balanced 40%", "weights": [], "note": "..." },
  "comparison_table": [],
  "monitor_triggers": [],
  "active_manager": { "sleeve_id", "display_name", "stance", "controls_capital" },
  "execution_readiness": { "broker_connected", "readiness_label", ... }
}
```

---

## Files

| File | Role |
|------|------|
| `src/services/fund_manager_console.py` | Operating layer builder |
| `src/services/fund_lab_service.py` | `benchmark_return_pct`, `equity_curve_60` |
| `src/services/model_funds.py` | `roi_vs_benchmark` for excess α |
| `src/api/routers/funds.py` | Embeds `console` in live payload |
| `tests/test_fund_manager_console.py` | Unit tests |

---

## P1 (not yet)

- Rolling alpha / beta / tracking error vs SPY
- Live vs training curve split
- Auto watchlist from fund adds
- Page-2 nav render issue (separate layout bug if still blank)

---

## Verify

```bash
python3 -m unittest tests.test_fund_manager_console -q
curl -s http://127.0.0.1:8000/api/fund-lab/console | jq '.allocation, .comparison_table[0], .cards[0].status_reason'
```

Restart `cc_api_dev` after deploy.
