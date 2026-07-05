# Deploy authority diagnosis

Why Dashboard often shows **monitor only** (`deploy_authority: false`).

## Resolution chain (`system_truth.resolve_system_truth`)

Deploy authority requires **all** of:

1. `decision_authority.authority_level == "deploy"` and `allows_trade_labels` and not `gates_active`
2. `board_gate == "open"` (or WAIT + execution_ready + broker ready — rare path)
3. `brief_freshness` not `expired` or `fallback`
4. `broker_freshness` not `offline` or `blocked`
5. `ranked_board_freshness` not `stale`, `fallback`, or `unavailable`
6. `deploy_qualified >= 1` **or** `execution_ready_count >= 1`

## Common blocker categories

| Category | Codes | User action |
|----------|-------|-------------|
| **Infra** | `BROKER_OFFLINE`, `BRIEF_EXPIRED`, `FALLBACK_BRIEF`, `BOARD_STALE`, `DATA_STALE`, `ENGINE_OFF` | IBKR session, regenerate brief, live scanner |
| **Regime / board** | `BOARD_WAIT`, `BOARD_CLOSED`, `REGIME_NO_TRADE` | Wait for tradeability upgrade or selective + execution-ready |
| **Council threshold** | `NO_DEPLOY_QUALIFIED` | Names fail score ≥7.5, conf ≥0.60, R:R ≥2.0, levels — tune via `CC_COUNCIL_DEPLOY_SCORE_MIN` (default unchanged) |

## Council thresholds (`decision_truth_model.is_execution_ready`)

- Score min: `CC_COUNCIL_DEPLOY_SCORE_MIN` (daily default **7.0**, strict **7.5**)
- Confidence min: `CC_COUNCIL_DEPLOY_CONF_MIN` (daily default **0.55**, strict **0.60**)
- R:R min: `CC_COUNCIL_DEPLOY_RR_MIN` (daily default **1.8**, strict **2.0**)
- Requires entry/stop/target levels

## Daily trading mode (`CC_DAILY_TRADING_MODE=1`, default ON in dev)

When board is fresh (not fallback/expired):

| Tier | When | Operator copy |
|------|------|---------------|
| `allowed` | execution-qualified ≥1 + broker ready | Deploy available · 可部署 |
| `paper_only` | trade-qualified ≥1 + broker offline | Paper deploy · 紙上可試 |
| `pilot_only` | B+ pilot-eligible, broker may be offline | Pilot probe · half size when broker ready |
| `blocked` | stale board, NO_TRADE, or no qualified names | 僅監察 |

`deploy_authority` boolean remains **live-only** — paper path never enables IBKR handoff.

## Universe expansion

`CC_SCAN_UNIVERSE_MODE=expanded` widens discovery caps to **50 / 20 / 8** only when ranked board is **fresh**.

## Research vs deploy

`opportunity_status` on `/api/v7/today` surfaces watch names, options liquidity, sector rotation, and upgrade triggers **without** changing capital authority.
