"""AI advisory suggestions for Futu-captured portfolios — ADVISORY ONLY."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ADVISORY_DISCLAIMER_EN = (
    "ADVISORY ONLY — not a trade instruction. "
    "Human approval required before any action. CC deploy authority unchanged."
)
ADVISORY_DISCLAIMER_ZH = "僅供參考 — 非交易指令。任何操作須人工確認，CC 部署權限不變。"


def _concentration_warnings(
    items: List[Dict[str, Any]], total_value: float
) -> List[str]:
    warnings: List[str] = []
    if total_value <= 0:
        return warnings
    for item in items:
        mv = float(item.get("market_value") or 0)
        if mv <= 0:
            continue
        w = (mv / total_value) * 100
        item["portfolio_weight_pct"] = round(w, 1)
        if w > 25:
            warnings.append(f"{item['ticker']} is {w:.0f}% — over-concentrated")
    return warnings


def _rule_action(pnl_pct: float, verdict: str) -> tuple[str, str]:
    if verdict == "STRONG_BUY":
        return "HOLD / ADD on dip", "Expert committee strongly bullish"
    if verdict == "BUY":
        return "HOLD", "Committee bullish"
    if verdict in ("SELL", "STRONG_SELL"):
        return "TRIM / REVIEW", "Committee bearish — review thesis"
    if pnl_pct < -15:
        return "REVIEW", f"Down {pnl_pct:.1f}% — check stop/thesis"
    if pnl_pct > 50:
        return "CONSIDER TRIM", f"Up {pnl_pct:.1f}% — take partial profits"
    return "HOLD", "Neutral — monitor"


async def build_futu_advisory(
    holdings: List[Dict[str, Any]],
    *,
    market_data: Any,
    regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build per-ticker advice + bilingual LLM summary. Never triggers trades."""
    import numpy as np

    from src.engines.expert_committee import ExpertCommittee
    from src.services.ai_service import get_ai_service
    from src.services.indicators import compute_indicators as _compute_indicators

    advice_items: List[Dict[str, Any]] = []
    total_value = 0.0
    total_pnl = 0.0

    for h in holdings:
        ticker = h["ticker"]
        mv = float(h.get("market_value") or 0)
        total_value += mv
        total_pnl += float(h.get("unrealized_pnl") or 0)
        verdict_str = "N/A"
        confidence = 0.0
        try:
            hist = await market_data.get_history(ticker, period="6mo", interval="1d")
            if hist is not None and not hist.empty:
                c_col = "Close" if "Close" in hist.columns else "close"
                close = hist[c_col].values.astype(float)
                v_col = "Volume" if "Volume" in hist.columns else "volume"
                volume = (
                    hist[v_col].values.astype(float)
                    if v_col in hist.columns
                    else np.ones(len(close))
                )
                ec = ExpertCommittee()
                ind = _compute_indicators(close, volume)
                i = len(close) - 1
                trending = bool(
                    close[i] > ind["sma50"][i] and ind["sma50"][i] > ind["sma200"][i]
                )
                votes = ec.collect_votes(
                    regime="UPTREND" if trending else "SIDEWAYS",
                    rsi=float(ind["rsi"][i]),
                    vol_ratio=float(ind["vol_ratio"][i]),
                    trending=trending,
                    rr_ratio=2.0,
                    atr_pct=float(ind["atr_pct"][i]),
                )
                v = ec.deliberate(votes, regime="UPTREND" if trending else "SIDEWAYS")
                verdict_str = v.direction
                confidence = v.agreement_ratio
        except Exception as exc:
            logger.debug("advisory skip %s: %s", ticker, exc)

        pnl_pct = float(h.get("pnl_pct") or 0)
        action, reason = _rule_action(pnl_pct, verdict_str)
        advice_items.append(
            {
                "ticker": ticker,
                "shares": h.get("shares"),
                "avg_cost": h.get("avg_cost"),
                "market_value": mv,
                "pnl_pct": pnl_pct,
                "committee_verdict": verdict_str,
                "committee_confidence": confidence,
                "action": action,
                "reason": reason,
            }
        )

    concentration_warnings = _concentration_warnings(advice_items, total_value)

    regime = regime or {}
    summary_en = ""
    summary_zh = ""
    ai = get_ai_service()
    if ai.is_configured and advice_items:
        holdings_blob = json.dumps(advice_items[:15], default=str)[:2000]
        prompt = (
            f"Futu portfolio capture advisory (DO NOT recommend auto-trading).\n"
            f"Regime: {regime.get('label', regime.get('trend', 'unknown'))}\n"
            f"Holdings advice JSON:\n{holdings_blob}\n"
            f"Concentration warnings: {concentration_warnings or 'none'}\n"
            "Return JSON: summary_en (2 short paragraphs), summary_zh (繁中 mirror), "
            "top_actions (array of {ticker, action, rationale_en, rationale_zh})."
        )
        llm = await ai.generate_json(
            system=(
                "You are CC PM Advisor. ADVISORY ONLY — never instruct auto-deploy. "
                "Bilingual 繁中·English. Be specific on concentration and trim/add ideas."
            ),
            user_prompt=prompt,
            max_tokens=900,
        )
        if llm:
            summary_en = str(llm.get("summary_en") or "")
            summary_zh = str(llm.get("summary_zh") or "")

    if not summary_en:
        trim = [a for a in advice_items if "TRIM" in a["action"]]
        summary_en = (
            f"Parsed {len(holdings)} Futu positions. "
            f"{len(trim)} names flagged for trim/review. "
            f"{ADVISORY_DISCLAIMER_EN}"
        )
        summary_zh = (
            f"已解析 {len(holdings)} 個富途持倉。"
            f"{len(trim)} 檔建議減倉/複查。{ADVISORY_DISCLAIMER_ZH}"
        )

    return {
        "advisory_only": True,
        "disclaimer_en": ADVISORY_DISCLAIMER_EN,
        "disclaimer_zh": ADVISORY_DISCLAIMER_ZH,
        "portfolio_summary": {
            "total_value": round(total_value, 2),
            "total_pnl": round(total_pnl, 2),
            "holdings_count": len(holdings),
        },
        "advice": advice_items,
        "concentration_warnings": concentration_warnings,
        "summary_en": summary_en,
        "summary_zh": summary_zh,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
