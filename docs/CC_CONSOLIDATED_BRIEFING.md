# CC / TradingAI Bot — Consolidated Project Briefing

> **Purpose of this document:** Paste this entire file into ChatGPT (or another advisor) to get informed guidance on architecture, authority boundaries, ops issues, i18n gaps, and next steps.  
> **Live page (recommended):** [http://localhost:8000/briefing](http://localhost:8000/briefing) — includes this doc plus API result-structure appendix and 10 ChatGPT prompts. Plain text: `/briefing.txt`.  
> **Product:** CC (Clarity Console) — *Regime-Aware Market Intelligence Platform* (repo name: TradingAI_Bot)  
> **Version:** 9.0.0 · **Last assembled:** 2026-06-25  
> **No secrets below** — environment variable *names* only.

---

## 1. Project Overview

| Item | Detail |
|------|--------|
| **Name** | CC (Clarity Console) / TradingAI Bot |
| **Purpose** | Professional algorithmic trading platform: regime-aware signal generation, multi-expert council decisions, portfolio risk management, and a live operator dashboard for daily deploy/monitor workflow |
| **Primary UI** | Alpine.js single-page dashboard served at `http://localhost:8000` |
| **API** | FastAPI (Python 3.13), ~60+ routers under `src/api/routers/` |
| **Instant boot** | `_cc_instant.py` binds port 8000 in <1s, proxies API to uvicorn on :8001 in background |
| **Container** | Docker Compose dev: `docker compose -f docker-compose.dev.yml up --build` → container `cc_api_dev` |
| **Broker** | Interactive Brokers (IBKR) via `ib_insync` / `src/services/ibkr_service.py` |
| **Notifications** | Discord (webhook preferred, or bot token + channel), unified via `discord_dispatch.py` |
| **Scheduler** | APScheduler (`src/scheduler/main.py`) — premarket, intraday, EOD jobs (US/Eastern) |
| **Data** | yfinance (primary), optional Polygon/Alpaca/news APIs |
| **AI** | Local Docker Model Runner (gemma3n / llama3.3) + optional OpenAI/Azure OpenAI |
| **Strategies** | Momentum, Breakout, Mean-Reversion, Swing — conviction tiers TRADE / LEADER / WATCH |
| **Regime** | VIX-entropy probabilistic regime (RISK_ON / RISK_OFF / NEUTRAL / crisis NO_TRADE) |

### Stack summary

```
Browser (Alpine.js dashboard)
    ↓
_cc_instant.py :8000  →  proxy  →  FastAPI :8001
    ↓
Services (signals, brief, playbook, ops, IBKR, research)
    ↓
Engines (regime_router, signal_engine, expert_council, auto_trading_engine)
    ↓
External: IBKR Gateway, Discord, yfinance, optional LLM APIs
```

---

## 2. Authority Model (Non-Negotiable)

This is the core safety contract. **Violating it is a product bug, not a feature request.**

### Deploy authority (capital decisions)

| Surface | Role | Can deploy / size / handoff? |
|---------|------|------------------------------|
| **Dashboard** (`today`) | Board review, monitor queue | Only when `deploy_open` |
| **Playbook** (`signals`) | Ranked deploy-qualified names | Only when `deploy_open` |
| **Portfolio** | Positions & risk | Sizing only when gates open |
| **Dossier** | Structure confirm | Confirm-only — no handoff until gates open |
| **IBKR** | Broker connection & bracket handoff | Execution-dependent — not research |

### Research / monitor only (no deploy authority)

| Surface | Role |
|---------|------|
| **Vibe Agent** (`agent`) | Overnight watch, intent parsing, rule evaluation |
| **Strategy Lab** (`strategy-lab`) | NL strategy drafts + validation |
| **Shadow Account** (`shadow`) | Actual vs rule-based behavior diagnostics |
| **Reports** (`reports`) | Inspectable research runs, MD/JSON export |
| **Discovery / Scanners** (`scanners`) | Opportunity research |
| **Flow** (`flow`) | Flow research (often mock/synthetic) |
| **Funds** (`funds`) | Allocation research |
| **Backtest Lab** (`btlab`) | Historical simulation — pass ≠ trade permission |
| **Ops** (`ops`) | Health, engine, alerts — reference/diagnostic |
| **Guide** (`guide`) | Operator manual |

### Binding gates (block deploy)

Deploy is **closed** when any of these bind:

| Gate | Effect |
|------|--------|
| `tradeability` = **WAIT** or **NO_TRADE** | Monitor-only authority |
| `should_trade` = false | Board gate closed |
| `board_decision_state.state` ≠ **DEPLOY** | No deploy review |
| `decision_authority.gates_active` = true | Explicit gate block |
| `data_freshness` = **STALE** or **CRITICAL** | Degraded — sizing blocked |
| `fallback_mode` (brief fallback / stale cache) | Deploy paused |
| `broker_state` in GATEWAY_DOWN, IBAPI_MISSING, SESSION_INACTIVE, DISCONNECTED, ENGINE_OFF, EXEC_BLOCKED, HANDOFF_BLOCKED | Execution blocked |

### Playbook ranking rules

- **AVOID / NO_TRADE / BLOCKED** → `rejectedAvoid` — never in monitor ranking
- Monitor ranking = `watchQualified` + `nearMiss` only (max ~12)
- Dashboard top monitors: watchQualified → nearMiss, never rejectedAvoid
- `structural_valid_for_monitor()` rejects hard_reject rows

### Operator sentence strip (bilingual)

Every page exposes NOW / BLOCKER / NEXT ACTION via `operator_state_contract.py`:
- Global strip active when NOT deploy-open OR fallback OR stale data
- `authority` values: `deploy` | `monitor_only` | `research_only`

**Source of truth:** `src/services/operator_state_contract.py`, `src/services/cc_state.py`

---

## 3. Architecture Map

### Entry & serving

| Component | Path | Role |
|-----------|------|------|
| Instant server | `_cc_instant.py` | Fast dashboard + API proxy |
| FastAPI app | `src/api/main.py` | Main app, lifespan, router mounting |
| Dashboard template | `src/api/templates/index.html` | ~14k-line Alpine.js SPA |
| Static JS | `src/api/static/cc-app.js`, `cc-helpers.js`, `cc-i18n.js` | UI logic + bilingual layer |
| Build script | `scripts/build-cc-template.mjs` | Template bundling |

### Key API routers (representative)

| Router | Prefix / area | Purpose |
|--------|---------------|---------|
| `cc_header.py` | Header pills | Single poll for top-bar status |
| `decision.py` | Today / board | Daily decision & tradeability |
| `playbook.py` | Playbook | Ranked signals, upgrade ladder |
| `monitors.py` | Monitors | Monitor queue API |
| `dossier.py` | Dossier | Stock intel / structure |
| `ops.py` | `/api/ops` | Engine controls, changelog, error log |
| `health.py` | `/health`, `/health/ready` | Liveness, readiness, metrics |
| `ibkr.py` | IBKR | Gateway, session, bracket, handoff |
| `notify.py` | `/api/v7/notify` | Discord test, status, setup |
| `vibe_agent.py` | `/api/v7/vibe-agent` | Agent intents, rules, alerts |
| `research_pipeline.py` | `/api/v7/research` | Strategy Lab, Shadow, Reports, pipeline |
| `position_alerts.py` | Position alerts | Live position monitoring |
| `brief_regenerate.py` | Brief | Morning brief generation |
| `funds.py`, `opportunity_scanner.py` | Discovery | Funds & scanner surfaces |

### Core services

| Service | Path | Role |
|---------|------|------|
| `operator_state_contract.py` | Authority contract | SystemState + PageCapability |
| `cc_state.py` | CC state builder | Execution ladder, board state |
| `ops_operator_console.py` | Ops console | Verdict, blockers, probe vs runtime table |
| `brief_data_service.py` | Morning brief | Brief board data |
| `best_action.py` | Best action | Operator guidance |
| `ibkr_service.py` | IBKR | Connection, brackets, MONITOR/HANDOFF badges |
| `auto_trading_engine.py` | Engine | Scan cycles, signal generation |
| `alert_service.py` | Alerts | Multi-channel alert log |
| `discord_dispatch.py` | Discord | Unified push (webhook or bot) |
| `vibe_agent.py` | Vibe Agent | Intent → rules → alerts |
| `research_pipeline.py` | Research | NL → draft → validate → watch rule |
| `strategy_builder.py` | Strategy Lab | NL strategy drafts |
| `validation_lab.py` | Validation | Backtest validation verdicts |
| `shadow_account.py` | Shadow | Behavior diagnostics |
| `reports_library.py` | Reports | Export MD/JSON/HTML |
| `playbook_operator_intelligence.py` | Playbook | Operator intelligence layer |
| `playbook_signal_universe.py` | Playbook | Signal universe filtering |
| `playbook_upgrade_ladder.py` | Playbook | Upgrade ladder buckets |

### Scheduler & notifications

| Component | Path |
|-----------|------|
| Scheduler | `src/scheduler/main.py` |
| Multi-channel notifier | `src/notifications/multi_channel.py` |
| Discord bot (legacy slash commands) | `src/notifications/discord_bot.py` |
| Discord dispatch (unified) | `src/notifications/discord_dispatch.py` |

### Data & cache

| Path | Contents |
|------|----------|
| `data/cache/brief_latest.json` | Latest brief snapshot |
| `data/cache/playbook_ranked_snapshot.json` | Playbook ranked cache |
| `data/artifacts/discord_channel_id.json` | Resolved Discord channel cache |
| `data/` | Reports, research store, agent journal |

---

## 4. Current Feature Areas

### Vibe Agent (`agent` tab)
- Natural-language intent → structured hypothesis (plan, not permission)
- Watch rules, overnight brief, calm-down guardrails
- API: `/api/v7/vibe-agent/*`
- Safety: `vibe_agent_safety.py` — explicit "monitoring only" contract

### Research Pipeline & Strategy Lab
- One-click pipeline: prompt → strategy draft → validation → watch rule → memory → committee
- Stops at Playbook review — **no live execution**
- Exports: Pine draft, JSON contract, Python pseudo
- API: `/api/v7/research/*`

### Shadow Account
- Compares actual trades vs ideal rule-based shadow path
- Tags: early exits, chasing, revenge trading, overtrading
- Research-only diagnostics

### Reports Library
- Inspectable validation/shadow/committee runs
- Export: markdown, JSON, HTML
- Footer disclaimer: "Research / Monitoring only · 非部署權限"

### Ops Console (`ops` tab)
- System verdict, blockers, next actions
- **Probe vs runtime** table (honest warmup — probe OK ≠ engine healthy)
- Engine start/stop via `/api/ops`
- Advanced diagnostics: self-learning, Thompson sizing, execution metrics (need runtime evidence)
- Degraded mode: `build_degraded_ops_operator_console()` during API warmup

### IBKR Integration
- Gateway → Session → Bracket → Handoff ladder
- Operator badges: **HANDOFF READY** | **MONITOR** | disconnected states
- **MONITOR** = connected + critical checks OK, but bracket/portfolio/handoff gaps remain
- Bracket orders: parent + stop + target (OCA)
- Dev compose sets `CC_SKIP_IB_INSYNC=1` (IB disabled in Docker dev by default)

### Discord Notices
- Unified dispatch: webhook (recommended) OR bot token + channel ID/name
- Research events muted by default (`DISCORD_NOTIFY_RESEARCH=false`)
- Dedup cooldown: `DISCORD_ALERT_COOLDOWN_SEC` (default 300s)
- Setup helper: `GET /api/v7/notify/setup`, test ping: `POST /api/v7/notify/test`

### i18n (繁中 · English)
- `cc-i18n.js` — runtime DOM augmentation: static labels → `"繁中 · English"`
- Primary display: Traditional Chinese; English preserved as reference
- Operator sentences in `operator_state_contract.py` are bilingual at source
- Alpine `x-text` bound nodes intentionally skipped by i18n layer (localized in `cc-helpers.js` instead)

---

## 5. Recent Work Completed

### Committed (through 8d9ae35)

| Area | What changed |
|------|--------------|
| **Ops i18n (8d9ae35)** | Remaining Ops section titles + HTTP 500 banner wired via `CCHelpers` title maps and Alpine wrappers (boundary/times/events/why-no-signals, Phase 9, cache, self-learn) |
| **Blank page fix (5d660c7)** | CC dashboard gzip/loader hardening; Ops advanced diagnostics i18n extended |
| **Research ship (7133c26)** | Ops i18n, Discord dispatch, Vibe Agent + research pipeline surfaces end-to-end with tests |
| **Authority UI (76979b4)** | CC hardening: authority-safe UI + zh-HK copy |

### Earlier / in-progress (may include uncommitted working tree)

| Area | What changed |
|------|--------------|
| **Operator state contract** | New unified `SystemState` + `PageCapability` — global strip, per-tab authority, playbook rank buckets (`operator_state_contract.py` + tests) |
| **i18n** | `cc-i18n.js` bilingual augmentation layer; guide/ops/surface labels in 繁中·English |
| **Discord dispatch fix** | New `discord_dispatch.py` — webhook/bot/channel-name resolution, dedup, research mute; `notify.py` wired; `config/discord.env.example` |
| **backend_fatal / health fix** | `build_degraded_ops_operator_console()` surfaces `backend_fatal_hint` when backend child crashes; `/health` reports `mode=full` vs `loading` |
| **IBKR bracket MONITOR state** | `ibkr_service.py` emits **MONITOR** badge when connected but bracket/portfolio/handoff incomplete |
| **Ops probe/runtime** | Bilingual 探測 vs 執行時證據 table; `localizeOpsRuntimeText()` + `ops_operator_console.py` `_ops_bi()`; warmup mode doesn't fake "OK" |
| **Docker models reference** | `config/docker-models.env.example` — role vars `LOCAL_MODEL_ADVISOR` / `REVIEWER` / `EMBED`; MCP not in API container |
| **Advanced diagnostics** | Bilingual collapsed + expanded block (`opsAdvancedDiagnosticsTitle`, section_states via CCHelpers); engine-off / insufficient-sample copy localized client-side |
| **Research surfaces** | Vibe Agent, Research Pipeline, Strategy Builder, Shadow, Reports — new services + routers + tests |
| **Playbook intelligence** | `playbook_operator_intelligence`, `playbook_signal_universe`, `playbook_upgrade_ladder` |
| **CC template build** | `scripts/build-cc-template.mjs`, gzip dashboard cache |
| **Dev scripts** | `scripts/dev/restart-and-verify-cc.sh`, `fix-cc-black-screen.sh`, `start-cc-offline.sh`, `discord_setup_channel.py` |

---

## 6. Known Issues / Open Items

### Discord

| Issue | Detail |
|-------|--------|
| **403 without webhook** | Bot-token mode needs `Send Messages` permission in target channel; missing permissions → HTTP 403 logged as `Discord bot channel 403` |
| **Missing `DISCORD_WEBHOOK_URL`** | `has_discord` false → no pushes; setup hint in `/api/v7/notify/status` |
| **Recommended fix** | Set `DISCORD_WEBHOOK_URL` in `.env` (no bot permissions needed) — see `config/discord.env.example` |

### Ops / Engine

| Issue | Detail |
|-------|--------|
| **Engine off** | `ENGINE_OFF` blocker; advanced diagnostics panels show `Inactive` / `insufficient_sample` |
| **Insufficient sample** | Self-learning, Thompson sizing, execution metrics need ≥5 observations + engine running |
| **Warmup mode** | On cold start, Ops shows "API warmup" — probe OK (disk brief) ≠ live engine health |
| **Backend child crash** | `backend_fatal_hint` surfaced in degraded ops console |

### Data / UI

| Issue | Detail |
|-------|--------|
| **Chinese incomplete** | `cc-i18n.js` only covers static literal labels; dynamic Alpine `x-text` strings often English-only |
| **Missing data** | WAIT/NO_TRADE days, engine off, or stale brief → empty playbook/deploy lists (often correct, not a bug) |
| **Ops English strings** | Probe/runtime + advanced diagnostics + section titles + HTTP 500 banner bilingual (8d9ae35). Remaining: some degraded warmup strings outside Ops, dynamic Alpine `x-text` on non-Ops tabs. |
| **Flow mock mode** | Flow surface synthetic — "colour only" per guide |
| **IBKR in Docker dev** | `CC_SKIP_IB_INSYNC=1` — broker features unavailable in dev container |

### Tests

- **124** test files under `tests/` (including new: `test_operator_state_contract`, `test_discord_dispatch`, `test_vibe_agent`, `test_research_pipeline`, etc.)
- Local `pytest` not available in bare shell — run inside Docker/venv: `python -m pytest tests/ -q`
- Test status at doc time: **not verified in this session** (no pytest module in host Python)

---

## 7. Environment

### Docker Compose (dev)

```bash
docker compose -f docker-compose.dev.yml up --build
# Dashboard: http://localhost:8000
# Container: cc_api_dev
# Ports: 8000 (instant), 8001 (FastAPI backend)
```

### Key compose environment variables (set in `docker-compose.dev.yml`)

| Variable | Dev value | Purpose |
|----------|-----------|---------|
| `CC_ENV` | `development` | Dev mode, higher rate limits |
| `CC_AUTO_START_ENGINE` | `1` | Auto-start AutoTradingEngine on boot |
| `CC_SKIP_IB_INSYNC` | `1` | Skip IBKR in Docker dev |
| `API_SECRET_KEY` | `dev-secret-local` | API auth (dev only) |
| `RUNNING_IN_DOCKER` | `1` | Docker-aware paths |
| `LOCAL_LLM_ENABLED` | `auto` | Local LLM routing (`auto` / `on` / `off`) |
| `LOCAL_MODEL_ADVISOR` | e.g. `ai/gemma3` | Advisor role (`ai_service.py`) |
| `LOCAL_MODEL_REVIEWER` | e.g. `ai/qwen3-coder` | Reviewer role |
| `LOCAL_MODEL_EMBED` | e.g. `ai/all-minilm-l6-v2-vllm` | Embeddings |
| `LOCAL_MODEL_FAST` / `HEAVY` | legacy aliases | Still in compose; prefer ADVISOR/REVIEWER/EMBED |
| `YFINANCE_CACHE_DIR` | `/tmp/yfinance-cache` | yfinance cache |
| `LOG_LEVEL` | `INFO` | Logging |

### `.env` variable names (no values — configure locally)

**Core / API**
- `API_SECRET_KEY`, `API_KEY`, `CC_ENV`, `CC_PORT`, `CC_AUTO_START_ENGINE`, `CC_SKIP_IB_INSYNC`, `CC_INSTANT_NO_BACKEND`, `LOG_LEVEL`, `SERVICE_NAME`, `ENVIRONMENT`

**Discord**
- `DISCORD_WEBHOOK_URL`, `DISCORD_ALERT_WEBHOOK`, `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `DISCORD_ALERT_CHANNEL_ID`, `DISCORD_CHANNEL_NAME`, `DISCORD_NOTIFY_ENABLED`, `DISCORD_NOTIFY_RESEARCH`, `DISCORD_ALERT_COOLDOWN_SEC`

**IBKR**
- `IB_HOST`, `IB_PORT`, `IB_CLIENT_ID`, `IB_ACCOUNT`, `IBKR_HOST`, `IBKR_CLIENT_ID`

**Market data**
- `POLYGON_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_ENDPOINT`, `ALPACA_PAPER`

**AI / LLM**
- `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_MODEL_MINI`, `AZURE_OPENAI_*`, `LOCAL_LLM_*`, `LOCAL_MODEL_ADVISOR`, `LOCAL_MODEL_REVIEWER`, `LOCAL_MODEL_EMBED`, `LOCAL_MODEL_FAST`, `LOCAL_MODEL_HEAVY`, `AI_DISABLED`
- Reference: `config/docker-models.env.example` — pull with `docker model pull <tag>`, rebuild API image to pick up env changes

**MCP (IDE, not Docker API)**
- CC API container (`cc_api_dev`) has **no MCP sidecar**. MCP servers run from Cursor/VS Code host (`src/services/mcp/` is extension-layer). Configure MCP in the IDE, not in `docker-compose.dev.yml`.

**Database / cache**
- `POSTGRES_*`, `REDIS_*`

**Risk / trading**
- `MAX_POSITION_PCT`, `MAX_DRAWDOWN_PCT`, `RISK_PER_TRADE`, `MAX_VIX_FOR_TRADING`, `REGIME_VIX_CRISIS`, `VIX_CRISIS`, `MAX_OPEN_POSITIONS`, `PREMARKET_REPORT_TIME`, etc.

**Other brokers**
- `MT5_*`, `FUTU_*`

### Health endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /health` | No | Basic status, version, `mode` (full vs loading) |
| `GET /health/ready` | Yes | Readiness (engines + DB + data) |
| `GET /health/live` | No | K8s liveness |
| `GET /api/v7/notify/status` | No | Discord config status |

---

## 8. File Map

| Path | Description |
|------|-------------|
| `_cc_instant.py` | Instant server + API proxy |
| `docker-compose.dev.yml` | Dev Docker compose (`cc_api_dev`) |
| `docker/Dockerfile.api` | API container build |
| `src/api/main.py` | FastAPI application entry |
| `src/api/templates/index.html` | Main dashboard SPA |
| `src/api/static/cc-app.js` | Primary Alpine app logic |
| `src/api/static/cc-helpers.js` | Shared helpers, banner copy |
| `src/api/static/cc-i18n.js` | Bilingual DOM augmentation |
| `src/api/routers/cc_header.py` | Header status poll |
| `src/api/routers/decision.py` | Today / board decision |
| `src/api/routers/playbook.py` | Playbook ranked API |
| `src/api/routers/ops.py` | Ops engine controls |
| `src/api/routers/health.py` | Health & metrics |
| `src/api/routers/ibkr.py` | IBKR API surface |
| `src/api/routers/notify.py` | Discord notify/test/setup |
| `src/api/routers/vibe_agent.py` | Vibe Agent API |
| `src/api/routers/research_pipeline.py` | Research / Strategy Lab API |
| `src/services/operator_state_contract.py` | Authority contract (SystemState, PageCapability) |
| `src/services/cc_state.py` | CC execution ladder state |
| `src/services/ops_operator_console.py` | Ops console builder |
| `src/services/ibkr_service.py` | IBKR service + MONITOR badge |
| `src/services/brief_data_service.py` | Brief data |
| `src/services/best_action.py` | Best action guidance |
| `src/engines/auto_trading_engine.py` | Auto trading engine loop |
| `src/notifications/discord_dispatch.py` | Unified Discord dispatch |
| `src/notifications/discord_bot.py` | Legacy Discord bot |
| `src/scheduler/main.py` | APScheduler jobs |
| `src/core/config.py` | Environment config loader |
| `src/core/version.py` | APP_VERSION, product identity |
| `config/discord.env.example` | Discord setup template |
| `config/docker-models.env.example` | Docker Model Runner env reference |
| `scripts/build-cc-template.mjs` | CC template build |
| `scripts/dev/*.sh` | Dev restart/verify scripts |
| `tests/test_operator_state_contract.py` | Authority contract tests |
| `tests/test_discord_dispatch.py` | Discord dispatch tests |
| `tests/test_vibe_agent.py` | Vibe Agent tests |
| `tests/test_research_pipeline.py` | Research pipeline tests |
| `tests/test_ops_surface_integrity.py` | Ops UI integrity tests |
| `AGENTS.md` | Agent coding guidance (SettingsView cachedState pattern) |
| `docs/ARCHITECTURE.md` | Full architecture doc |
| `docs/CC_CONSOLIDATED_BRIEFING.md` | This file |
| `src/api/routers/advisor_briefing.py` | Live advisor briefing page at `/briefing` |
| `src/api/briefing_content.py` | Briefing HTML/text assembler (doc + API shapes) |

---

## 9. User's Recent UI Complaints

| Complaint | Root cause / status |
|-----------|---------------------|
| **Chinese incomplete** | `cc-i18n.js` only translates static literal DOM text (~300 entries). Dynamic content from API (`x-text`, `x-html`) and Ops probe/runtime table remain English. Operator sentences in contract are bilingual; many panel labels are not. |
| **Missing data** | Common on WAIT/NO_TRADE days, engine-off, stale brief fallback, or pre-warmup — playbook deploy list empty by design. Discovery 0 hits on WAIT day is often correct. Portfolio/broker reconciliation gaps after session. |
| **Ops English strings** | Probe/runtime + advanced diagnostics + section titles + HTTP 500 banner bilingual (8d9ae35). Remaining: degraded warmup copy in non-Ops areas; dynamic API-driven strings on other tabs. |
| **Black screen (reported)** | Mitigated via gzip dashboard cache (`cc-dashboard.html.gz`), `_cc_instant.py` chunked reads, `scripts/dev/fix-cc-black-screen.sh` |
| **Discord not pinging** | Missing `DISCORD_WEBHOOK_URL` or bot 403 — see §6 |

---

## 10. Suggested Advisory Prompts for ChatGPT

Copy one of these after pasting this briefing (full set of 10 on http://localhost:8000/briefing Appendix C):

1. **Authority audit:** "Given the authority model in §2, review my planned feature [describe feature] and tell me which tab(s) it belongs on, what `PageCapability` flags it needs, and what gates must block it when tradeability is WAIT."

2. **Ops diagnostics:** "My Ops tab shows engine off and insufficient sample on advanced diagnostics. Using §6–7, give me a step-by-step recovery checklist for Docker dev (`cc_api_dev`) including which env vars to verify and which `/health` / `/api/ops` endpoints to hit."

3. **i18n strategy:** "§9 says Chinese is incomplete. Propose a maintainable i18n plan for CC that doesn't break the 14k-line `index.html` tests — should we extend `cc-i18n.js`, move Ops strings server-side, or extract a locale JSON? Prioritize remaining English in degraded warmup copy."

4. **Discord setup:** "I want reliable operator alerts without bot permission issues. Based on §6 and the Discord dispatch architecture, recommend webhook vs bot mode and exact `.env` keys for my setup (macOS Docker dev)."

5. **Research vs deploy boundary:** "I'm building [Vibe Agent rule / Strategy Lab draft / Shadow analysis]. Confirm it cannot grant deploy authority, list the API surfaces involved, and suggest UX copy that makes the research-only boundary obvious to a Chinese-speaking operator."

6. **Architecture review:** "Review the stack in §1 and propose which services should stay synchronous vs async for ranked playbook under 2s p95."

7. **Ops honesty model:** "Explain how probe vs runtime evidence should be presented so operators don't confuse disk-brief OK with engine health."

8. **Performance:** "Propose a polling budget for cc-header, playbook ranked, and ops console without hammering yfinance."

9. **Testing plan:** "Design pytest coverage for SystemState/PageCapability across WAIT, NO_TRADE, and deploy_open with stale data."

10. **IBKR MONITOR ladder:** "When monitoring_only=true but connected=true, what should Playbook and Portfolio show?"

---

## Quick Reference: Daily Operator Flow

```
1. Dashboard (today)  →  check tradeability + global strip
2. Playbook (signals) →  deploy-qualified only if deploy_open
3. Dossier            →  structure confirm (no handoff until gates open)
4. Agent / Strategy Lab / Shadow / Reports → research only
5. Ops                →  health, engine, Discord
6. IBKR               →  Gateway → Session → Bracket → Handoff ladder
```

**When in doubt:** If `authority` ≠ `deploy` or `deploy_open` is false → **monitor and research only**.

---

*End of consolidated briefing.*
