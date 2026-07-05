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

- Score min: `CC_COUNCIL_DEPLOY_SCORE_MIN` (default **7.5**)
- Confidence min: `CC_COUNCIL_DEPLOY_CONF_MIN` (default **0.60**)
- R:R min: `CC_COUNCIL_DEPLOY_RR_MIN` (default **2.0**)
- Requires entry/stop/target levels

Lowering defaults without env flags would fake deploy authority — do not.

## Universe expansion

`CC_SCAN_UNIVERSE_MODE=expanded` widens discovery caps to **50 / 20 / 8** only when ranked board is **fresh**.

## Research vs deploy

`opportunity_status` on `/api/v7/today` surfaces watch names, options liquidity, sector rotation, and upgrade triggers **without** changing capital authority.
