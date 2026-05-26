bilbi# CC VNext Sprint Plan (Truthful Surfaces + Product Compression)

Date: 2026-04-02 | Updated: 2026-04-04
Owner: TradingAI_Bot CC Core
Scope: Convert strong backend depth into auditable, single-purpose surfaces with one truth layer.

### Progress Tracker

| Commit | Title                                | Status  |
| ------ | ------------------------------------ | ------- |
| A      | Wire recommendations to engine cache | ✅ Done |
| B      | Signal lifecycle truth fields        | ✅ Done |
| C      | Remove random from perf-lab          | ✅ Done |
| D      | Immutable performance artifacts      | ✅ Done |
| E      | Engine async context path            | ✅ Done |
| F      | Engine yfinance → MarketDataService  | ✅ Done |
| G      | API + Discord data consolidation     | ✅ Done |
| H      | Portfolio brief catalysts + holdings | ✅ Done |
| I      | Real options chain provider          | ✅ Done |
| J      | Expression-aware options explanation | ✅ Done |
| K      | Compare overlay alignment modes      | ✅ Done |
| L      | Strategy portfolio lab MVP           | ✅ Done |
| M      | Unified artifact writer for research | ✅ Done |
| N      | External market-intel contract       | ✅ Done |
| O      | Research lab modularity refactor     | ✅ Done |
| P      | Codebase hygiene + duplicates        | ✅ Done |

---

## 0) Principles (hard rules)

1. **One source of truth**
   - `AutoTradingEngine` singleton state is authoritative for recommendations and live lifecycle.
2. **Truth badges everywhere**
   - Every API/page returns `mode` in `{LIVE, PAPER, BACKTEST, SYNTHETIC}` + `as_of` + `source` + `sample_size`.
3. **Artifact-first**
   - Every daily/surface analysis writes `json/csv/png/md` artifact before UI rendering.
4. **Single-purpose page contract**
   - Each page answers one question only.

---

## 1) Target surfaces (v7)

- `/api/v7/regime-screener` → “What market regime now, and what engine is active?”
- `/api/v7/signals` (or existing recommendations surface) → “What to watch/trade now, and why?”
- `/api/v7/portfolio-brief` → “What happened in my portfolio today?”
- `/api/v7/performance-lab` → “What is audited performance history?”
- `/api/v7/research/compare-overlay` → “How do instruments compare under aligned dates?”
- `/api/v7/options-screen` → “Which options expressions are highest quality now?”
- `/api/v7/strategy-portfolio-lab` (new) → “How to mix strategy sleeves optimally?”

---

## 2) P0 (must ship first)

## P0.1 Truthful recommendations surface

### Commit A — Wire recommendations to singleton engine cache

**Files**

- `src/api/main.py`
- `src/engines/auto_trading_engine.py`
- `src/core/models.py` (only if response schema extension needed)

**Endpoint/page**

- Existing `/api/recommendations` (or promote alias `/api/v7/signals`)

**Changes**

- Replace local `ContextAssembler()` + local `RegimeRouter()` fallback path with `_get_engine()` state reads.
- Response uses engine-side cached recommendation list (`_cached_recommendations` or public getter).
- Include metadata block:
  - `mode`, `as_of`, `source="engine_cache"`, `regime`, `no_trade_reason`, `sample_size`.

**Acceptance**

- No empty placeholder list when engine cache exists.
- `TradeRecommendation` fields (`why_now`, `approval_flags`, `scenario_plan`, `evidence`, `why_not_trade`, `better_alternative`, `expression`) are preserved end-to-end.

**Tests**

- `tests/api/test_recommendations_truthful.py`
- `tests/engines/test_engine_cache_recommendations.py`

---

### Commit B — Add lifecycle truth fields to signal payload

**Files**

- `src/core/models.py`
- `src/engines/auto_trading_engine.py`
- `src/api/main.py`

**Endpoint/page**

- `/api/recommendations` and signals UI card/table

**Changes**

- Add/ensure lifecycle fields: `status`, `triggered_at`, `exited_at`, `exit_reason`, `expected_r`, `realized_r`.
- Standardize statuses: `TRIGGERED`, `ACTIVE`, `TP`, `SL`, `EXPIRED`, `CANCELLED`.

**Acceptance**

- Every recommendation with terminal status includes `exit_reason` and realized metrics.

**Tests**

- `tests/engines/test_signal_lifecycle_status.py`

---

## P0.2 Performance Lab must be auditable

### Commit C — Remove random fallback from performance metrics path

**Files**

- `src/api/main.py`
- `src/services/performance_tracker.py` (if exists)
- `src/repositories/trade_outcome_repository.py` (if exists)

**Endpoint/page**

- `/api/v7/performance-lab`

**Changes**

- Remove `np.random.normal(...)` metrics construction from non-demo path.
- Source order:
  1. persistent `TradeOutcomeRepository` (closed trades)
  2. engine cached KPI snapshot
  3. explicit synthetic demo mode only (`mode=SYNTHETIC` hard label)
- Return assumptions block: fees/slippage basis and whether gross/net.

**Acceptance**

- Live/paper paths never fabricate random KPI.
- Synthetic path is explicit and impossible to confuse with live record.

**Tests**

- `tests/api/test_performance_lab_truth_labels.py`
- `tests/api/test_performance_lab_no_random_in_live.py`

---

### Commit D — Immutable performance artifacts

**Files**

- `src/services/artifacts/performance_artifact_writer.py` (new)
- `src/api/main.py`
- `data/` (runtime output path only)

**Endpoint/page**

- `/api/v7/performance-lab`
- Performance UI

**Changes**

- On generation, write:
  - `json`: full metrics + provenance
  - `csv`: trade ledger / monthly returns
  - `png`: equity + drawdown chart
  - `md`: executive summary
- Add `artifact_id`, `artifact_paths`, `generated_at` in response.

**Acceptance**

- Every response references immutable artifact set.

**Tests**

- `tests/services/test_performance_artifact_writer.py`

---

## P0.3 One market data layer

### Commit E — Replace engine sync context path

**Files**

- `src/engines/auto_trading_engine.py`
- `src/services/context_assembler.py`

**Endpoint/page**

- Engine internals (affects all surfaces)

**Changes**

- Replace `assemble_sync()` hot path with awaited async `assemble(...)` in loop.
- Remove mixed sync/async branching where avoidable.

**Acceptance**

- Engine loop has no blocking context assembly in normal run path.

**Tests**

- `tests/engines/test_engine_async_context.py`

---

### Commit F — Remove direct `yfinance` calls in engine signal generation

**Files**

- `src/engines/auto_trading_engine.py`
- `src/services/market_data.py`

**Endpoint/page**

- Engine signal generation

**Changes**

- Replace direct `yf.download(...)` with `MarketDataService` batch OHLCV fetch.
- Add provider tags to payload (`provider`, `latency_ms`, `staleness_sec`).

**Acceptance**

- No direct `yfinance` import/use in `auto_trading_engine.py`.

**Tests**

- `tests/engines/test_engine_market_data_service_only.py`

---

### Commit G — API and Discord market data consolidation

**Files**

- `src/api/main.py`
- `src/notifications/discord_bot.py`
- `src/discord_bot.py` (if active)

**Endpoint/page**

- all quote/history reads

**Changes**

- Replace direct `yfinance` accesses with `MarketDataService` adapters.
- Add cache/rate-limit wrappers where absent.
- Mark deprecated bot file(s) and define single active bot entrypoint.

**Acceptance**

- No direct `yfinance` calls in API + active Discord bot paths.

**Tests**

- `tests/notifications/test_discord_marketdata_provider.py`
- `tests/api/test_marketdata_provider_unified.py`

---

## P0.4 Portfolio Brief: from heuristic to contextual

### Commit H — Portfolio input + catalysts integration

**Files**

- `src/api/main.py`
- `src/services/market_data.py`
- `src/services/catalyst_summarizer.py` (new)

**Endpoint/page**

- `/api/v7/portfolio-brief`

**Changes**

- Replace static watchlist with:
  1. real holdings input (if available)
  2. fallback user watchlist
- Integrate news/catalyst feed and sector cluster summaries.
- Output `follow_up_questions` list for conversational drill-down.

**Acceptance**

- Brief includes market context + catalyst narrative, not only indicator deltas.

**Tests**

- `tests/api/test_portfolio_brief_holdings_and_catalysts.py`

---

## 3) P1 (high-value expansion)

## P1.1 Real Options Lab

### Commit I — Connect real options chain provider

**Files**

- `src/api/main.py`
- `src/ingestors/options_data.py`
- `src/services/options/options_mapper.py` (new)

**Endpoint/page**

- `/api/v7/options-screen`

**Changes**

- Switch from synthetic contract generation to provider chain fetch.
- Map real fields: strike, expiry, DTE, delta, IV, OI, spread, liquidity score.
- Add warnings: earnings proximity, ex-div, IV crush risk.

**Acceptance**

- Contract table is provider-backed in non-synthetic mode.

**Tests**

- `tests/api/test_options_screen_provider_backed.py`

---

### Commit J — Expression-aware options explanation

**Files**

- `src/core/expression_engine.py` (or equivalent)
- `src/api/main.py`

**Endpoint/page**

- `/api/v7/options-screen`

**Changes**

- Reuse expression engine for explanation path:
  - stock vs long_call vs long_put vs debit_spread rationale.
- Add `expression_rationale` and `rejection_reasons` fields.

**Acceptance**

- Options page explanation is tied to execution expression logic.

---

## P1.2 Compare Overlay Pro

### Commit K — Date-aligned comparison modes

**Files**

- `src/api/main.py`
- `src/services/compare_overlay_service.py` (new)

**Endpoint/page**

- `/api/v7/research/compare-overlay`

**Changes**

- Implement aligned join strategies:
  - strict mode: inner join
  - smooth mode: outer join + forward fill
- Add modes:
  1. normalized return
  2. relative strength ratio
  3. rolling correlation/beta

**Acceptance**

- Mixed calendars (US/HK/vol indexes/ETFs) do not silently misalign.

**Tests**

- `tests/api/test_compare_overlay_alignment_modes.py`

---

## P1.3 Strategy Portfolio Lab (new)

### Commit L — Multi-strategy sleeve optimizer MVP

**Files**

- `src/api/main.py`
- `src/services/strategy_portfolio_lab.py` (new)
- `src/research_lab/portfolio/optimizer.py` (new)

**Endpoint/page**

- `/api/v7/strategy-portfolio-lab`

**Changes**

- Input: strategy sleeve return streams.
- Output:
  - max Sharpe / min drawdown / risk parity weights
  - correlation matrix
  - attribution and equity curve
- Include regime-conditioned weight profile.

**Acceptance**

- User gets “best mix” not only “best strategy”.

**Tests**

- `tests/api/test_strategy_portfolio_lab.py`

---

## P1.4 Artifact-first for research surfaces

### Commit M — Unified artifact writer for v7 research pages

**Files**

- `src/services/artifacts/research_artifact_writer.py` (new)
- `src/api/main.py`

**Endpoint/page**

- compare/options/strategy lab

**Changes**

- Standard output bundle per run: `json/csv/png/md`.
- Add replay endpoint design scaffold:
  - `/api/v7/research/artifacts/{artifact_id}`

**Acceptance**

- Research results are replayable/shareable across API, bot, dashboard.

---

## 4) P2 (platformization + hygiene)

### Commit N — External read-only market-intel contract

**Files**

- `src/api/main.py`
- `docs/SKILL.md` (new)
- `docs/API_MARKET_INTEL.md` (new)

**Endpoint/page**

- `/api/market-intel/*`

**Changes**

- Stable read-only endpoints for assistants/bots.
- Add provenance, rate-limit, and response contracts.

---

### Commit O — Research lab modularity refactor

**Files**

- `src/research_lab/factors/` (new)
- `src/research_lab/patterns/` (new)
- `src/research_lab/slippage/` (new)
- `src/research_lab/metrics/` (new)
- `src/research_lab/portfolio/` (new)
- `src/research_lab/options/` (new)

**Changes**

- Move exploratory logic out of monolithic engine/page handlers.
- Keep live scanner lean (selected factors only).

---

### Commit P — Codebase hygiene and duplicate surface cleanup

**Files**

- duplicate bot files + stale `.bak/.v2bak` paths
- `tests/` additions for v7 endpoints

**Changes**

- Define one active bot module and deprecate duplicates.
- Remove or archive dead backup files from runtime path.
- Add CI target for v7 API contract tests.

---

## 5) Delivery cadence (2-week sprints)

- **Sprint 1 (P0-A to P0-D)**: truthful recommendations + auditable performance
- **Sprint 2 (P0-E to P0-H)**: one data layer + contextual portfolio brief
- **Sprint 3 (P1-I to P1-K)**: real options + compare overlay pro
- **Sprint 4 (P1-L to P1-M)**: strategy portfolio lab + full artifact-first research
- **Sprint 5 (P2-N to P2-P)**: external market-intel + modularity + hygiene

---

## 6) Definition of Done (global)

1. Every v7 response includes trust metadata:
   - `mode`, `as_of`, `source`, `sample_size`, `assumptions`.
2. No silent synthetic fallback in LIVE/PAPER/BACKTEST mode.
3. All major pages are single-question surfaces.
4. All research-capable pages output immutable artifacts (`json/csv/png/md`).
5. API, bot, dashboard consume same artifact/truth source.

---

## 7) Immediate next commit (start now)

**`feat(v7): make recommendations endpoint read singleton engine cache with trust metadata`**

Implementation slice:

- Update recommendations handler in `src/api/main.py` to use `_get_engine()`.
- Add trust metadata fields and `no_trade_reason`.
- Add one API test asserting non-empty cache passthrough and `mode/source` presence.

This commit unlocks the truth-layer baseline for all downstream surfaces.
