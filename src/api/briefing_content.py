"""Assemble advisor briefing text for /briefing — copy-paste friendly, no secrets."""

from __future__ import annotations

import html

from src.services.guide_briefing import resolve_briefing_path


def _load_consolidated_md() -> str:
    briefing_path = resolve_briefing_path()
    if briefing_path is not None:
        return briefing_path.read_text(encoding="utf-8")
    return "# CC Consolidated Briefing\n\n(Markdown source missing.)\n"


def _branch_update_section() -> str:
    return """
---

## APPENDIX A — Branch state (commits through 8d9ae35)

| Commit | Summary |
|--------|---------|
| **8d9ae35** | Wire remaining Ops section titles + HTTP 500 banner i18n (`CCHelpers` title maps, Alpine wrappers for boundary/times/events/why-no-signals, Phase 9, cache, self-learn panels) |
| **5d660c7** | Fix CC blank page; extend Ops advanced diagnostics i18n |
| **7133c26** | Ship CC ops i18n, Discord dispatch, research/vibe surfaces end-to-end with tests |
| **76979b4** | CC hardening: authority-safe UI + zh-HK copy |
| **403296c0** | (not in repo history — no matching commit at doc time) |

**Live page:** http://localhost:8000/briefing (also `/advisor-briefing`)
**Assembled:** 2026-06-25
"""


def _result_structures_section() -> str:
    return """
---

## APPENDIX B — API result structures (from source code)

All shapes below are top-level keys or nested objects the operator dashboard consumes.
Field types are descriptive, not exhaustive for every nested leaf.

### B.1 GET /health  (`src/api/routers/health.py` → HealthResponse)

```
{
  "status": "healthy" | "degraded" | "unhealthy",
  "timestamp": "<ISO-8601 UTC>",
  "version": "<APP_VERSION>",
  "database": "<optional — detailed only>",
  "redis": "<optional>",
  "uptime_seconds": <float>,
  "phase9_engines": <optional dict>,
  "ai_status": {
    "status": "disabled" | "active" | "missing_key",
    "provider": "azure_openai" | "openai" | null,
    "reason": "<optional>"
  },
  "mode": "full" | "loading"
}
```

- `mode=full` — FastAPI backend on :8001 answering (clears dashboard warmup banner).
- `mode=loading` — `_cc_instant.py` shell only; Ops uses degraded console.

### B.2 GET /health/ready

```
{
  "ready": <bool>,
  "timestamp": "<ISO>",
  "checks": {
    "database": <bool>,
    "market_data": <bool>,
    "data_freshness": <bool>,
    "phase9_engines": <bool>
  },
  "ai_status": { ... }
}
```

### B.3 SystemState  (`build_system_state` in operator_state_contract.py)

Attached to payloads as `system_state` via `attach_system_state()`.

```
{
  "regime": "<tradeability string>",
  "tradeability": "RISK_ON" | "RISK_OFF" | "NEUTRAL" | "WAIT" | "NO_TRADE" | ...,
  "data_freshness": "FRESH" | "STALE" | "CRITICAL",
  "engine_state": "ON" | "OFF",
  "broker_state": "CONNECTED" | "HANDOFF_READY" | "BRACKET_READY" | "GATEWAY_DOWN" |
                  "IBAPI_MISSING" | "SESSION_INACTIVE" | "DISCONNECTED" | "ENGINE_OFF" |
                  "EXEC_BLOCKED" | "HANDOFF_BLOCKED" | "UNKNOWN",
  "board_mode": "live" | "fallback_brief" | "stale_cache" | ...,
  "authority": "deploy" | "monitor_only" | "research_only",
  "fallback_mode": <bool>,
  "deploy_open": <bool>,
  "global_strip_active": <bool>,
  "blocker_compact": "<bilingual one-liner>",
  "repair_priority": "<bilingual repair hint>",
  "operator_sentence": {
    "now": "...",
    "blocker": "...",
    "next_action": "...",
    "scope": "global",
    "line": "現況 · NOW: ... · 阻擋 · BLOCKER: ... · 下一步 · NEXT: ..."
  },
  "chips": [
    {"label": "<tradeability>", "class": "tradeability"},
    {"label": "DATA FRESH|STALE|CRITICAL", "class": "data"|"warn"},
    {"label": "<broker state words>", "class": "broker"},
    {"label": "ENGINE ON|OFF", "class": "engine"}
  ]
}
```

### B.4 PageCapability  (`build_page_capability` in operator_state_contract.py)

Attached as `page_capability` when tab is known.

```
{
  "page_id": "<tab key>",
  "tab": "<tab key>",
  "surface_type": "deploy_authority" | "research" | "confirm_structure" |
                  "research_monitoring" | "reference" | "execution_dependent",
  "can_deploy": <bool>,
  "can_monitor": <bool>,
  "can_research": <bool>,
  "can_confirm_structure": <bool>,
  "can_size": <bool>,
  "can_handoff": <bool>,
  "can_use_cached": <bool>,
  "visible_warning_level": "none" | "amber" | "red",
  "primary_action": "<string>",
  "blocked_reason_compact": "<string>",
  "operator_sentence": { "now", "blocker", "next_action", "scope", "line" },
  "research_only_once": <bool>
}
```

Tab keys: today, signals, scanners, dossier, flow, funds, guide, agent, strategy-lab,
shadow, reports, portfolio, ops, ibkr, btlab.

### B.5 GET /api/ops/cc-header  (`cc_header.py`)

Single poll for top-bar pills and global strip inputs.

```
{
  "as_of": "<ISO Z>",
  "healthy": <bool>,
  "display_mode": "LIVE" | "PAPER",
  "trust_mode": "PAPER" | "LIVE",
  "engine": {
    "running": <bool>,
    "dry_run": <bool>,
    "circuit_breaker": <bool>,
    "circuit_breaker_reason": "<string>"
  },
  "freshness": { "worst_tier", "streams": [...], ... },
  "brief_status": { "ok": <bool>, "latest": { "tier", "as_of", ... } },
  "risk_alerts": { "count", "by_severity", ... },
  "ibkr": <IBKR status object — see B.8>,
  "pills": { "data": "FRESH|STALE|CRITICAL", "brief": "...", "alerts": <int> },
  "components": { "market_data", "regime_router", "broker": <bool>, ... },
  "decision_authority": { "authority_level", "gates_active", "gates", "source", "degraded", ... },
  "cc_state": <see B.6>,
  "system_state": <see B.3>,
  "page_capability": <see B.4 — when ?tab= provided>,
  "page_authority_mode": "active" | "degraded_board" | "fallback_board" | "diagnostic",
  "portfolio_context": {
    "mode", "book_label", "position_count", "positions_label",
    "broker_sync", "broker_sync_label", "rebalance_only", "rebalance_label", "source"
  },
  "surface_mode": "<optional when tab set>",
  "header_summary": "<optional tab-aware summary>",
  "providers": {
    "yfinance": <bool>,
    "regime_router": <bool>,
    "alpaca": { "configured", "connected", "paper" }
  }
}
```

### B.6 cc_state  (`build_cc_state` in cc_state.py)

```
{
  "tradeability": "<string>",
  "should_trade": <bool>,
  "board_decision_state": { "state": "DEPLOY" | "RESEARCH_ONLY" | "SUSPENDED", ... },
  "execution_state": {
    "state": "<broker/engine ladder state>",
    "broker_connected", "gateway_reachable", "api_port_open",
    "engine_running", "circuit_breaker", "bracket_ready", "handoff_ready",
    "monitoring_only", "blockers": [{ "domain", "code", "label" }],
    "label", "level"
  },
  "freshness_state": {
    "worst_tier", "worst_domain", "market_tier", "board_tier",
    "execution_tier", "board_source", ...
  },
  "surface_authority": <optional>
}
```

### B.7 Ops operator console  (`build_ops_operator_console` / `build_degraded_ops_operator_console`)

Built server-side; surfaced on Ops tab. Top-level keys:

```
{
  "as_of": "<ISO Z>",
  "degraded": <bool — true in warmup>,
  "research_only": <bool — warmup>,
  "system_verdict": "<human string>",
  "verdict_code": "RUNNABLE" | "PAPER_READY" | "PAPER_ONLY" | "NOT_RUNNABLE" |
                  "LIVE_BLOCKED" | "WARMING",
  "verdict_detail": "<string>",
  "verdict_summary": "<verdict> — <detail>",
  "runnable": <bool>,
  "paper_ready": <bool>,
  "blockers": ["<string>", ...] | max 8,
  "next_actions": [{ "step", "action", "why" }, ...] | max 6,
  "last_times": { ... },
  "metrics_display": {
    "uptime": { "display", "value", "reason" },
    "regime_latency_ms": { "display", "value", "reason" }
  },
  "engine_controls": {
    "running", "can_start", "can_stop", "can_run_cycle",
    "auto_start_env", "start_endpoint", "run_cycle_endpoint"
  },
  "execution_layers": [
    { "layer", "status", "tone": "ok"|"warn"|"fail", "detail" }
    // layers: Service reachable, Engine running, Scheduler alive, Session auth,
    //         Order path tested, Engine handoff, Last successful cycle
  ],
  "execution_boundary": {
    "market_data", "signal_engine", "execution_mode", "broker_path", ...
  },
  "signal_zero_reason": "<string>",
  "operational_events": [...],
  "scheduler": { "alive", "label", "detail", ... },
  "last_events": {
    "last_cycle", "last_brief", "ibkr_heartbeat", "market_data_tier"
  },
  "engine": {
    "running", "dry_run", "cycle_count", "signals_today", "trades_today",
    "cached_recommendations", "circuit_breaker"
  },
  "why_no_signals": [...],
  "section_states": {
    "self_learning": { "state", "label", "detail" },
    "thompson_sizing": { ... },
    "pipeline_stats": { ... },
    "execution_metrics": { ... }
  },
  "component_evidence": [
    {
      "name": "market_data" | "regime_router" | "broker",
      "ok": <bool>,
      "tier": "probe_ok" | "runtime_ok" | "warming" | ...,
      "label", "probe", "runtime_evidence", "evidence"
    }
  ],
  "diagnostics": {
    "probe_only_mode", "warming_mode", "engine_stopped", "page_intro",
    "signals_today_note", "probe_table_note", "engine_stopped_banner", ...
  },
  "providers_honest": {
    "market_data": { "probe", "runtime" },
    "regime_router": { "probe", "runtime" },
    "broker": { "probe", "runtime" }
  },
  "machines_health": <decision machines panel from decision_machines.py>,
  "ibkr": { see B.8 ops subset },
  "providers", "uptime", "latency", "startup_time"
}
```

Degraded warmup adds: `backend_fatal_hint` in blockers when child :8001 crashes.

### B.8 IBKR readiness  (`IBKRService.status()` in ibkr_service.py`)

```
{
  "connected": <bool — effective session>,
  "socket_connected": <bool>,
  "session_usable": <bool>,
  "gateway_reachable": <bool>,
  "api_port_open": <bool>,
  "mode": "paper" | "live",
  "ibapi_available": <bool>,
  "host", "port", "docker", "client_id", "next_order_id",
  "account_loaded", "account_id",
  "health": {
    "session_usable", "session_status", "account_status",
    "market_data_status", "secdef_status", "handoff_status",
    "summary_label", ...
  },
  "health_label": "<display label — MONITOR | HANDOFF READY | ...>",
  "health_label_short": "<short>",
  "diagnosis": { "label", "short", "api_port_open", ... },
  "monitoring_only": <bool — connected but bracket/handoff incomplete>,
  "transport": { gateway_reachable, api_port_open, diagnosis, ... }
}
```

### B.9 GET /api/v7/playbook/ranked  (after `_finalize_ranked_response`)

```
{
  "count": <int>,
  "opportunities": [<row>, ...],
  "near_miss": [<row>, ...],
  "cached": <bool>,
  "stale": <bool>,
  "compressed": <bool — optional>,
  "source": "ranked_pipeline" | "brief_fallback" | ...,
  "board_mode": "full_live" | "<fallback modes>",
  "filter_funnel": {
    "execution_ready_setups", "deploy_qualified_setups", "watch_qualified_setups",
    "scan_ranked_count", ...
  },
  "avoid_grouped": { ... },
  "rejection_clusters": [...],
  "rejection_clusters_note": "<optional>",
  "signal_universe": { ... },
  "unlock_deploy": { tradeability, deployable_count, watch_qualified_count, ... },
  "best_action": { tradeability, execution_readiness, pilot_count, ... },
  "surface_authority": { ... },
  "restraint": { ... },
  "decision_authority": { ... },
  "score_reconciliation": { ... },
  "cc_state": <B.6>,
  "system_state": <B.3>,
  "page_capability": <B.4 tab=signals>,
  "rank_buckets": {
    "buckets": {
      "deployQualified", "pilotQualified", "watchQualified",
      "nearMiss", "rejectedAvoid"
    },
    "monitor_rows": [...],  // max ~12
    "monitor_section_label", "rejected_section_label",
    "has_valid_monitors", "counts": { ... }
  },
  "operator_board", "watch_queues", "watch_intelligence_summary",
  "ai_vibe", "board_posture", "paper_automation", "monitor_auto_actions",
  "auto_execution"
}
```

**Opportunity row** (core + ladder enrichment):

```
{
  "ticker", "action" | "effective_action", "score", "sector",
  "thesis_conf", "timing_conf", "vol_ratio", "leader", "risk_reward",
  "hard_reject", "execution_ready", "final_conf", "conflict_level",
  "ladder_bucket", "upgrade_gaps", "upgrade_proximity",
  "operator_action", "holder_guidance", "alert_trigger", "why_here",
  "upgrade_trigger", "operator_insight", "evidence_stack",
  "watch_intelligence", "monitor_state", "whats_missing"
}
```

### B.10 GET /api/v7/vibe-agent/status

```
{
  "mode": "running" | "paused" | "degraded" | "offline",
  "running": <bool>,
  "last_check": "<ISO>",
  "data_freshness": "FRESH" | "STALE" | "CRITICAL",
  "watch_scope": "<N> active rules",
  "alert_count": <int>,
  "authority_label": "Research / Monitoring only · 非部署權限",
  "authority_notice": ["...", ...],
  "operator_sentence": { "now", "blocker", "next_action" },
  "safety": <AgentSafetyContract — see /contract>
}
```

**GET /api/v7/vibe-agent/contract** → `agent_safety_contract()`:
`surface_type`, `authority_label`, `can_monitor`, `can_alert`, `can_create_watch_rules`,
`can_journal`, `can_suggest_confirmation_path`, `can_deploy=false`, `can_size=false`,
`can_handoff=false`, `can_override_dashboard=false`, `can_override_playbook=false`,
`authority_notice[]`.

### B.11 Research pipeline  (`/api/v7/research/*`)

**GET /contract** → `research_safety_contract(surface)`:
`surface_type`, `surface`, `authority_label`, `authority_sub`, `can_research`,
`can_monitor`, `can_validate`, `can_export`, `can_deploy=false`, `can_size=false`,
`can_handoff=false`, `can_override_dashboard=false`, `can_override_playbook=false`,
`authority_notice[]`, `pipeline_stops_at`: `"watch_rule_or_playbook_review"`.

**GET /pipeline/steps** → `{ "steps": [{ "id", "label" }, ...], "safety": { ... } }`
Steps: draft → validate → watch_rule → memory → committee (labels bilingual).

**POST /pipeline** → run result includes sanitized actions only
(`research_only`, `alert_only`, `validate_only`, etc.) — no sizing/order/ibkr keys.

### B.12 GET /api/v7/notify/status  (Discord)

```
{
  "discord_configured": <bool>,
  "webhook_set": <bool>,
  "bot_token_set": <bool>,
  "channel_id_set": <bool>,
  "channel_name": "<string>",
  "channel_cached": <bool>,
  "mode": "webhook" | "bot_channel" | "unconfigured",
  "notify_enabled": <bool>,
  "notify_research": <bool>,
  "last_alert_ts": "<optional ISO>",
  "last_alert_type": "<optional>",
  "setup_hint": "<when unconfigured>"
}
```

Env names only (no values): DISCORD_WEBHOOK_URL, DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID,
DISCORD_CHANNEL_NAME, DISCORD_NOTIFY_ENABLED, DISCORD_NOTIFY_RESEARCH,
DISCORD_ALERT_COOLDOWN_SEC.
"""


def _chatgpt_prompts_section() -> str:
    return """
---

## APPENDIX C — Suggested ChatGPT prompts (copy one after this briefing)

1. **Authority audit:** "Given the authority model in §2, review my planned feature [describe] and tell me which tab(s) it belongs on, what PageCapability flags it needs, and what gates must block it when tradeability is WAIT."

2. **Ops diagnostics:** "My Ops tab shows engine off and insufficient sample on advanced diagnostics. Using §6–7 and Appendix B.7, give me a step-by-step recovery checklist for Docker dev (`cc_api_dev`) including env vars and which `/health` / `/api/ops` endpoints to hit."

3. **i18n strategy:** "§9 says Chinese is incomplete. Propose a maintainable i18n plan for CC that doesn't break the 14k-line `index.html` tests — extend `cc-i18n.js`, server-side Ops strings, or locale JSON? Prioritize remaining English in degraded warmup copy outside Ops."

4. **Discord setup:** "I want reliable operator alerts without bot 403. Based on §6 and Appendix B.12, recommend webhook vs bot mode and exact `.env` keys for macOS Docker dev."

5. **Research vs deploy boundary:** "I'm building [Vibe Agent rule / Strategy Lab draft / Shadow analysis]. Confirm it cannot grant deploy authority, list API surfaces (Appendix B.10–B.11), and suggest UX copy for a Chinese-speaking operator."

6. **Architecture review:** "Review the stack in §1 and Appendix B. Map which services should stay synchronous vs async for ranked playbook under 2s p95 when engine is on. Flag circular imports between cc_state, playbook, and decision routers."

7. **Ops honesty model:** "Explain how `component_evidence` probe vs `runtime_evidence` should be presented so operators don't confuse disk-brief OK with engine health. Suggest UI copy and test cases for warmup → full transition."

8. **Performance:** "Dashboard polls cc-header, playbook ranked, and ops console. Using the file map in §8, propose a polling budget and cache strategy that keeps authority fields fresh without hammering yfinance."

9. **Testing plan:** "Design pytest coverage for SystemState/PageCapability across WAIT, NO_TRADE, and deploy_open with stale data and ENGINE_OFF. List fixtures needed from test_operator_state_contract.py patterns."

10. **IBKR MONITOR ladder:** "When `monitoring_only=true` but `connected=true`, what should Playbook and Portfolio show? Use Appendix B.8 and authority gates in §2 to propose operator-facing badges and blocked actions."
"""


def build_briefing_text() -> str:
    """Full plain-text briefing for HTML <pre> or export."""
    parts = [
        _load_consolidated_md().rstrip(),
        _branch_update_section().strip(),
        _result_structures_section().strip(),
        _chatgpt_prompts_section().strip(),
    ]
    return "\n\n".join(parts) + "\n"


def build_briefing_html() -> str:
    """Single-page HTML — Select All friendly, no Alpine."""
    body = html.escape(build_briefing_text())
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CC Advisor Briefing</title>
  <style>
    body {{
      font-family: ui-sans-serif, system-ui, sans-serif;
      max-width: 960px;
      margin: 1.5rem auto 3rem;
      padding: 0 1.25rem;
      background: #f8f9fa;
      color: #1a1a1a;
    }}
    h1 {{ font-size: 1.35rem; margin-bottom: 0.25rem; }}
    .hint {{
      font-size: 0.9rem;
      color: #555;
      margin-bottom: 1rem;
      padding: 0.6rem 0.75rem;
      background: #fff;
      border: 1px solid #ddd;
      border-radius: 6px;
    }}
    pre {{
      font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
      font-size: 12px;
      line-height: 1.45;
      white-space: pre-wrap;
      word-wrap: break-word;
      background: #fff;
      border: 1px solid #ccc;
      border-radius: 8px;
      padding: 1rem 1.1rem;
      margin: 0;
    }}
  </style>
</head>
<body>
  <h1>CC / TradingAI Bot — Advisor Briefing</h1>
  <p class="hint">
    <strong>Copy for ChatGPT:</strong> click inside the box below, then
    <strong>Cmd+A</strong> (Mac) or <strong>Ctrl+A</strong> (Windows/Linux) to select all,
    then copy. No secrets — environment variable names only.
    Served at <code>/briefing</code> and <code>/advisor-briefing</code>.
  </p>
  <pre>{body}</pre>
</body>
</html>"""
