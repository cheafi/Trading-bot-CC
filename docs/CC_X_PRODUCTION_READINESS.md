# CC X — Production Readiness & Ops

**Product:** CC X · `TradingAI_Bot`  
**Updated:** 2026-08-25

> Architecture → [`CC_X_ARCHITECTURE.md`](./CC_X_ARCHITECTURE.md) · Backlog → [`CC_X_ENGINEERING_BACKLOG.md`](./CC_X_ENGINEERING_BACKLOG.md)

---

## Prerequisites

| Requirement | Version | Notes                      |
| ----------- | ------- | -------------------------- |
| Python      | 3.11+   | Tested on 3.13             |
| Docker      | 24+     | Recommended for dev parity |
| Git         | any     | Clone repo                 |

---

## Installation

```bash
git clone https://github.com/cheafi/Trading-bot-CC
cd Trading-bot-CC
python -m venv venv && source venv/bin/activate
pip install -r requirements/base.txt
pip install -r requirements/notifications.txt requirements/engine.txt
cp .env.example .env   # never commit .env
```

Configuration reference: [`config/default.yaml`](../config/default.yaml), [`.env.example`](../.env.example).

---

## Docker dev (recommended)

```bash
docker compose -f docker-compose.dev.yml up --build
# Dashboard: http://localhost:8000  ·  container: cc_api_dev
```

| Variable               | Dev default        | Purpose                |
| ---------------------- | ------------------ | ---------------------- |
| `CC_ENV`               | `development`      | Dev mode               |
| `CC_AUTO_START_ENGINE` | `1`                | Auto-start engine      |
| `CC_SKIP_IB_INSYNC`    | `1`                | Skip IBKR in container |
| `API_SECRET_KEY`       | `dev-secret-local` | API auth (dev only)    |
| `LOCAL_MODEL_ADVISOR`  | e.g. `ai/gemma3`   | Local LLM advisor      |

---

## Health endpoints

| Endpoint                    | Auth | Purpose                           |
| --------------------------- | ---- | --------------------------------- |
| `GET /health`               | No   | Version, `mode` (full vs loading) |
| `GET /health/ready`         | Yes  | Engines + DB + data               |
| `GET /health/live`          | No   | Liveness                          |
| `GET /api/v7/notify/status` | No   | Discord config status             |

---

## Public access (dev tunnels only)

**Development only** — do not expose production or real broker credentials.

1. Start CC: `python _cc_instant.py` or docker compose dev
2. Install tunnel: `brew install cloudflared` (or ngrok)
3. Run: `./scripts/dev/expose-cc-public.sh`
4. Copy the HTTPS URL from terminal output

Optional: `config/tunnel.env.example` — `TUNNEL_PROVIDER`, `NGROK_AUTHTOKEN`, `API_SECRET_KEY`, `CORS_ORIGINS`.

Docker tunnel profile:

```bash
docker compose -f docker-compose.dev.yml -f docker-compose.tunnel.yml --profile tunnel up
```

Telegram alerts when tunneled: [`TELEGRAM_SETUP.md`](./TELEGRAM_SETUP.md) (`CC_PUBLIC_BASE_URL` for link targets).

---

## Channel setup

| Channel                  | Doc                                                  |
| ------------------------ | ---------------------------------------------------- |
| Telegram operator alerts | [`TELEGRAM_SETUP.md`](./TELEGRAM_SETUP.md)           |
| Futu screenshot capture  | [`FUTU_CAPTURE_SETUP.md`](./FUTU_CAPTURE_SETUP.md)   |
| Discord webhooks / bot   | `config/discord.env.example`, `/api/v7/notify/setup` |

---

## Soak / staging checklist

Run after stabilization passes. Copy-only recovery — no fake authority.

### Cold start

| Step                                      | Pass criteria                       |
| ----------------------------------------- | ----------------------------------- |
| Open `/` fresh                            | Instant shell; warmup strip visible |
| Poll `/health` until `mode=full`          | ≤ ~2 min typical                    |
| No green TRADE pills while `mode=loading` | Authority safe                      |

### IBKR ladder

| Step                               | Pass criteria                         |
| ---------------------------------- | ------------------------------------- |
| IBKR tab shows LOGIN/OFFLINE/READY | —                                     |
| Playbook on WAIT                   | No `Send to IBKR` on playbook surface |
| Mission hint                       | READY + bracket before handoff        |

### Engine OFF / stale data

| Step               | Pass criteria                              |
| ------------------ | ------------------------------------------ |
| Engine off         | ENGINE OFF pill; blockers in mission panel |
| Stale market strip | Honest downgrade; no sizing CTA            |

### WAIT day soak (30+ min)

| Step             | Pass criteria                  |
| ---------------- | ------------------------------ |
| Dashboard        | Today focus; monitors hint     |
| Playbook         | WATCH ONLY; near-miss ≠ deploy |
| Periodic refresh | No new green TRADE pills       |

**Prereqs:** `node scripts/build-cc-template.mjs --check` green; Playwright `cc-e2e` green on CI.

---

## Known ops issues

| Issue                            | Mitigation                                       |
| -------------------------------- | ------------------------------------------------ |
| Discord 403                      | Prefer `DISCORD_WEBHOOK_URL` over bot token      |
| Engine off / insufficient sample | Start engine via Ops; need ≥5 observations       |
| IBKR unavailable in Docker dev   | Expected with `CC_SKIP_IB_INSYNC=1`              |
| Chinese i18n incomplete          | Static labels only; dynamic API strings often EN |

---

## Pre-deploy gate

- [ ] `bash scripts/verify_10_10.sh` green
- [ ] Authority tests green (`test_operator_state_contract`, `test_decision_board_service`, `test_decision_board_authority_cache`)
- [ ] Soak checklist passed on staging
- [ ] No secrets in committed files
- [ ] `.env` not in git
- [ ] `node scripts/build-cc-template.mjs --check` green

---

## Chaos tests (planned — CCX-092)

| Scenario                    | Inject                             | Expected behavior                            |
| --------------------------- | ---------------------------------- | -------------------------------------------- |
| IBKR disconnect mid-handoff | Kill gateway during bracket submit | HANDOFF_BLOCKED; no orphan deploy state      |
| Regime service exception    | Force regime router error          | FAIL CLOSED → WAIT                           |
| Stale cache with old rank   | Serve aged playbook snapshot       | `deploy_open` recomputed false if gates bind |
| Engine OFF during poll      | Stop AutoTradingEngine             | ENGINE OFF pill; mission blockers update     |
| Data STALE during deploy    | Mark freshness CRITICAL            | Deploy CTAs hidden                           |

**Verified (2026-08-25):** regime fail-closed + never-cache-deploy_open — commit `8b51620`.

---

## Performance targets

Cache affects **latency only**, never **permission**.

| Surface                  | Current (observed)   | Target                  | Module                          |
| ------------------------ | -------------------- | ----------------------- | ------------------------------- |
| Playbook ranked (cached) | 8–15s live scan days | **<1.5s p95** cache hit | `playbook_ranked_snapshot.json` |
| Playbook ranked (live)   | 8–15s                | **<2s p95** with SWR    | Snapshot writer                 |
| Today load               | 3–5s                 | **<800ms**              | `_cc_instant.py`, gzip          |
| Dossier core             | Partial instant      | **<500ms** core fields  | `live_dossier.py`               |
| cc-header poll           | 15s + 60s freshness  | **1 unified poll**      | `cc_header.py`, board service   |
| API QPS (multi-tab)      | Poll storm           | **−40%**                | Poll consolidation              |

**Forbidden:** skip gate computation; cache `deploy_open=true`; client-side rank bypass.

**CI gates (todo):** k6 p95 (CCX-091); Playwright E2E (CCX-090).

---

## Security checklist

| Area                 | Status             | Action                           |
| -------------------- | ------------------ | -------------------------------- |
| API auth             | Dev key in compose | Rotate `API_SECRET_KEY` in prod  |
| Secrets in code      | Clean — env vars   | Never commit `.env`              |
| Telegram HTML escape | ✓                  | `escape_html()` in `telegram.py` |
| Input validation     | ✓                  | `validate_ticker()` on alerts    |
| RBAC / audit ledger  | Not started        | CCX-120                          |
| IBKR credentials     | Env vars           | Never logged                     |
| Rate limiting        | Dev relaxed        | Tighten in production            |
| Dependency audit     | Not in CI          | Add `pip audit`                  |

---

## CI gaps

| Gap                 | Current          | Target                       | Backlog          |
| ------------------- | ---------------- | ---------------------------- | ---------------- |
| Playwright E2E      | Absent / partial | WAIT → deploy disabled in CI | CCX-090          |
| k6 performance      | Absent           | p95 gate on playbook ranked  | CCX-091          |
| Provenance contract | Partial          | CI fails on unlabeled prices | CCX-006, CCX-007 |
| Chaos IBKR          | Absent           | Reconnect test in staging    | CCX-092          |

---

## Runbooks

### Authority incident (deploy drift)

1. Compare `deploy_open` on Today, Playbook ranked, cc-header
2. Run `pytest tests/test_decision_board_authority_cache.py -q`
3. Rollback: revert router attach only — gates stay in truth model + operator contract

### IBKR handoff failure

1. Confirm LOGIN → READY ladder honest
2. Check `execution_readiness` HARD blocks
3. Log fill vs plan in `execution_analytics.py`

---

## Historical soak doc

Full step-by-step: [`archive/CC_SOAK_STAGING_RUNBOOK.md`](./archive/CC_SOAK_STAGING_RUNBOOK.md) (superseded by this file).
