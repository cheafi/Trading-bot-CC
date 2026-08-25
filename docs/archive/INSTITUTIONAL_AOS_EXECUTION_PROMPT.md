# Institutional AOS — Agent Execution Prompt (Claude Code / Copilot / Cursor)

**Use with:** [`INSTITUTIONAL_AOS_IMPLEMENTATION_PROMPT.md`](./INSTITUTIONAL_AOS_IMPLEMENTATION_PROMPT.md) (master rules + deliverables)  
**Chinese sprint map:** [`ALPHA_OPERATING_SYSTEM_DEVELOPER_PROMPT_ZH.md`](./ALPHA_OPERATING_SYSTEM_DEVELOPER_PROMPT_ZH.md)

**Repo root:** `TradingAI_Bot-main`  
**Primary UI:** `src/api/templates/index.html` (Alpine `cc()`)  
**Primary API:** `src/api/main.py` + `src/api/routers/*`

---

## COPY — START HERE (paste to agent)

```text
You are implementing upgrades to Clarity Console (TradingAI_Bot) per docs/INSTITUTIONAL_AOS_IMPLEMENTATION_PROMPT.md.

WORK DISCIPLINE (mandatory):
1. Diagnose → 2. Verify in repo → 3. Minimal patch → 4. Verify after (file, function, curl, unittest).
Never claim "done" without diff + verification. Label: Observed | Inferred | Not verifiable.

REPO ANCHORS:
- UI: src/api/templates/index.html (x-data="cc()", switchTab at ~L4681)
- Today: GET /api/v7/today → src/services/today_insights.py
- Decision hub: GET /api/v7/decision-hub → src/services/decision_hub.py
- Stock 360: GET /api/v7/stock-intel/{t} → src/services/stock_intel.py
- Portfolio PM: GET /api/v7/portfolio-decision → portfolio_decision_console.py
- Risk: GET /api/v7/portfolio-risk-cockpit → portfolio_risk_cockpit.py
- Funds: fund_manager_console.py + /api/fund-lab/cards
- Extras: platform_extras.py (catalyst, pm-memo, stock-universe)
- Universe: src/core/stock_universe.py

BASELINE SHIPPED (do not regress):
decision-hub, today best_action/avoid_now/near_miss, stock-intel pm_answer,
portfolio-decision, portfolio-risk-cockpit, catalyst-calendar, pm-memo,
fund_manager_console, execution_readiness, stock_universe.

ROLLOUT ORDER (highest ROI first):
Sprint 1: Unified Decision Summary Bar on today|portfolio|funds|dossier|signals
Sprint 1: avoid_now panel UI, target vs current weight, IB state on portfolio
Sprint 2: stock-intel decision_bar + confluence + portfolio_fit + thesis depth
Sprint 3: attribution, correlation heatmap, rebalance-sim
Sprint 4: thesis_drift, pm_memory, leaders_tracker, compare engine

VERIFY EACH PR:
bash scripts/verify_10_10.sh
bash scripts/test_api_endpoints.sh
python3 -m unittest tests.test_decision_hub tests.test_stock_intel tests.test_portfolio_decision_console -q

ANTI-FAKE: No influencer=buy. Label live|paper|backtest on every performance number.
```

---

## 1. Pre-flight (run before any code change)

```bash
cd /path/to/TradingAI_Bot-main
export BASE_URL=http://127.0.0.1:8000
export API_KEY=dev-secret-local

# Backend up?
curl -sf "$BASE_URL/api/health" | head -c 400

# Full gate (may take 2–5 min)
bash scripts/verify_10_10.sh

# API sweep
bash scripts/test_api_endpoints.sh
```

**Docker dev:** `docker restart cc_api_dev` after router / `_cc_instant.py` / template changes.

---

## 2. Tab inventory (Alpine `index.html`)

| Tab ID      | Rendered (`x-show`) | `switchTab` fetch                          | Primary APIs                                       |
| ----------- | ------------------- | ------------------------------------------ | -------------------------------------------------- |
| `today`     | ✅ L915             | `fetchToday7`                              | `/api/v7/today`, `/api/v7/decision-hub`            |
| `signals`   | ✅ L1617            | `fetchSignals`, `fetchRanked`              | `/api/v7/playbook/ranked`                          |
| `scanners`  | ✅ L2709            | `fetchScanners`                            | scanner hub                                        |
| `portfolio` | ✅ L2821            | `fetchPortfolio`, `fetchPortfolioDecision` | `/api/portfolio/*`, `/api/v7/portfolio-decision`   |
| `dossier`   | ✅ L1964            | `fetchDossier`                             | `/api/v7/stock-intel/{t}`, `/api/live/dossier/{t}` |
| `command`   | ✅ L555             | `fetchCommandBoard`                        | `/api/watchlist`                                   |
| `funds`     | ✅ L3197            | `fetchFunds`                               | `/api/fund-lab/cards`, fund console                |
| `flow`      | ✅ L3427            | `fetchFlow`                                | `/api/v7/playbook/flow`                            |
| `rs`        | ✅ L3461            | `fetchRs`                                  | `/api/v7/playbook/rs-ranking`                      |
| `notrade`   | ✅ L3505            | `fetchRejections`                          | `/api/v7/playbook/no-trade`                        |
| `ibkr`      | ✅ L3546            | `ibkrFetchStatus`                          | IBKR router                                        |
| `ops`       | ✅ L3854            | `fetchCcStatus`                            | `/api/ops/cc-header`                               |
| `guide`     | ✅ L2295            | (modal also)                               | static                                             |

**Bottom nav:** command, today, signals, scanners, portfolio, ibkr, dossier, ops.

**Known dead / orphan state (L4392–4396 comment):** `factory`, `benchBT`, `fundMonitor`, `pmStrip`, `tradeIntel`, `tt`, `bt` — methods may exist without tab render. **Do not wire new features to these without restoring UI or deleting methods.**

**Trust audit command:**

```bash
# Tabs declared vs rendered
rg "x-show=\"tab==='" src/api/templates/index.html
rg "tabs:\[|moreTabs:" -A20 src/api/templates/index.html

# switchTab targets
rg "switchTab\('" src/api/templates/index.html

# DEAD-CODE marker
rg "DEAD-CODE" src/api/templates/index.html
```

---

## 3. v7 API checklist (curl)

```bash
KEY="${API_KEY:-dev-secret-local}"
H="X-API-Key: $KEY"
B="${BASE_URL:-http://127.0.0.1:8000}"

curl -s -H "$H" "$B/api/v7/decision-hub" | jq '.decision_strip|keys,.monitoring|keys'
curl -s -H "$H" "$B/api/v7/today" | jq '.best_action.capital_stance,.avoid_now|length,.evidence_badges'
curl -s -H "$H" "$B/api/v7/stock-intel/AAPL" | jq '.pm_answer,.smart_money,.layers|keys'
curl -s -H "$H" "$B/api/v7/portfolio-decision" | jq '.allocator_summary,.action_needed'
curl -s -H "$H" "$B/api/v7/portfolio-risk-cockpit" | jq '.concentration,.correlation'
curl -s -H "$H" "$B/api/v7/catalyst-calendar" | jq '.events|length'
curl -s -H "$H" "$B/api/v7/pm-memo?scope=today" | jq '.memo|length'
curl -s "$B/api/v7/stock-universe" | jq '.core_watchlist_count,.rs_universe_count'
```

**Add after implementing new endpoints:**

```bash
curl -s "$B/api/v7/stock-intel/AAPL" | jq '.decision_bar'   # Sprint 2
# curl -s -X POST "$B/api/v7/rebalance-sim" ...            # Sprint 3
```

---

## 4. Frontend state audit

```bash
# Alpine state keys in cc()
rg "^\s+[a-zA-Z_][a-zA-Z0-9_]*:" src/api/templates/index.html | head -80

# Common undefined-risk: DOM uses field not in init object
# Manually grep: x-text="decisionHub. x-show="pfDecision. x-show="dos.intel.
rg "decisionHub\.|pfDecision\.|dos\.intel\.|platformExtras\." src/api/templates/index.html | head -40

# ccFetch / retry
rg "ccFetch|fetchDecisionHub|fetchPortfolioDecision" src/api/templates/index.html
```

**Init path:** `init()` L4448 — staggered fetch to avoid 503 burst. New tab-level fetch should use `setTimeout` or `$watch('tab')` like portfolio L2821.

**Decision strip today:** `#pm-strip`, `decisionHub`, `fetchDecisionHub()`, `buildDecisionHubFromToday()` fallback.

---

## 5. Backend file map (where to implement)

| Capability               | Primary files                                                                                             |
| ------------------------ | --------------------------------------------------------------------------------------------------------- |
| Decision bar schema      | **new** `src/schemas/decision_bar.py` → wire `decision_hub`, `today`, `stock_intel`, `portfolio_decision` |
| Avoid Now UI             | `today_insights.py` (engine exists) → `index.html` Today                                                  |
| Fund / sleeve            | `fund_manager_console.py`, `funds.py`, Funds tab L3197                                                    |
| Curve diagnostics        | `model_funds.py`, fund cards UI                                                                           |
| IB execution             | `ibkr` router, `execution_readiness.py`, IBKR tab L3546                                                   |
| Monitors CRUD            | **new** `src/api/routers/monitors.py`, `data/monitors.json` (static path only — no user input in paths)   |
| Options depth            | `stock_intel.py`, dossier options, `options_radar`                                                        |
| Smart money tiers        | **new** `src/services/smart_money_tracker.py`                                                             |
| Portfolio fit            | **new** `src/services/portfolio_fit.py`                                                                   |
| Thesis drift / PM memory | **new** `src/services/thesis_drift.py`, `pm_memory.py`                                                    |
| Compare engine           | **new** `GET /api/v7/compare`                                                                             |

---

## 6. Unit tests (no pytest required)

```bash
python3 -m unittest tests.test_decision_hub tests.test_stock_intel \
  tests.test_portfolio_decision_console tests.test_avoid_now_engine \
  tests.test_fund_manager_console tests.test_stock_universe -q
```

Add tests alongside each service: `tests/test_<feature>.py`.

---

## 7. Browser runtime checklist (manual)

After UI change, in DevTools:

1. **Console** — no `Alpine Expression Error`, no undefined property on tab switch.
2. **Network** — `/api/v7/today` and `/api/v7/decision-hub` return 200 (not 503 loop).
3. **Tab switch** — Today → Portfolio → Dossier → Funds: decision content visible within 5s.
4. **Cold start** — hard refresh: PM strip populates (fallback from today if hub slow).
5. **Evidence** — backtest/fund α shows basis label, not bare “+97%”.

---

## 8. Implementation PR template (anti-fake-completion)

For **each** PR, agent output must include:

```markdown
## Change

- File: `path` — Function/section: `name` — What changed (1–2 sentences)

## Verification

- [ ] Syntax: `python3 -m py_compile ...` or `node --check` if applicable
- [ ] Unit: `unittest ...` → PASS / FAIL
- [ ] curl: endpoint → status / key fields
- [ ] UI: tab X → observed behavior (or: not runtime-tested)

## Status

- [ ] Complete | [ ] Partial — list gaps
- Residual risk: ...
```

---

## 9. Sprint task IDs (link to code)

### Sprint 1 — Decision & Monitoring

| ID   | Task                                  | Files                                                 |
| ---- | ------------------------------------- | ----------------------------------------------------- |
| S1-1 | `decision_bar` schema + API top-level | `schemas/decision_bar.py`, `decision_hub.py`, routers |
| S1-2 | Decision bar UI component (4+ tabs)   | `index.html`                                          |
| S1-3 | Avoid Now category panel              | `index.html` Today, `today.avoid_now`                 |
| S1-4 | Target vs current weight prominent    | `portfolio_decision_console.py`, Portfolio tab        |
| S1-5 | Curve live/backtest labels on sleeves | `fund_manager_console.py`, Funds UI                   |
| S1-6 | IB linkage strip on Portfolio + Today | `execution_readiness`, `index.html`                   |
| S1-7 | Monitors CRUD stub                    | `routers/monitors.py`                                 |

### Sprint 2 — Stock 360

| ID   | Task                                | Files                           |
| ---- | ----------------------------------- | ------------------------------- |
| S2-1 | `stock-intel` decision_bar + thesis | `stock_intel.py`                |
| S2-2 | Peer matrix + live fundamentals     | `stock_intel.py`, dossier peers |
| S2-3 | Options flow quality block          | options services + dossier      |
| S2-4 | `smart_money_tracker.py` tiers      | new service                     |
| S2-5 | Dossier 360 layout (sticky verdict) | `index.html` dossier            |

### Sprint 3 — Portfolio intelligence

| ID   | Task                         | Files                       |
| ---- | ---------------------------- | --------------------------- |
| S3-1 | `portfolio_fit.py`           | new service + stock-intel   |
| S3-2 | Correlation heatmap UI       | `portfolio_risk_cockpit.py` |
| S3-3 | Rebalance simulator endpoint | new router                  |
| S3-4 | Scenario wire-up             | `scenario_engine.py`        |

### Sprint 4 — Smart alpha

| ID   | Task                 | Files                |
| ---- | -------------------- | -------------------- |
| S4-1 | Confluence engine    | new service          |
| S4-2 | Leaders accumulation | `leaders_tracker.py` |
| S4-3 | Thesis drift         | `thesis_drift.py`    |
| S4-4 | PM memory            | `pm_memory.py`       |
| S4-5 | Compare `?a=&b=`     | new router           |

---

## 10. Review-mode deliverable reminder

When user asks for **audit only** (no code), output sections 1–11 from master prompt:

Executive Summary → Tab-by-Tab → Cross-Tab → FE/State Audit → Consolidation → Build Order → Top 10 ROI / Trust Killers / Fake Sophistication → Implementation table (if any) → Brutal Verdict.

Use scores 0–10 and classification: `production-grade | prototype-grade | misleading | unfinished`.

---

## 11. Quick “what’s real today” (2026-05-25 — verify before trusting)

| Claim                         | Status       | Verify                            |
| ----------------------------- | ------------ | --------------------------------- |
| Decision hub API              | Shipped      | `curl .../decision-hub`           |
| avoid_now categories          | API shipped  | `jq .avoid_now` on today          |
| avoid_now dedicated panel     | Partial      | UI grep `avoid_now` in index.html |
| Portfolio decision console    | Shipped      | `curl .../portfolio-decision`     |
| Stock-intel PM answer         | Shipped      | `curl .../stock-intel/AAPL`       |
| Unified Decision Bar all tabs | **Not done** | no `decision_bar` in payloads     |
| Monitors CRUD                 | **Not done** | no `/api/v7/monitors`             |
| Thesis drift / PM memory      | **Not done** | no services                       |
| Full options LEAPS/skew stack | Partial      | dossier options tab               |
| Influencer tier (non-gossip)  | Partial      | smart_money shape only            |

**Re-verify after every sprint** — this table goes stale quickly.

---

## 12. Related docs index

| Doc                                             | Purpose                            |
| ----------------------------------------------- | ---------------------------------- |
| `INSTITUTIONAL_AOS_IMPLEMENTATION_PROMPT.md`    | Master rules + deliverables        |
| `ALPHA_OPERATING_SYSTEM_DEVELOPER_PROMPT_ZH.md` | 三層架構 + Sprint 中英             |
| `DECISION_SYSTEM_DEVELOPER_PROMPT_ZH.md`        | Decision strip + smart money rules |
| `FUND_CONSOLE_DEVELOPER_PROMPT_ZH.md`           | Sleeve / FM / allocator            |
| `PORTFOLIO_ANALYSIS_DEVELOPER_PROMPT_ZH.md`     | Portfolio PM surface               |
| `SINGLE_STOCK_COMMAND_CENTER.md`                | 單股十層                           |
| `PM_PRODUCT_ROADMAP_10_10.md`                   | Gap 表 M1–N8                       |

---

**End.** Paste § COPY block + relevant sprint IDs when opening an agent session.
