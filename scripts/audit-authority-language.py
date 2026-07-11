#!/usr/bin/env python3
"""Scan CC templates and service payload copy for forbidden authority phrases."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]

# Phrase, default severity, suggested replacement
FORBIDDEN: Sequence[Tuple[str, str, str]] = (
    ("buy now", "critical", "monitor only · review dossier"),
    ("sell now", "critical", "monitor only · review dossier"),
    ("trade now", "critical", "monitor only · review Playbook"),
    ("deploy-ready", "critical", "research only · deploy authority unavailable"),
    ("deploy ready", "critical", "research only · deploy authority unavailable"),
    ("execution ready", "high", "execution diagnostic only"),
    ("high conviction deploy", "critical", "research evidence only"),
    ("capital candidate", "high", "research candidate · not permission"),
    ("live trade", "high", "closed-trade evidence · not permission"),
    ("route order", "critical", "IBKR handoff surface only when authorized"),
    ("position size", "high", "sizing blocked · review Portfolio"),
    ("handoff", "medium", "handoff (IBKR surface only when authorized)"),
    ("execute", "medium", "review only · no auto-execute"),
    ("deploy", "low", "context-dependent — verify surface authority"),
    ("size", "low", "context-dependent — verify sizing gate"),
    ("order", "low", "context-dependent — IBKR surface only"),
)

APPROVED_CONTEXTS = (
    "no sizing",
    "no handoff",
    "not deploy authority",
    "not deploy-ready",
    "not deploy ready",
    "deploy blocked",
    "deploy authority unavailable",
    "research only",
    "monitor only",
    "review only",
    "authority effect: none",
    "not trade authority",
    "no live changes",
    "no auto-loosen",
    "removeTradeLanguageWhenBlocked",
    "remove_sizing_language_when_blocked",
    "sanitize_blocked_candidate_copy",
    "LEGACY_BANNED_DO_NOT_RENDER",
    "Illustrative examples only",
    "whitelist",
    "banned phrase",
    "forbidden phrase",
    "audit-authority-language",
    "verify-surface-authority-contract",
    "SURFACE_AUTHORITY_CONTRACT",
    "OPERATOR_DECISION_OS",
    "ibkr/orderForm",
    "orderType",
    "border",
    "order ",
    "disorder",
    "/buy|enter|deploy|trade now",
    "test(cue)",
    "test(bestAction",
    "What to buy NOW",
    "Suggested position size (1R",
    "execution_readiness===",
    "Live trades",
    "live_trades_count",
    "Execution ready?",
    "deploy absent",
    "Avoid — not deploy",
    "Avoid — not deploy-ready",
    "not deploy-ready",
    "not deploy ready",
)

SURFACE_HINTS = (
    ("cc/partials/guide.html", "guide"),
    ("tab==='guide'", "guide"),
    ("tab==='today'", "dashboard"),
    ("data-cc=\"playbook-surface\"", "playbook"),
    ("data-cc=\"discovery-surface\"", "discovery"),
    ("tab==='dossier'", "dossier"),
    ("tab==='portfolio'", "portfolio"),
    ("tab==='funds'", "funds"),
    ("tab==='command'", "command"),
    ("tab==='stratlab'", "strategy_lab"),
    ("tab==='flow'", "flow"),
    ("tab==='rs'", "rs"),
    ("tab==='notrade'", "rejections"),
    ("tab==='ops'", "ops"),
    ("tab==='ibkr'", "ibkr"),
    ("tab==='btlab'", "backtest_lab"),
    ("replayModeActive()", "time_travel"),
)

SCAN_PATHS = (
    ROOT / "src/api/templates/index.html",
    ROOT / "src/api/templates/cc/partials",
    ROOT / "src/api/static/cc-helpers.js",
    ROOT / "docs/OPERATOR_DECISION_OS.md",
    ROOT / "docs/SURFACE_AUTHORITY_CONTRACT.md",
    ROOT / "src/services/today_payload_builder.py",
    ROOT / "src/services/opportunity_quality_engine.py",
    ROOT / "src/services/alpha_review_service.py",
    ROOT / "src/services/threshold_proposal_service.py",
    ROOT / "src/services/fetch_surface_state.py",
    ROOT / "src/services/operator_surface.py",
)


@dataclass
class Finding:
    file: str
    line: int
    phrase: str
    surface: str
    severity: str
    suggested_replacement: str
    excerpt: str


def iter_files() -> Iterable[Path]:
    for p in SCAN_PATHS:
        if p.is_dir():
            yield from sorted(p.rglob("*.html"))
        elif p.exists():
            yield p


def infer_surface(path: Path, line_text: str) -> str:
    rel = str(path.relative_to(ROOT))
    if "guide.html" in rel:
        return "guide"
    for marker, surface in SURFACE_HINTS:
        if marker in line_text or marker in rel:
            return surface
    if "cc-helpers" in rel:
        return "helpers"
    if path.suffix == ".py":
        return "service_payload"
    if rel.startswith("docs/"):
        return "docs"
    return "global"


def approved_context(line: str) -> bool:
    low = line.lower()
    return any(ctx.lower() in low for ctx in APPROVED_CONTEXTS)


def scan_file(path: Path) -> List[Finding]:
    findings: List[Finding] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return findings
    for i, line in enumerate(text.splitlines(), start=1):
        if approved_context(line):
            continue
        if re.search(r"\.test\s*\(|FORBIDDEN|forbidden phrase|banned phrase", line):
            continue
        low = line.lower()
        for phrase, severity, replacement in FORBIDDEN:
            if phrase not in low:
                continue
            if phrase in ("deploy", "size", "order", "execute", "handoff") and severity == "low":
                # Low-severity tokens are informational only — never fail release on them
                continue
            # Skip JS nullish coalescing and ternary-only lines
            if phrase == "size" and "??" in line:
                continue
            if phrase == "order" and re.search(r"order(Form|Type|_id|book)", line, re.I):
                continue
            if phrase == "deploy" and re.search(
                r"deploy_(blocked|authority|qualified)|no deploy|not deploy|deploy blocked|"
                r"deploy-authority|deploy authority unavailable|0 deploy",
                line,
                re.I,
            ):
                continue
            if phrase == "handoff" and re.search(
                r"no handoff|handoff blocked|not handoff|handoff surface|handoff readiness",
                line,
                re.I,
            ):
                continue
            if phrase == "execute" and re.search(
                r"executeQuery|execute\(|cannot execute|do not execute|no execute",
                line,
                re.I,
            ):
                continue
            if phrase == "size" and re.search(
                r"font-size|sample_size|page-size|resize|filesize|payload_size|"
                r"no sizing|half size|size shares|sizeShares",
                line,
                re.I,
            ):
                continue
            surf = infer_surface(path, line)
            if surf == "docs" and severity in ("low", "medium"):
                continue
            findings.append(
                Finding(
                    file=str(path.relative_to(ROOT)),
                    line=i,
                    phrase=phrase,
                    surface=surf,
                    severity=severity,
                    suggested_replacement=replacement,
                    excerpt=line.strip()[:160],
                )
            )
    return findings


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Authority language audit for Clarity Console")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    parser.add_argument("--fail-on", default="critical", choices=("critical", "high", "medium", "low", "never"))
    args = parser.parse_args(list(argv) if argv is not None else None)

    all_findings: List[Finding] = []
    for path in iter_files():
        all_findings.extend(scan_file(path))

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_findings.sort(key=lambda f: (order.get(f.severity, 9), f.file, f.line))

    if args.json:
        print(json.dumps([asdict(f) for f in all_findings], indent=2))
    else:
        print(f"Authority language audit — {len(all_findings)} finding(s)")
        for f in all_findings:
            print(
                f"{f.severity.upper():8} {f.file}:{f.line} [{f.surface}] "
                f'"{f.phrase}" → {f.suggested_replacement}'
            )
            print(f"         {f.excerpt}")

    fail_levels = {"critical": {"critical"}, "high": {"critical", "high"}, "medium": {"critical", "high", "medium"}}
    if args.fail_on != "never":
        bad = [f for f in all_findings if f.severity in fail_levels.get(args.fail_on, set())]
        if bad:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
