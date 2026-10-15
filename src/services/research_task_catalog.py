"""Vibe-Trading task → output capability matrix for CC X."""

from __future__ import annotations

from typing import Any, Dict, List

TASK_CATALOG: List[Dict[str, Any]] = [
    {
        "task": "ask_question",
        "label": "Ask a trading question",
        "outputs": [
            "Market research",
            "Tools + live data",
            "Session memory",
        ],
        "endpoint": "POST /api/v7/research/task",
        "status": "available",
    },
    {
        "task": "backtest_idea",
        "label": "Backtest a strategy idea",
        "outputs": [
            "Strategy draft + Pine export",
            "Metrics + run cards",
            "Validation lab artifacts",
        ],
        "endpoint": "POST /api/v7/research/task",
        "status": "available",
    },
    {
        "task": "review_trades",
        "label": "Review your own trades",
        "outputs": [
            "Broker journal parse",
            "Behavior diagnostics",
            "Shadow Account comparison",
        ],
        "endpoint": "POST /api/v7/research/task",
        "status": "available",
    },
    {
        "task": "read_documents",
        "label": "Read documents & charts",
        "outputs": ["PDF/DOCX/XLSX/PPTX/text", "Up to 5 files", "analyze_image (vision)"],
        "endpoint": "POST /api/v7/research/documents/read",
        "status": "partial",
        "note": "API + Strategy Lab upload (5 files); optional pypdf/docx/xlsx; OPENAI_VISION for charts.",
    },
    {
        "task": "institutional_intel",
        "label": "Institutional filings & fund books",
        "outputs": ["SEC 13F overlap", "Dossier sponsor intel", "ETF/universe context"],
        "endpoint": "GET /api/v7/research/institutional/intel",
        "status": "partial",
        "note": "13F QoQ manager diffs + OpenAlex + arXiv + Polymarket gamma (read-only) + ETF proxies.",
    },
    {
        "task": "improve_research",
        "label": "Improve repeated research",
        "outputs": ["Persistent memory", "Editable skills"],
        "endpoint": "GET/POST /api/v7/research/skills",
        "status": "available",
    },
    {
        "task": "analyst_teams",
        "label": "Run analyst teams",
        "outputs": ["Investment", "Quant", "Crypto", "Macro", "Risk"],
        "endpoint": "POST /api/v7/research/vibe/workspace",
        "status": "available",
    },
    {
        "task": "im_channels",
        "label": "IM channel runtime",
        "outputs": [
            "Discord",
            "Slack",
            "Telegram",
            "WhatsApp",
            "Matrix",
            "Teams",
            "Webhook",
            "ntfy",
            "WebSocket progress (all tasks)",
        ],
        "endpoint": "POST /api/v7/research/task?im_channel=discord · WS /api/v7/research/ws/session",
        "status": "available",
    },
    {
        "task": "ship_artifacts",
        "label": "Ship usable artifacts",
        "outputs": ["Reports", "Pine", "Signal sync MCP-style JSON"],
        "endpoint": "/api/v7/research/export/*",
        "status": "partial",
        "note": "Pine/TDX/MT5 stubs via backtest_idea; MCP tool catalog at /mcp/tools.",
    },
    {
        "task": "alpha_zoo",
        "label": "Bench alpha zoo",
        "outputs": ["IC + alive/reversed/dead", "478 manifest + nightly cache"],
        "endpoint": "POST /api/v7/research/alpha/bench-zoo · GET /alpha/bench-zoo/latest",
        "status": "available",
        "note": "Full zoo via compute_limit=478; nightly research_nightly_stub refreshes cache.",
    },
    {
        "task": "correlation_regime",
        "label": "Spot correlation regimes",
        "outputs": ["Edge-density timeline", "Hysteresis fused bloc"],
        "endpoint": "GET /api/v7/research/correlation/regime-timeline",
        "status": "available",
    },
]


def catalog_payload() -> Dict[str, Any]:
    return {
        "schema": "cc.research_task_catalog.v1",
        "tasks": TASK_CATALOG,
        "authority": "research_only",
    }
