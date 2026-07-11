#!/usr/bin/env python3
"""Detect visible copy corruption: ??, mojibake, broken emoji, double spaces in badges."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]

SCAN_GLOBS = (
    "src/api/templates/index.html",
    "src/api/templates/cc/partials/*.html",
    "src/api/static/cc-helpers.js",
    "docs/OPERATOR_DECISION_OS.md",
    "docs/SURFACE_AUTHORITY_CONTRACT.md",
    "docs/INTELLIGENCE_STACK.md",
    "docs/RELEASE_CHECKLIST.md",
    "src/services/opportunity_quality_engine.py",
    "src/services/threshold_proposal_service.py",
    "src/services/fetch_surface_state.py",
)

# UI-facing corruption patterns (exclude JS ?? nullish coalescing in expressions)
CORRUPT_PATTERNS: Sequence[tuple[str, str, str]] = (
    (r"(?<![?])\?\?(?![?=])", "critical", "literal ?? in visible copy"),
    (r"\ufffd", "critical", "Unicode replacement character"),
    (r"Ã[\x80-\xBF]", "critical", "UTF-8 mojibake sequence"),
    (r"â[\x80-\xbf]", "high", "UTF-8 mojibake (arrow/emoji)"),
    (r"'Dashboard \? Playbook", "critical", "corrupted arrow in workflow copy"),
    (r"x-text=\"'\? ", "high", "corrupted UI prefix (should be icon/bullet)"),
    (r">\? Ops Console", "high", "corrupted Ops header emoji"),
    (r"Strategy Lab \? research", "medium", "corrupted em dash"),
    (r"More \? Strategy Lab", "medium", "corrupted navigation arrow"),
    (r"2\?45\+", "medium", "corrupted range dash"),
    (r"'\? '\+", "high", "corrupted list prefix in Alpine binding"),
    (r"export is monitor-only \? not", "high", "corrupted em dash in export copy"),
    (r"Stock .+\? SPY .+\? \? ", "high", "corrupted comparison separators"),
    (r'pill[^>]*>\s*</span>', "medium", "empty pill element"),
    (r'class="pill[^"]*"\s+x-text=""', "medium", "empty pill binding"),
    (r"\?\?today7", "critical", "broken Alpine nullish (space in ??)"),
    (r"  +·", "low", "double space before middle dot in badge"),
    (r"[!?]{3,}", "medium", "repeated punctuation cluster"),
)

JS_NULLISH_OK = re.compile(
    r"\?\?|\?\s*:\s*|'\?'|\?\s*Failed|\?\s*'\)|mode\|\|'\?'|sig\.mode\|\|'\?'"
)


@dataclass
class CopyFinding:
    file: str
    line: int
    pattern: str
    severity: str
    detail: str
    excerpt: str


def iter_files() -> Iterable[Path]:
    for pattern in SCAN_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if path.is_file():
                yield path


def line_is_js_nullish_only(line: str) -> bool:
    if "??" not in line:
        return False
    stripped = line.strip()
    if JS_NULLISH_OK.search(stripped):
        return True
    if re.search(r"\w+\?\?\w+", stripped) and "x-text" not in stripped and "x-show" not in stripped:
        return True
    return False


def scan_file(path: Path) -> List[CopyFinding]:
    findings: List[CopyFinding] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return findings
    rel = str(path.relative_to(ROOT))
    for i, line in enumerate(lines, start=1):
        if line_is_js_nullish_only(line):
            continue
        for regex, severity, detail in CORRUPT_PATTERNS:
            if re.search(regex, line):
                findings.append(
                    CopyFinding(
                        file=rel,
                        line=i,
                        pattern=regex,
                        severity=severity,
                        detail=detail,
                        excerpt=line.strip()[:160],
                    )
                )
                break
    return findings


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Visible copy corruption audit")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on", default="high", choices=("critical", "high", "medium", "low", "never"))
    args = parser.parse_args(list(argv) if argv is not None else None)

    findings: List[CopyFinding] = []
    for path in iter_files():
        findings.extend(scan_file(path))

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: (order.get(f.severity, 9), f.file, f.line))

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        print(f"Visible copy audit — {len(findings)} finding(s)")
        for f in findings:
            print(f"{f.severity.upper():8} {f.file}:{f.line} — {f.detail}")
            print(f"         {f.excerpt}")

    fail_levels = {
        "critical": {"critical"},
        "high": {"critical", "high"},
        "medium": {"critical", "high", "medium"},
    }
    if args.fail_on != "never":
        bad = [f for f in findings if f.severity in fail_levels.get(args.fail_on, set())]
        if bad:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
