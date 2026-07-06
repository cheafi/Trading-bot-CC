#!/usr/bin/env python3
"""Repair mojibake and apply Chinese clarity patches to index.html."""
from __future__ import annotations

from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "src/api/templates/index.html"

FIXES: list[tuple[str, str]] = [
    (
        '<div class="font-bold uppercase mb-1" style="color:var(--t3)">?? ? Now</div>',
        '<div class="font-bold uppercase mb-1" style="color:var(--t3)">現在 · Now</div>',
    ),
    (
        '<div class="font-bold uppercase mb-1" style="color:var(--t3)">?? ? Why</div>',
        '<div class="font-bold uppercase mb-1" style="color:var(--t3)">原因 · Why</div>',
    ),
    (
        '<div class="font-bold uppercase mb-1" style="color:var(--green)">?? ? Allowed</div>',
        '<div class="font-bold uppercase mb-1" style="color:var(--green)">允許 · Allowed</div>',
    ),
    (
        '<div class="font-bold uppercase mb-1" style="color:var(--red)">?? ? Blocked</div>',
        '<div class="font-bold uppercase mb-1" style="color:var(--red)">禁止 · Blocked</div>',
    ),
    (
        '<div class="font-bold uppercase mb-1" style="color:var(--amber)">???? ? Missing</div>',
        '<div class="font-bold uppercase mb-1" style="color:var(--amber)">缺少內容 · Missing</div>',
    ),
    (
        '<span class="font-bold uppercase" style="color:var(--blue)">??? ? Next</span> ?',
        '<span class="font-bold uppercase" style="color:var(--blue)">下一步 · Next</span> ·',
    ),
    (
        "(dossierOperatorBlock().allowed||[]).join(' ? ')",
        "(dossierOperatorBlock().allowed||[]).join(' · ')",
    ),
    (
        "(dossierOperatorBlock().blocked||[]).join(' ? ')",
        "(dossierOperatorBlock().blocked||[]).join(' · ')",
    ),
    (
        "return 'Confirm-only ? ?????????????????? ? no sizing ? no handoff';",
        "return 'Confirm-only · 僅結構確認：無入場價、無止損、無倉位 · no sizing · no handoff';",
    ),
    (
        "return 'Structure snapshot ? ????';",
        "return 'Structure snapshot · 結構快照';",
    ),
    (
        "if(field==='entry') return 'Reference level ? ????';",
        "if(field==='entry') return 'Reference level · 參考價位';",
    ),
    (
        "if(field==='stop') return 'Risk reference ? ????';",
        "if(field==='stop') return 'Risk reference · 風險參考';",
    ),
    (
        "return 'Paper draft disabled ? ??????? ? ? live Dossier + Playbook ???????';",
        "return 'Paper draft disabled · 紙上模擬已關閉 — 需 live Dossier + Playbook 確認後才可模擬';",
    ),
    (
        "return 'Create monitor rule ? ??????';",
        "return 'Create monitor rule · 建立監察規則';",
    ),
    (
        "return 'Alert only ? ??? ? ????????? ? no sizing ? no handoff';",
        "return 'Alert only · 僅提醒 — 不定倉、不交接券商 · no sizing · no handoff';",
    ),
    (
        "return 'Lagged / illustrative context ? ???????????? ? not used for confirmation';",
        "return 'Lagged / illustrative context · 滯後參考，不用於結構確認 · not used for confirmation';",
    ),
    (
        "if(field==='target') return 'Upside references ? ????';",
        "if(field==='target') return 'Upside references · 上行參考';",
    ),
    (
        '<div class="text-[9px] font-bold uppercase mb-2" style="color:var(--blue)">A ? Core index posture</div>',
        '<div class="text-[9px] font-bold uppercase mb-2" style="color:var(--blue)">A · Core index posture</div>',
    ),
    (
        '<span class="text-[9px] font-bold uppercase" style="color:var(--t3)">B ? Sleeve research (secondary)</span>',
        '<span class="text-[9px] font-bold uppercase" style="color:var(--t3)">B · Sleeve research (secondary)</span>',
    ),
    (
        '<span x-show="playbookUsesBriefFallback()" class="text-amber-400">?? Brief fallback ? confidence is estimated, not calibrated</span>',
        '<span x-show="playbookBriefExpired()" class="text-amber-400" x-text="playbookBriefExpiredLine()"></span>',
    ),
    (
        "if(this.playbookUsesBriefFallback()) parts.push('Brief fallback board ? uncalibrated ranks.');",
        "if(this.playbookBriefExpired()) parts.push(this.playbookBriefExpiredLine()+' — excluded from ranking.');",
    ),
    (
        "if(m==='compressed_fallback'||this.playbookUsesBriefFallback()) return 'Fallback board';",
        "if(this.playbookBriefExpired()) return this.playbookBriefExpiredLine(); if(m==='compressed_fallback'||this.playbookUsesBriefFallback()) return 'Brief sample board';",
    ),
    (
        "return 'Uncalibrated fallback ? rank ? deploy permission';",
        "return 'Brief expired — rank is monitor context only';",
    ),
    (
        "(playbookOperatorView().next||[]).join(' ? ')",
        "(playbookOperatorView().next||[]).join(' · ')",
    ),
]

PATCHES: list[tuple[str, str]] = [
    (
        ':title="unifiedTruthStripLine()"\n                  x-text="unifiedTruthStripLine()"></span>',
        ':title="(typeof CCHelpers!==\'undefined\'&&CCHelpers.localizeScopedFreshnessStrip)?CCHelpers.localizeScopedFreshnessStrip(unifiedTruthStripLine()):unifiedTruthStripLine()"\n                  x-text="(typeof CCHelpers!==\'undefined\'&&CCHelpers.scopedFreshnessStripLocalized&&today7.system_truth)?CCHelpers.scopedFreshnessStripLocalized(today7.system_truth):(typeof CCHelpers!==\'undefined\'&&CCHelpers.localizeScopedFreshnessStrip)?CCHelpers.localizeScopedFreshnessStrip(unifiedTruthStripLine()):unifiedTruthStripLine()"></span>',
    ),
    (
        "x-text=\"'Board stance '+(isWaitDay()?'WAIT':'MONITOR')\"",
        "x-text=\"'看板姿態 '+(isWaitDay()?'WAIT · 等待':'MONITOR · 僅監察')+' · Board stance '+(isWaitDay()?'WAIT':'MONITOR')\"",
    ),
]


def main() -> None:
    raw = INDEX.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    n = 0
    for old, new in FIXES + PATCHES:
        if old in text:
            text = text.replace(old, new)
            n += 1
    INDEX.write_text(text, encoding="utf-8")
    text.encode("utf-8")
    print(f"fixed {n} blocks")


if __name__ == "__main__":
    main()
