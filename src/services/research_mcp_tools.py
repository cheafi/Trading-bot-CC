"""MCP-style tool descriptors for research session runtimes."""

from __future__ import annotations

from typing import Any, Dict, List

TOOL_DESCRIPTORS: List[Dict[str, Any]] = [
    {
        "name": "research_task",
        "description": "Run catalog task: ask_question, backtest_idea, review_trades, analyst_teams",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "prompt": {"type": "string"},
                "payload": {"type": "object"},
            },
            "required": ["task"],
        },
        "endpoint": "POST /api/v7/research/task",
    },
    {
        "name": "read_document",
        "description": "Parse uploaded document bytes (base64)",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "content_b64": {"type": "string"},
            },
            "required": ["filename", "content_b64"],
        },
        "endpoint": "POST /api/v7/research/documents/read",
    },
    {
        "name": "analyze_image",
        "description": "Vision read of chart screenshot",
        "endpoint": "POST /api/v7/research/documents/analyze-image",
    },
    {
        "name": "correlation_regime_timeline",
        "description": "Edge-density fused-bloc timeline (descriptive)",
        "endpoint": "GET /api/v7/research/correlation/regime-timeline",
    },
    {
        "name": "alpha_bench",
        "description": "IC categorization on alpha subset / zoo sample",
        "endpoint": "POST /api/v7/research/alpha/bench",
    },
    {
        "name": "alpha_bench_universe",
        "description": "Mean IC across Signal Board / custom ticker universe",
        "endpoint": "POST /api/v7/research/alpha/bench-universe",
    },
    {
        "name": "alpha_bench_zoo",
        "description": "478-alpha manifest IC sample (compute_limit capped)",
        "endpoint": "POST /api/v7/research/alpha/bench-zoo",
    },
    {
        "name": "alpha_manifest",
        "description": "Full 478-alpha zoo registry metadata",
        "endpoint": "GET /api/v7/research/alpha/manifest",
    },
    {
        "name": "institutional_intel",
        "description": "13F, ETF proxy constituents, OpenAlex factors",
        "endpoint": "GET /api/v7/research/institutional/intel",
    },
    {
        "name": "signals_sync_export",
        "description": "Paper signal envelope (no execution permission)",
        "endpoint": "GET /api/v7/research/signals/sync/export",
    },
]


def mcp_tool_catalog() -> Dict[str, Any]:
    return {
        "schema": "cc.mcp_tools.v1",
        "tools": TOOL_DESCRIPTORS,
        "authority": "research_only",
        "execution_permission": False,
    }
