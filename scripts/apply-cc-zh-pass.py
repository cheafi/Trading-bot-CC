#!/usr/bin/env python3
"""UTF-8 safe CC Chinese clarity pass for index.html."""
from __future__ import annotations

import re
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "src/api/templates/index.html"
ROOT = INDEX.parents[3]


def _import_dossier_constants() -> dict[str, str]:
    import sys

    sys.path.insert(0, str(ROOT))
    from src.services.dossier_mode import (  # noqa: PLC0415
        DOSSIER_CONFIRM_ONLY_STRIP,
        LAGGED_CONTEXT_COLLAPSED_NOTE,
        MONITOR_RULE_BUTTON,
        MONITOR_RULE_HINT,
        PAPER_DRAFT_DISABLED_COPY,
        STRUCTURE_SNAPSHOT_TITLE,
        structure_level_label,
    )

    return {
        "confirm_strip": DOSSIER_CONFIRM_ONLY_STRIP,
        "paper_draft": PAPER_DRAFT_DISABLED_COPY,
        "structure_title": STRUCTURE_SNAPSHOT_TITLE,
        "monitor_button": MONITOR_RULE_BUTTON,
        "monitor_hint": MONITOR_RULE_HINT,
        "lagged_note": LAGGED_CONTEXT_COLLAPSED_NOTE,
        "entry_label": structure_level_label("entry", mode="structure_review_only"),
        "stop_label": structure_level_label("stop", mode="structure_review_only"),
        "target_label": structure_level_label("target", mode="structure_review_only"),
    }


def main() -> None:
    text = INDEX.read_text(encoding="utf-8")
    n = 0
    dossier = _import_dossier_constants()

    def sub(old: str, new: str, label: str = "") -> None:
        nonlocal text, n
        if old not in text:
            print("skip:", label or old[:50])
            return
        text = text.replace(old, new, 1)
        n += 1
        print("ok:", label or old[:50])

    # Dossier JS fallbacks (mojibake uses U+FFFD or ? instead of ·)
    dossier_js = [
        (r"return 'Confirm-only[^']*no handoff';", f"return '{dossier['confirm_strip']}';", "dossier confirm strip js"),
        (r"return 'Structure snapshot[^']*';", f"return '{dossier['structure_title']}';", "dossier structure title js"),
        (r"if\(field==='entry'\) return 'Reference level[^']*';", f"if(field==='entry') return '{dossier['entry_label']}';", "dossier entry js"),
        (r"if\(field==='stop'\) return 'Risk reference[^']*';", f"if(field==='stop') return '{dossier['stop_label']}';", "dossier stop js"),
        (r"if\(field==='target'\) return 'Upside references[^']*';", f"if(field==='target') return '{dossier['target_label']}';", "dossier target js"),
        (r"return 'Paper draft disabled[^']*';", f"return '{dossier['paper_draft']}';", "dossier paper draft js"),
        (r"return 'Create monitor rule[^']*';", f"return '{dossier['monitor_button']}';", "dossier monitor button js"),
        (r"return 'Alert only[^']*no handoff';", f"return '{dossier['monitor_hint']}';", "dossier monitor hint js"),
        (r"return 'Lagged / illustrative context[^']*';", f"return '{dossier['lagged_note']}';", "dossier lagged js"),
    ]
    for pattern, repl, label in dossier_js:
        if re.search(pattern, text):
            text = re.sub(pattern, repl, text, count=1)
            n += 1
            print("ok:", label)
        else:
            print("skip:", label)

    # Dossier confirm-only HTML block labels
    dossier_html = [
        (r'<div class="font-bold uppercase mb-1" style="color:var\(--t3\)">[^<]*Why</div>', '<div class="font-bold uppercase mb-1" style="color:var(--t3)">原因 · Why</div>', "dossier why html"),
        (r'<div class="font-bold uppercase mb-1" style="color:var\(--green\)">[^<]*Allowed</div>', '<div class="font-bold uppercase mb-1" style="color:var(--green)">允許 · Allowed</div>', "dossier allowed html"),
        (r'<div class="font-bold uppercase mb-1" style="color:var\(--red\)">[^<]*Blocked</div>', '<div class="font-bold uppercase mb-1" style="color:var(--red)">禁止 · Blocked</div>', "dossier blocked html"),
        (r'<div class="font-bold uppercase mb-1" style="color:var\(--amber\)">[^<]*Missing</div>', '<div class="font-bold uppercase mb-1" style="color:var(--amber)">缺少內容 · Missing</div>', "dossier missing html"),
        (r'<span class="font-bold uppercase" style="color:var\(--blue\)">[^<]*Next</span>', '<span class="font-bold uppercase" style="color:var(--blue)">下一步 · Next</span>', "dossier next html"),
        (r"\(dossierOperatorBlock\(\)\.allowed\|\|\[\]\)\.join\('[^']*'\)", "(dossierOperatorBlock().allowed||[]).join(' · ')", "dossier allowed join"),
        (r"\(dossierOperatorBlock\(\)\.blocked\|\|\[\]\)\.join\('[^']*'\)", "(dossierOperatorBlock().blocked||[]).join(' · ')", "dossier blocked join"),
        (r"return CCHelpers\.dossierMissingDataLabels\(missing\)\.join\('[^']*'\)", "return CCHelpers.dossierMissingDataLabels(missing).join(' · ')", "dossier missing join"),
        (r"return missing\.join\('[^']*'\)", "return missing.join(' · ')", "dossier missing join raw"),
    ]
    for pattern, repl, label in dossier_html:
        new_text, count = re.subn(pattern, repl, text, count=1)
        if count:
            text = new_text
            n += count
            print("ok:", label)
        else:
            print("skip:", label)

    # Repair pre-existing mojibake in dossier fallbacks / labels
    # Dashboard operator block labels (same glossary as dossier)
    dash_ops = [
        ('<span class="font-bold uppercase mr-1" style="color:var(--blue)">?? ? Now</span>', '<span class="font-bold uppercase mr-1" style="color:var(--blue)">現在 · Now</span>', "dashboard now"),
        ('<span class="font-bold uppercase mr-1" style="color:var(--amber)">?? ? Why</span>', '<span class="font-bold uppercase mr-1" style="color:var(--amber)">原因 · Why</span>', "dashboard why"),
        ('<span class="font-bold uppercase mr-1" style="color:var(--green)">可做 · Allowed</span>', '<span class="font-bold uppercase mr-1" style="color:var(--green)">可做 · Allowed</span>', "dashboard allowed"),
        ('<span class="font-bold uppercase mr-1" style="color:var(--red)">?? ? Blocked</span>', '<span class="font-bold uppercase mr-1" style="color:var(--red)">禁止 · Blocked</span>', "dashboard blocked"),
        ('<span class="font-bold uppercase mr-1" style="color:var(--purple)">?? ? Valid</span>', '<span class="font-bold uppercase mr-1" style="color:var(--purple)">有效候選 · Valid</span>', "dashboard valid"),
        ('<span class="font-bold uppercase mr-1" style="color:var(--blue)">??? ? Next</span>', '<span class="font-bold uppercase mr-1" style="color:var(--blue)">下一步 · Next</span>', "dashboard next"),
        ("x-text=\"'???? ? Opportunity Status'\"", "x-text=\"'機會狀態 · Opportunity Status'\"", "opportunity status title"),
        ('<span class="font-bold mr-1" style="color:var(--amber)">Why ? <span', '<span class="font-bold mr-1" style="color:var(--amber)">原因 · Why · <span', "opportunity why label"),
        ('<span class="font-bold mr-1" style="color:var(--green)">Upgrade ? <span', '<span class="font-bold mr-1" style="color:var(--green)">升級條件 · Upgrade · <span', "opportunity upgrade label"),
        ("x-text=\"(today7.opportunity_status.blockers||[]).join(' ? ')\"", "x-text=\"(today7.opportunity_status.blockers||[]).join(' · ')\"", "blockers join"),
        ("x-text=\"(today7.opportunity_status.upgrade_triggers||[]).join(' ? ')\"", "x-text=\"(today7.opportunity_status.upgrade_triggers||[]).join(' · ')\"", "upgrade join"),
        ("x-text=\"'? '+today7.top_monitor.label\"", "x-text=\"'· '+today7.top_monitor.label\"", "top monitor prefix"),
    ]
    for old, new, label in dash_ops:
        sub(old, new, label)

    for old, new, label in [
        ('<div class="font-bold uppercase mb-1" style="color:var(--t3)">?? ? Now</div>', '<div class="font-bold uppercase mb-1" style="color:var(--t3)">現在 · Now</div>', "dossier now label"),
        ('<div class="font-bold uppercase mb-1" style="color:var(--t3)">?? ? Why</div>', '<div class="font-bold uppercase mb-1" style="color:var(--t3)">原因 · Why</div>', "dossier why label"),
        ('<div class="font-bold uppercase mb-1" style="color:var(--green)">?? ? Allowed</div>', '<div class="font-bold uppercase mb-1" style="color:var(--green)">允許 · Allowed</div>', "dossier allowed"),
        ('<div class="font-bold uppercase mb-1" style="color:var(--red)">?? ? Blocked</div>', '<div class="font-bold uppercase mb-1" style="color:var(--red)">禁止 · Blocked</div>', "dossier blocked"),
        ('<div class="font-bold uppercase mb-1" style="color:var(--amber)">???? ? Missing</div>', '<div class="font-bold uppercase mb-1" style="color:var(--amber)">缺少內容 · Missing</div>', "dossier missing"),
        ('<span class="font-bold uppercase" style="color:var(--blue)">??? ? Next</span> ?', '<span class="font-bold uppercase" style="color:var(--blue)">下一步 · Next</span> ·', "dossier next"),
        ("(dossierOperatorBlock().allowed||[]).join(' ? ')", "(dossierOperatorBlock().allowed||[]).join(' · ')", "allowed join"),
        ("(dossierOperatorBlock().blocked||[]).join(' ? ')", "(dossierOperatorBlock().blocked||[]).join(' · ')", "blocked join"),
        ("return 'Confirm-only ? ?????????????????? ? no sizing ? no handoff';", "return 'Confirm-only · 僅結構確認：無入場價、無止損、無倉位 · no sizing · no handoff';", "confirm strip fallback"),
        ("return 'Structure snapshot ? ????';", "return 'Structure snapshot · 結構快照';", "structure title fallback"),
        ("if(field==='entry') return 'Reference level ? ????';", "if(field==='entry') return 'Reference level · 參考價位';", "entry label"),
        ("if(field==='stop') return 'Risk reference ? ????';", "if(field==='stop') return 'Risk reference · 風險參考';", "stop label"),
        ("if(field==='target') return 'Upside references ? ????';", "if(field==='target') return 'Upside references · 上行參考';", "target label"),
        ("return 'Paper draft disabled ? ??????? ? ? live Dossier + Playbook ???????';", "return 'Paper draft disabled · 紙上模擬已關閉 — 需 live Dossier + Playbook 確認後才可模擬';", "paper draft fallback"),
    ]:
        sub(old, new, label)

    sub(
        ':title="unifiedTruthStripLine()"\n                  x-text="unifiedTruthStripLine()"></span>',
        ':title="(typeof CCHelpers!==\'undefined\'&&CCHelpers.localizeScopedFreshnessStrip)?CCHelpers.localizeScopedFreshnessStrip(unifiedTruthStripLine()):unifiedTruthStripLine()"\n                  x-text="(typeof CCHelpers!==\'undefined\'&&CCHelpers.scopedFreshnessStripLocalized&&today7.system_truth)?CCHelpers.scopedFreshnessStripLocalized(today7.system_truth):(typeof CCHelpers!==\'undefined\'&&CCHelpers.localizeScopedFreshnessStrip)?CCHelpers.localizeScopedFreshnessStrip(unifiedTruthStripLine()):unifiedTruthStripLine()"></span>',
        "header truth strip",
    )
    sub(
        "x-text=\"'Board stance '+(isWaitDay()?'WAIT':'MONITOR')\"",
        "x-text=\"'看板姿態 '+(isWaitDay()?'WAIT · 等待':'MONITOR · 僅監察')+' · Board stance '+(isWaitDay()?'WAIT':'MONITOR')\"",
        "board stance",
    )
    sub(
        "x-text=\"'Upgrade · '+playbookCardUpgradeTrigger(r)\"",
        "x-text=\"'升級條件 · Upgrade · '+playbookCardUpgradeTrigger(r)\"",
        "upgrade trigger label",
    )
    sub(
        """        let detail=String(this.playbookCardPrimaryBlocker(r)||'').trim();
        const norm=s=>String(s||'').toUpperCase().replace(/[^A-Z0-9]+/g,' ').trim();""",
        """        let detail=String(this.playbookCardPrimaryBlocker(r)||'').trim();
        if(typeof CCHelpers!=='undefined'&&CCHelpers.playbookCardGateLine){
          return CCHelpers.playbookCardGateLine(status,detail);
        }
        const norm=s=>String(s||'').toUpperCase().replace(/[^A-Z0-9]+/g,' ').trim();""",
        "playbook gate helper",
    )
    sub(
        """        if(truth.truth_strip) return String(truth.truth_strip);
        if(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip) return CCHelpers.scopedFreshnessStrip(truth);
        if(typeof CCHelpers!=='undefined'&&CCHelpers.systemTruthLine) return CCHelpers.systemTruthLine(truth);
        return '';
      },
      todayDeployBlocked():""",
        """        if(truth.truth_strip) return String(truth.truth_strip);
        if(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStripLocalized) return CCHelpers.scopedFreshnessStripLocalized(truth);
        if(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip) return CCHelpers.scopedFreshnessStrip(truth);
        if(typeof CCHelpers!=='undefined'&&CCHelpers.systemTruthLine) return CCHelpers.systemTruthLine(truth);
        return '';
      },
      todayDeployBlocked():""",
        "unifiedTruthStripLine localized",
    )
    sub(
        """        if(typeof CCHelpers!=='undefined'&&CCHelpers.globalTruthStrip)
          return CCHelpers.globalTruthStrip(truth);
        if(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip)
          return CCHelpers.scopedFreshnessStrip(truth);""",
        """        if(typeof CCHelpers!=='undefined'&&CCHelpers.globalTruthStrip)
          return CCHelpers.globalTruthStrip(truth);
        if(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStripLocalized)
          return CCHelpers.scopedFreshnessStripLocalized(truth);
        if(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip)
          return CCHelpers.scopedFreshnessStrip(truth);""",
        "unifiedTruthStripLine global",
    )
    sub(
        """        const typed=(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip)
          ?CCHelpers.scopedFreshnessStrip(truth)
          :'';
        return {
          fetch:this.dataContractFetchBadge(),
          truth:typed||this.unifiedTruthStripLine()||this.canonicalRegimeLine()||'—',""",
        """        const typed=(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStripLocalized)
          ?CCHelpers.scopedFreshnessStripLocalized(truth)
          :((typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip)?CCHelpers.scopedFreshnessStrip(truth):'');
        return {
          fetch:this.dataContractFetchBadge(),
          truth:typed||this.unifiedTruthStripLine()||this.canonicalRegimeLine()||'—',""",
        "dataContractStrip",
    )
    sub(
        """        const typed=(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip)
          ?CCHelpers.scopedFreshnessStrip(truth):'';""",
        """        const typed=(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStripLocalized)
          ?CCHelpers.scopedFreshnessStripLocalized(truth):((typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip)?CCHelpers.scopedFreshnessStrip(truth):'');""",
        "headerChipGroups strip",
    )
    sub(
        """        return {
          surface_mode:mode,
          badge,
          title:base.title,
          subtitle,
          explanation,
          next_action:nextAction,
          fetch_state:fetchState,
          show_decision_chips:showChips,
          show_regime_strip:mode!=='guide_reference',
          chips,
          authority_badge:base.badge,
        };
      },
      pageAuthorityMode():""",
        """        const summary={
          surface_mode:mode,
          badge,
          title:base.title,
          subtitle,
          explanation,
          next_action:nextAction,
          fetch_state:fetchState,
          show_decision_chips:showChips,
          show_regime_strip:mode!=='guide_reference',
          chips,
          authority_badge:base.badge,
        };
        return (typeof CCHelpers!=='undefined'&&CCHelpers.localizeHeaderSurface)?CCHelpers.localizeHeaderSurface(summary):summary;
      },
      pageAuthorityMode():""",
        "headerSummary localize",
    )
    sub(
        """        if(detail) base.explanation=(base.explanation+' ('+String(detail)+')').trim();
        return base;
      },
      surfaceFetchStateMessage(state, detail):""",
        """        if(detail) base.explanation=(base.explanation+' ('+String(detail)+')').trim();
        return (typeof CCHelpers!=='undefined'&&CCHelpers.localizeFetchStateCopy)?CCHelpers.localizeFetchStateCopy(base):base;
      },
      surfaceFetchStateMessage(state, detail):""",
        "surfaceFetchStateCopy",
    )

    # Tab labels — line by line
    tab_map = {
        "label:'Guide'}": "label:'Guide · 指南'}",
        "label:'Dashboard'}": "label:'Dashboard · 看板'}",
        "label:'Playbook'}": "label:'Playbook · 候選'}",
        "label:'Discovery'}": "label:'Discovery · 掃描'}",
        "label:'Portfolio & Risk'}": "label:'Portfolio · 持倉'}",
        "label:'Search / Dossier'}": "label:'Dossier · 研究檔'}",
        "label:'Funds'}": "label:'Funds · 策略'}",
        "label:'Flow'}": "label:'Flow · 流量'}",
        "label:'RS·research'}": "label:'RS · 相對強度'}",
        "label:'Command · advanced',hidden_from_primary_nav:true}": "label:'Command · 進階',hidden_from_primary_nav:true}",
        "label:'Rejections'}": "label:'Rejections · 拒絕'}",
        "label:'Ops'}": "label:'Ops · 運行'}",
        "label:'IBKR'}": "label:'IBKR · 券商'}",
        "label:'Backtest Lab'}": "label:'Backtest · 回測'}",
        "label:'Strategy Lab'}": "label:'Strategy Lab · 策略實驗'}",
    }
    for old, new in tab_map.items():
        sub(old, new, f"tab {old}")

    sub(
        "x-text=\"'???? '+(isWaitDay()?'WAIT ? ??':'MONITOR ? ???')+' ? Board stance '+(isWaitDay()?'WAIT':'MONITOR')\"",
        "x-text=\"'看板姿態 '+(isWaitDay()?'WAIT · 等待':'MONITOR · 僅監察')+' · Board stance '+(isWaitDay()?'WAIT':'MONITOR')\"",
        "board stance corrupted q",
    )
    if re.search(
        r"x-text=\"'[^']*'\+\\(isWaitDay\\(\\)\\?'WAIT[^']*':'MONITOR[^']*'\\)\+'[^']*Board stance",
        text,
    ):
        text = re.sub(
            r"x-text=\"'[^']*'\+\\(isWaitDay\\(\\)\\?'WAIT[^']*':'MONITOR[^']*'\\)\+'[^']*Board stance '\+\\(isWaitDay\\(\\)\\?'WAIT':'MONITOR'\\)\"",
            "x-text=\"'看板姿態 '+(isWaitDay()?'WAIT · 等待':'MONITOR · 僅監察')+' · Board stance '+(isWaitDay()?'WAIT':'MONITOR')\"",
            text,
            count=1,
        )
        n += 1
        print("ok: board stance regex")
    sub("label:'RS?research'}", "label:'RS · 相對強度'}", "rs tab corrupted")
    sub("label:'Command ? advanced',hidden_from_primary_nav:true}", "label:'Command · 進階',hidden_from_primary_nav:true}", "command tab corrupted")
    sub(
        """        const typed=(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip)
          ?CCHelpers.scopedFreshnessStrip(truth)
          :'';
        return {
          fetch:this.dataContractFetchBadge(),
          truth:typed||this.unifiedTruthStripLine()||this.canonicalRegimeLine()||'?',""",
        """        const typed=(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStripLocalized)
          ?CCHelpers.scopedFreshnessStripLocalized(truth)
          :((typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip)?CCHelpers.scopedFreshnessStrip(truth):'');
        return {
          fetch:this.dataContractFetchBadge(),
          truth:typed||this.unifiedTruthStripLine()||this.canonicalRegimeLine()||'—',""",
        "dataContractStrip ascii dash",
    )

    INDEX.write_text(text, encoding="utf-8")
    text.encode("utf-8")
    print(f"done — {n} replacements")


if __name__ == "__main__":
    main()
