#!/usr/bin/env python3
"""UTF-8 safe index.html Chinese clarity patches."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src/api/templates/index.html"

REPLACEMENTS: list[tuple[str, str]] = [
    (
        ':title="unifiedTruthStripLine()"\n                  x-text="unifiedTruthStripLine()"></span>',
        ':title="(typeof CCHelpers!==\'undefined\'&&CCHelpers.localizeScopedFreshnessStrip)?CCHelpers.localizeScopedFreshnessStrip(unifiedTruthStripLine()):unifiedTruthStripLine()"\n                  x-text="(typeof CCHelpers!==\'undefined\'&&CCHelpers.scopedFreshnessStripLocalized&&today7.system_truth)?CCHelpers.scopedFreshnessStripLocalized(today7.system_truth):(typeof CCHelpers!==\'undefined\'&&CCHelpers.localizeScopedFreshnessStrip)?CCHelpers.localizeScopedFreshnessStrip(unifiedTruthStripLine()):unifiedTruthStripLine()"></span>',
    ),
    (
        "x-text=\"'Board stance '+(isWaitDay()?'WAIT':'MONITOR')\"",
        "x-text=\"'看板姿態 '+(isWaitDay()?'WAIT · 等待':'MONITOR · 僅監察')+' · Board stance '+(isWaitDay()?'WAIT':'MONITOR')\"",
    ),
    (
        """        {id:'guide',icon:'📖',label:'Guide'},
        {id:'today',icon:'🎯',label:'Dashboard'},
        {id:'signals',icon:'📋',label:'Playbook'},
        {id:'scanners',icon:'🔬',label:'Discovery'},
        {id:'portfolio',icon:'💼',label:'Portfolio & Risk'},
        {id:'dossier',icon:'🔍',label:'Search / Dossier'},
      ],
      moreTabs:[
        {id:'funds',icon:'💼',label:'Funds'},
        {id:'flow',icon:'💧',label:'Flow'},
        {id:'rs',icon:'📈',label:'RS·research'},
        {id:'command',icon:'🖥',label:'Command · advanced',hidden_from_primary_nav:true},
        {id:'notrade',icon:'🚫',label:'Rejections'},
        {id:'ops',icon:'⚙️',label:'Ops'},
        {id:'ibkr',icon:'⚡',label:'IBKR'},
        {id:'btlab',icon:'🧪',label:'Backtest Lab'},
        {id:'stratlab',icon:'📊',label:'Strategy Lab'},""",
        """        {id:'guide',icon:'📖',label:'Guide · 指南'},
        {id:'today',icon:'🎯',label:'Dashboard · 看板'},
        {id:'signals',icon:'📋',label:'Playbook · 候選'},
        {id:'scanners',icon:'🔬',label:'Discovery · 掃描'},
        {id:'portfolio',icon:'💼',label:'Portfolio · 持倉'},
        {id:'dossier',icon:'🔍',label:'Dossier · 研究檔'},
      ],
      moreTabs:[
        {id:'funds',icon:'💼',label:'Funds · 策略'},
        {id:'flow',icon:'💧',label:'Flow · 流量'},
        {id:'rs',icon:'📈',label:'RS · 相對強度'},
        {id:'command',icon:'🖥',label:'Command · 進階',hidden_from_primary_nav:true},
        {id:'notrade',icon:'🚫',label:'Rejections · 拒絕'},
        {id:'ops',icon:'⚙️',label:'Ops · 運行'},
        {id:'ibkr',icon:'⚡',label:'IBKR · 券商'},
        {id:'btlab',icon:'🧪',label:'Backtest · 回測'},
        {id:'stratlab',icon:'📊',label:'Strategy Lab · 策略實驗'},""",
    ),
    (
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
    ),
    (
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
    ),
    (
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
    ),
    (
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
    ),
    (
        """        if(detail) base.explanation=(base.explanation+' ('+String(detail)+')').trim();
        return base;
      },
      surfaceFetchStateMessage(state, detail):""",
        """        if(detail) base.explanation=(base.explanation+' ('+String(detail)+')').trim();
        return (typeof CCHelpers!=='undefined'&&CCHelpers.localizeFetchStateCopy)?CCHelpers.localizeFetchStateCopy(base):base;
      },
      surfaceFetchStateMessage(state, detail):""",
    ),
    (
        """        let detail=String(this.playbookCardPrimaryBlocker(r)||'').trim();
        const norm=s=>String(s||'').toUpperCase().replace(/[^A-Z0-9]+/g,' ').trim();""",
        """        let detail=String(this.playbookCardPrimaryBlocker(r)||'').trim();
        if(typeof CCHelpers!=='undefined'&&CCHelpers.playbookCardGateLine){
          return CCHelpers.playbookCardGateLine(status,detail);
        }
        const norm=s=>String(s||'').toUpperCase().replace(/[^A-Z0-9]+/g,' ').trim();""",
    ),
    (
        """        const typed=(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip)
          ?CCHelpers.scopedFreshnessStrip(truth):'';""",
        """        const typed=(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStripLocalized)
          ?CCHelpers.scopedFreshnessStripLocalized(truth):((typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip)?CCHelpers.scopedFreshnessStrip(truth):'');""",
    ),
    (
        "x-text=\"'Upgrade · '+playbookCardUpgradeTrigger(r)\"",
        "x-text=\"'升級條件 · Upgrade · '+playbookCardUpgradeTrigger(r)\"",
    ),
]


def main() -> None:
    text = INDEX.read_text(encoding="utf-8")
    applied = 0
    for old, new in REPLACEMENTS:
        if old not in text:
            print("skip missing:", old[:60].replace("\n", " "))
            continue
        text = text.replace(old, new, 1)
        applied += 1
    INDEX.write_text(text, encoding="utf-8")
    text.encode("utf-8")  # validate
    print(f"applied {applied} replacements")


if __name__ == "__main__":
    main()
