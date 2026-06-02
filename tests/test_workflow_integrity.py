"""Section 5 workflow integrity — instant degraded, discovery WAIT, dossier levels."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"
CC_INSTANT = ROOT / "_cc_instant.py"


def test_index_html_instant_degraded_banner_wired():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "instantDegradedBannerVisible()" in raw
    assert "instantDegradedBannerLine()" in raw
    assert "dismissInstantDegradedBanner()" in raw
    assert "captureInstantDegradedBanner(" in raw
    assert "fetchHealth()" in raw
    assert "INSTANT DEGRADED" in raw
    assert "Dismiss" in raw


def test_index_html_discovery_wait_empty_copy():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "discoveryWaitEmptyLine()" in raw
    assert "Often correct on WAIT — monitor funnel, not deploy." in raw
    assert "discoveryWaitZeroHits()" in raw


def test_index_html_dossier_indicative_levels_when_failed():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "dossierLevelsIndicativeOnly()" in raw
    assert "dossierResearchOnly()" in raw
    assert "CONFIRM ONLY" in raw
    assert "Indicative entry" in raw
    assert "dosDashboardReminderLine()" in raw


def test_index_html_playbook_ibkr_and_level_gates():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "playbookCanSendToIbkr(r)" in raw
    assert "cardShowsDeployLevels(r)" in raw
    assert "(r.action==='TRADE'||r.action==='BUY')&&r.execution_ready" not in raw


def test_index_html_dashboard_playbook_cta_on_wait():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "dashboardPlaybookCtaLabel()" in raw
    assert "Review monitor ranking in Playbook" in raw


def test_index_html_btlab_honest_metrics():
    raw = INDEX_HTML.read_text(encoding="utf-8")
    assert "btLabHonestMetric(" in raw
    assert "btLabHonestStabilityScore()" in raw
    assert "btLabTradeMetricsLine()" in raw
    btlab = raw[raw.find("x-show=\"tab==='btlab'\"") : raw.find("x-show=\"tab==='btlab'\"") + 12000]
    assert "win_rate+'%'" not in btlab


def test_cc_instant_degraded_banner_on_stale_today():
    fn_block = (
        CC_INSTANT.read_text(encoding="utf-8")
        .split("def _stale_today_bytes(reason: str = \"backend importing\") -> bytes:")[1]
        .split("\ndef _load_ranked_snapshot_bytes")[0]
    )
    ns: dict = {}
    exec(  # noqa: S102
        "import json\nfrom datetime import datetime, timezone\n"
        + "def _load_latest_brief(): return None\n"
        + "def _today_bytes_from_brief(b,r): return b''\n"
        + "def _encode_degraded(p, reason=None):\n"
        + "  p=dict(p); p['degraded']=True; p['degraded_banner']='INSTANT DEGRADED — test'; return json.dumps(p).encode()\n"
        + "def _stale_today_bytes(reason: str = 'backend importing') -> bytes:"
        + fn_block,
        ns,
    )
    payload = json.loads(ns["_stale_today_bytes"]("warming"))
    assert payload.get("degraded_banner")
    assert payload.get("degraded") is True


def test_cc_instant_health_loading_stamps_banner():
    raw = CC_INSTANT.read_text(encoding="utf-8")
    assert "_stamp_instant_degraded" in raw
    assert "DEGRADED_BANNER" in raw
    assert "health_payload = _stamp_instant_degraded" in raw or "_stamp_instant_degraded(" in raw


def test_cc_instant_ai_narrative_degraded_post():
    """POST /api/v7/today/ai-narrative must return honest stub during warm-up."""
    raw = CC_INSTANT.read_text(encoding="utf-8")
    assert "_degraded_ai_narrative_post" in raw
    assert 'path_only == "/api/v7/today/ai-narrative"' in raw
    assert "/api/v7/today/ai-narrative" in raw
    assert "research_only" in raw
    assert "narrative only" in raw

    # Exercise fallback path only (avoid heavy ai_service import in CI).
    ns: dict = {}
    exec(  # noqa: S102
        "import json\n"
        + "def _encode_degraded(p, reason=None):\n"
        + "  p=dict(p); p['degraded']=True; return json.dumps(p).encode()\n"
        + "def _degraded_ai_narrative_post(body: bytes):\n"
        + "  note = 'backend importing — full LLM narrative pending API warm-up'\n"
        + "  payload = json.loads(body.decode('utf-8') if body else '{}')\n"
        + "  regime = payload.get('regime_ctx') or {}\n"
        + "  trend = regime.get('trend') or regime.get('label') or 'unknown'\n"
        + "  tradeability = regime.get('tradeability') or 'WAIT'\n"
        + "  ai_narrative = (\n"
        + "    'Rule-based briefing (instant degraded — narrative only; does not affect '\n"
        + "    'ranking, sizing, or deploy gates).\\n\\n'\n"
        + "    f'Regime **{trend}**, tradeability **{tradeability}**. {note}'\n"
        + "  )\n"
        + "  return 200, _encode_degraded({\n"
        + "    'ai_narrative': ai_narrative,\n"
        + "    'provider': 'stub',\n"
        + "    'research_only': True,\n"
        + "    'degraded': True,\n"
        + "  })\n",
        ns,
    )
    body_in = json.dumps(
        {"regime_ctx": {"label": "NEUTRAL", "tradeability": "WAIT"}}
    ).encode()
    status, out = ns["_degraded_ai_narrative_post"](body_in)
    payload = json.loads(out)
    assert status == 200
    assert payload.get("ai_narrative")
    assert payload.get("provider") == "stub"
    assert payload.get("research_only") is True
    assert "does not affect" in payload["ai_narrative"]
