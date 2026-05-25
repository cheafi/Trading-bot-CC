# PM Product Roadmap — Decision-Grade Trading Platform

## Product Verdict

The platform should move from many partially reconciled surfaces to five decision-grade workflows with one shared truth state. The priority is trust: every page must agree on regime, scanner status, confidence source, timestamp, and live/training/degraded state.

## Sprint 1 — Trust State And No Fake Precision

Goal: stop visible contradictions and remove fake confidence.

### Sprint 1 Scope

- Add one shared trust vocabulary: `live`, `snapshot`, `stale`, `training`, `degraded`.
- Show a trust badge beside opportunity, scanner, fund, and review data.
- Never render missing confidence as `0%`; show `—` or a clearly labeled fallback.
- Mark scanner-derived fallback candidates as `fallback` or `stale-fallback`.
- Collapse empty/broken panels by default: empty Avoid Now, empty closed trades, training-only fund outputs.

### Sprint 1 Acceptance Criteria

- No action card shows `Conf 0%` unless a real calibrated score of exactly zero is explicitly provided.
- If scanner times out, Command and Opportunities both show the same degraded/snapshot state.
- Training-only and fallback AI text cannot visually outrank live deployable data.
- Health smoke checks stay green: `/healthz`, `/readyz`, `/api/live/market`, `/api/ibkr/status`, `/api/v1/pm-arena/overview?fast=true`.

## Sprint 2 — Merge Opportunities Pipeline

Goal: replace OPPTY + Scanner Detail + Avoid Now with one reconciled pipeline.

Inspired by TradingAgents and ai-hedge-fund, the product should display the workflow as a compact decision chain rather than many peer pages: analysts produce evidence, bull/bear or style agents challenge it, risk constrains it, and the PM layer emits the final action.

### Sprint 2 Screen

- Top 3 deployable ideas only above the fold.
- Pilot and Watch lists collapsed below.
- Filter funnel in the same page: universe → filters → finalists.
- Rejected ideas and reasons integrated under the funnel.
- One click from every symbol to Dossier.
- Every candidate shows: action tier, regime fit, R:R, confidence source, why now, why not stronger, invalidation.

### Sprint 2 Acceptance Criteria

- Scanner detail cannot show a different regime than Command without an explanation.
- If no rejected names exist, Avoid section is collapsed and labeled `no rejection run` or `scanner degraded`.
- Long weak-candidate lists are hidden behind `Show more`.

## Sprint 3 — PM Arena V2

Goal: turn Funds from a training dashboard into a PM operating surface.

Borrow the useful pattern, not the code: compress each analyst/PM voice into structured fields (`signal`, `confidence`, `reason`, `risk veto`, `allowed action`) and keep deterministic constraints ahead of any LLM-generated memo.

### Sprint 3 Screen

- Live sleeves first; training sleeves collapsed below.
- For each fund show: status `BUY / ADD / HOLD / TRIM / EXIT / WATCH`, top holdings, entry basis, current P&L, alpha since entry, regime fit, concentration, invalidation.
- Keep deterministic engine as final decision layer.
- AI roles remain bounded: Gemma memo, Qwen challenge, MiniLM memory.
- Fallback AI text must be labeled `fallback memo` and visually de-emphasized.

### Sprint 3 Acceptance Criteria

- Training funds do not compete with live deployable funds at top prominence.
- Concentration risk above policy threshold is visible as a CRO warning.
- Every fund has an action ladder and invalidation condition.

## Sprint 4 — Review And Calibration

Goal: make performance evidence decision-useful.

### Sprint 4 Screen

- Merge Track Record, Trade Journal, and Review.
- Live closed trades first.
- Backtest lab collapsed below and labeled research-grade if gross/no-commission assumptions apply.
- Add confidence calibration by bucket, strategy, and regime.
- Add repeated-mistake tags and recent failure themes.

### Sprint 4 Acceptance Criteria

- No `undefined%` metrics render in user-facing UI.
- Empty live trade history is collapsed with a clear `research only` label.
- Confidence buckets show hit rate, average return, alpha vs benchmark, and sample size.

## Navigation Target

Primary tabs:

1. Command
2. Opportunities
3. Funds
4. Review
5. Research / Ops

Secondary tools under Research / Ops:

- Research Card / Dossier
- Portfolio / Broker
- Research Scanners
- IBKR Live
- Methodology

Archived or deep-link only surfaces: Legacy Overview, Scanner Detail, Avoid Now, Brief, Strategy Factory, Options, Time Travel, Guide, RS, Flow, Catalog. These can still exist behind contextual buttons, but they should not compete as top-level tabs.

## Agentic Research Lessons

- TradingAgents pattern: use a staged chain — Analyst Team → Bull/Bear Research → Trader → Risk Debate → Portfolio Manager — and show each stage as evidence feeding one PM decision.
- ai-hedge-fund pattern: keep many specialist lenses internally, but expose only compact `{signal, confidence, reasoning}` summaries plus deterministic allowed actions.
- PM-grade adaptation: every live action card must show conviction tier, R:R, regime gate, confidence source, and risk veto status before any AI memo.
- CRO guardrail: LLM outputs can explain or challenge; they cannot override position limits, correlation caps, VIX gates, or live broker safety.

## North Star

Fewer pages, one shared truth state, and PM-grade actionability. The Dossier page is the canonical quality bar for all future opportunity and fund cards.
