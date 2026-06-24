"""Multi-agent research committee — support decisions, never grant authority."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.research_safety import sanitize_research_payload


_AGENTS = (
    ("quant_reviewer", "Quant reviewer · 量化審閱"),
    ("risk_manager", "Risk manager · 風控"),
    ("regime_analyst", "Regime analyst · 市況"),
    ("technical_analyst", "Technical setup · 技術面"),
    ("portfolio_manager", "Portfolio manager · 組合"),
    ("skeptic", "Skeptic / bear case · 反方"),
    ("execution_checker", "Execution readiness · 執行準備"),
)


def run_committee_review(
    *,
    subject: Dict[str, Any],
    system_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ss = system_state or {}
    tb = str(ss.get("tradeability") or "WAIT").upper()
    data_tier = str(ss.get("data_freshness") or "FRESH")
    deploy_blocked = tb in ("WAIT", "NO_TRADE") or not ss.get("deploy_open")

    agents_out: List[Dict[str, Any]] = []
    for agent_id, label in _AGENTS:
        stance, evidence, missing, risk = _agent_opinion(
            agent_id, subject=subject, tradeability=tb, data_tier=data_tier
        )
        agents_out.append(
            {
                "id": agent_id,
                "label": label,
                "stance": stance,
                "evidence": evidence,
                "missingData": missing,
                "risk": risk,
                "confirmationPath": "Playbook → Dossier → Dashboard",
            }
        )

    support = len([a for a in agents_out if a["stance"] == "support"])
    contradict = len([a for a in agents_out if a["stance"] == "contradiction"])
    consensus = "neutral"
    if support >= 5 and not deploy_blocked:
        consensus = "research_favorable"
    elif contradict >= 3:
        consensus = "research_unfavorable"
    elif deploy_blocked:
        consensus = "monitor_only"

    disagreement = [a for a in agents_out if a["stance"] == "contradiction"]
    must_improve = []
    if data_tier in ("STALE", "CRITICAL"):
        must_improve.append("Repair data freshness before actionable research")
    if deploy_blocked:
        must_improve.append(f"Board gate {tb} — open Playbook for watch-qualified only")
    if contradict:
        must_improve.extend([a["risk"] for a in disagreement[:2]])

    open_playbook = support >= 4 and not deploy_blocked
    open_dossier = support >= 3

    return sanitize_research_payload(
        {
            "agents": agents_out,
            "researchConsensus": consensus,
            "disagreementMap": {a["id"]: a["stance"] for a in agents_out},
            "mustImprove": must_improve,
            "openPlaybook": open_playbook,
            "openDossier": open_dossier,
            "summaryZh": _summary_zh(consensus, deploy_blocked, support, contradict),
            "summaryEn": f"Committee: {consensus}; support={support} contradiction={contradict}",
            "authority_notice": [
                "Investment committee supports research only",
                "Cannot grant deploy authority",
            ],
        }
    )


def _agent_opinion(
    agent_id: str,
    *,
    subject: Dict[str, Any],
    tradeability: str,
    data_tier: str,
) -> tuple:
    hypothesis = str(subject.get("hypothesis") or subject.get("rawPrompt") or "")
    has_rules = bool(subject.get("entryRules") or subject.get("entry_rules"))
    stale = data_tier in ("STALE", "CRITICAL")
    wait = tradeability in ("WAIT", "NO_TRADE")

    if agent_id == "quant_reviewer":
        stance = "support" if has_rules else "neutral"
        return stance, ["Structured entry/exit rules present"] if has_rules else [], ["Backtest metrics"], "Overfit if untested"
    if agent_id == "risk_manager":
        stance = "contradiction" if wait else "neutral"
        return stance, [f"Board {tradeability}"], ["Portfolio heat"], "Size only after gates"
    if agent_id == "regime_analyst":
        stance = "contradiction" if wait else "support"
        return stance, [f"Regime {tradeability}"], ["Sector breadth"], "Regime drift risk"
    if agent_id == "technical_analyst":
        return "support" if has_rules else "neutral", ["Setup rules defined"], ["Live price structure"], "Extended chase risk"
    if agent_id == "portfolio_manager":
        return "neutral", ["Universe scoped"], ["Correlation cluster"], "Concentration"
    if agent_id == "skeptic":
        return "contradiction" if not hypothesis else "neutral", ["Bear case: unvalidated draft"], ["Forward sample"], "Narrative risk"
    if agent_id == "execution_checker":
        stance = "contradiction" if stale or wait else "neutral"
        return stance, ["No handoff from research"], ["Broker session"], "Execution blocked"
    return "neutral", [], [], ""


def _summary_zh(consensus: str, deploy_blocked: bool, support: int, contradict: int) -> str:
    if deploy_blocked:
        return f"委員會結論：只可監察（support {support} / contradiction {contradict}）· 需 Playbook 確認"
    if consensus == "research_favorable":
        return f"研究偏向正面（{support}/7）· 仍須 Playbook + Dashboard 閘門"
    return f"研究中性／分歧（support {support}）· 先驗證再開 Playbook"
