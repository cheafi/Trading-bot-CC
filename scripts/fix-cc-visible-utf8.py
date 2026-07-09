#!/usr/bin/env python3
"""Fix remaining visible UTF-8 / emoji corruption in index.html (post git-restore pass)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src/api/templates/index.html"

# Order matters — longer / more specific patterns first.
REPLACEMENTS: list[tuple[str, str]] = [
    # Section comments
    ("/* ?? Command Center terminal layout ?? */", "/* ── Command Center terminal layout ── */"),
    ("/* ?? Guide / Onboarding ?? */", "/* ── Guide / Onboarding ── */"),
    ("// ?? DEAD-CODE WARNING (no UI binding, kept only because JS methods still reference them) ??",
     "// ── DEAD-CODE WARNING (no UI binding, kept only because JS methods still reference them) ──"),
    ("// ?? IBKR auto-sync: when broker is connected, broker positions become canonical ??",
     "// ── IBKR auto-sync: when broker is connected, broker positions become canonical ──"),
    ("// ?? Correlation guard: warn (>0.6) / block (>0.7) when adding correlated names ??",
     "// ── Correlation guard: warn (>0.6) / block (>0.7) when adding correlated names ──"),
    ("// ?? 24/7 Fund Monitor (sprint89) ??????????????????????????????????????",
     "// ── 24/7 Fund Monitor (sprint89) ──"),
    ("// ?? BRACKET ORDER (parent + stop + target, OCA) ?????????????????????????",
     "// ── BRACKET ORDER (parent + stop + target, OCA) ──"),
    ("// ?? Pre-trade slippage gate (BLOCK on illiquid; WARN on costly) ??",
     "// ── Pre-trade slippage gate (BLOCK on illiquid; WARN on costly) ──"),
    ("// ?? Bracket live polling + cancel ??????????????????????????????????????",
     "// ── Bracket live polling + cancel ──"),
    ("// ?? Playbook ? IBKR bracket helper ?????????????????????????????????????",
     "// ── Playbook → IBKR bracket helper ──"),
    ("// ?? PM Strip (model funds mini-cards, refreshed lazily) ????????????????",
     "// ── PM Strip (model funds mini-cards, refreshed lazily) ──"),
    ("// ?? Model Funds (productized fund cards) ??????????????????????????????",
     "// ── Model Funds (productized fund cards) ──"),
    ("// ?? Trade Intelligence ????????????????????????????????????????????????",
     "// ── Trade Intelligence ──"),
    # Time travel modal
    (
        "????????????????????????????????????????",
        "選擇回放日期 · 載入該日 Morning Brief 快照 · Dashboard + Playbook + 標頭同步切換 · Pick a date to replay the whole console from that day's brief.",
    ),
    ("x-text=\"tt.loading?'? Loading?':'? Enter replay'\"", "x-text=\"tt.loading?'⏳ Loading…':'⏪ Enter replay'\""),
    ("x-text=\"tt.loading?'? Running?':'? Run replay'\"", "x-text=\"tt.loading?'⏳ Running…':'▶ Run replay'\""),
    (".join(' ? ')", ".join(' · ')"),
    ("? I Understand ? Proceed", "✓ I Understand · Proceed"),
    ("? Position Risk Alerts", "⚠ Position Risk Alerts"),
    (">? Refresh</button>", ">↻ Refresh</button>"),
    (">? Load</button>", ">↻ Load</button>"),
    (">? Rotate</button>", ">🔄 Rotate</button>"),
    ("? No active risk alerts.", "✓ No active risk alerts."),
    ("? Strategy signals", "📊 Strategy signals"),
    ("Pick a ticker + date ? see regime", "Pick a ticker + date · see regime"),
    ("Pick a date ? Enter replay loads", "Pick a date · Enter replay loads"),
    ("trust.as_of?'? '+", "trust.as_of?'🕐 '+"),
    (">? AI</span>", ">✨ AI</span>"),
    ("apiError.startsWith('?')?'color:#fde68a", "apiError.startsWith('⚠')?'color:#fde68a"),
    ("x-show=\"apiError.startsWith('?')\"", "x-show=\"apiError.startsWith('⚠')\""),
    ("'Uptime: '+(healthData?.uptime_seconds?Math.round(healthData.uptime_seconds)+'s':'?')", "'Uptime: '+(healthData?.uptime_seconds?Math.round(healthData.uptime_seconds)+'s':'—')"),
    # Command / agent
    ("<span style=\"font-size:13px\">??</span>", "<span style=\"font-size:13px\">⚠️</span>"),
    ("<span style=\"font-size:14px\">??</span>", "<span style=\"font-size:14px\">⚠️</span>"),
    ("? SYNTHETIC ? Regime data is synthetic", "⚠ SYNTHETIC · Regime data is synthetic"),
    ("? Morning briefing", "📰 Morning briefing"),
    ("Intent inbox ? rule builder", "Intent inbox · rule builder"),
    ("?? Agent ?? ? Monitor only", "🤖 Agent · 監察 · Monitor only"),
    ("Agent ? Monitor copilot", "Agent · Monitor copilot"),
    ("No degraded note ? active monitor copilot.", "No degraded note · active monitor copilot."),
    (">?? Agent Journal</summary>", ">📝 Agent Journal</summary>"),
    (">?? Agent Reliability</summary>", ">📊 Agent Reliability</summary>"),
    (">? Starred</div>", ">⭐ Starred</div>"),
    ("click ? Refresh to load", "click ↻ Refresh to load"),
    (">? SYNTHETIC</span>", ">⚠ SYNTHETIC</span>"),
    (">? Why Now</div>", ">💡 Why Now</div>"),
    (">? Contradictions</div>", ">⚖ Contradictions</div>"),
    ("Loading decisions?", "Loading decisions…"),
    ("x-text=\"'🕐 '+topMonitorLabelsLine()\"", "x-text=\"'· '+topMonitorLabelsLine()\""),
    ("x-text=\"'? '+topMonitorLabelsLine()\"", "x-text=\"'· '+topMonitorLabelsLine()\""),
    # Dashboard / opportunities
    (">?? Top Opportunities</summary>", ">🎯 Top Opportunities</summary>"),
    ("Regime snapshot ? expand", "Regime snapshot · expand"),
    ("Unlock deploy ? expand", "Unlock deploy · expand"),
    ("? AI Commentary ? expand", "✨ AI Commentary · expand"),
    (">? What Changed</div>", ">📈 What Changed</div>"),
    ("title=\"Star (favorite)\" @click=\"toggleStar(opp.ticker)\">?</button>",
     "title=\"Star (favorite)\" @click=\"toggleStar(opp.ticker)\">★</button>"),
    ("title=\"Love (high conviction)\" @click=\"toggleLove(opp.ticker)\">?</button>",
     "title=\"Love (high conviction)\" @click=\"toggleLove(opp.ticker)\">♥</button>"),
    ("?? Strong thesis, weak timing ? wait for better entry before acting",
     "⚠ Strong thesis, weak timing · wait for better entry before acting"),
    ("?? Good timing but weak thesis ? low conviction, size down or skip",
     "⚠ Good timing but weak thesis · low conviction, size down or skip"),
    ("?? Good setup but execution risk high ? use limit orders, reduce size by 50%",
     "⚠ Good setup but execution risk high · use limit orders, reduce size by 50%"),
    ("?? Strong thesis, weak timing ? wait for pullback",
     "⚠ Strong thesis, weak timing · wait for pullback"),
    ("?? Good timing, weak thesis ? low conviction",
     "⚠ Good timing, weak thesis · low conviction"),
    (">?? Vol?</span>", ">📈 Vol✓</span>"),
    (">??ER Blackout</span>", ">📅 ER Blackout</span>"),
    (">?? Earnings Blackout</span>", ">📅 Earnings Blackout</span>"),
    ("?? <strong style=\"color:var(--t1)\">PILOT</strong> when: partial edge with stop ? review-only",
     "🧪 <strong style=\"color:var(--t1)\">PILOT</strong> when: partial edge with stop · review-only"),
    ("?? <strong style=\"color:var(--t1)\">Historical Win Rate</strong> shown when ?10 similar past trades exist ? use as extra confirmation",
     "📊 <strong style=\"color:var(--t1)\">Historical Win Rate</strong> shown when ≥10 similar past trades exist · use as extra confirmation"),
    ("board-ranked score ?8, thesis+timing ?65%, R:R ?2.5", "board-ranked score ≥8, thesis+timing ≥65%, R:R ≥2.5"),
    ("ranked #1?10 but below TRADE bar (score 6?8", "ranked #1–10 but below TRADE bar (score 6–8"),
    ("Green ?70%</span> ? <span", "Green ≥70%</span> · <span"),
    ("Amber ?50%</span> ? <span", "Amber ≥50%</span> · <span"),
    ("<span style=\"color:var(--green)\">?</span> <strong style=\"color:var(--t1)\">BUY</strong> ? Enter now",
     "<span style=\"color:var(--green)\">●</span> <strong style=\"color:var(--t1)\">BUY</strong> · Enter now"),
    ("<strong style=\"color:var(--t1)\">BUY_ON_DIP</strong> ? Good setup", "<strong style=\"color:var(--t1)\">BUY_ON_DIP</strong> · Good setup"),
    ("<span style=\"color:var(--amber)\">?</span> <strong style=\"color:var(--t1)\">WATCH</strong> ? Monitor",
     "<span style=\"color:var(--amber)\">●</span> <strong style=\"color:var(--t1)\">WATCH</strong> · Monitor"),
    ("<strong style=\"color:var(--t1)\">WAIT</strong> ? Regime unfavorable", "<strong style=\"color:var(--t1)\">WAIT</strong> · Regime unfavorable"),
    ("<span style=\"color:var(--red)\">?</span> <strong style=\"color:var(--t1)\">AVOID</strong> ? Extended",
     "<span style=\"color:var(--red)\">●</span> <strong style=\"color:var(--t1)\">AVOID</strong> · Extended"),
    ("? <strong style=\"color:var(--t1)\">Full TRADE</strong> when:", "● <strong style=\"color:var(--t1)\">Full TRADE</strong> when:"),
    ("? <strong style=\"color:var(--t1)\">Watch</strong> when:", "● <strong style=\"color:var(--t1)\">Watch</strong> when:"),
    ("? Tradeability improves to SELECTIVE+", "● Tradeability improves to SELECTIVE+"),
    ("<div>? At least 1 deploy-qualified setup exists</div>", "<div>● At least 1 deploy-qualified setup exists</div>"),
    ("<div>? Broker handoff is live</div>", "<div>● Broker handoff is live</div>"),
    ("<div>? Board-level quality supports risk (?1 watch-qualified name on fresh data)</div>",
     "<div>● Board-level quality supports risk (≥1 watch-qualified name on fresh data)</div>"),
    ("x-text=\"(c.met?'? ':'? ')+c.label\"", "x-text=\"(c.met?'✓ ':'○ ')+c.label\""),
    ("x-text=\"'? '+(Array.isArray(today7.top_ranked[0].why_now)", "x-text=\"'✓ '+(Array.isArray(today7.top_ranked[0].why_now)"),
    ("x-text=\"'? Invalidation: '+today7.top_ranked[0].invalidation\"", "x-text=\"'✕ Invalidation: '+today7.top_ranked[0].invalidation\""),
    ("x-text=\"'? '+ln\"", "x-text=\"'• '+ln\""),
    ("x-text=\"'? '+c\"", "x-text=\"'• '+c\""),
    ("x-text=\"'? '+eventRiskLabel", "x-text=\"'📅 '+eventRiskLabel"),
    ("x-text=\"'? '+nm.upgrade_trigger\"", "x-text=\"'→ '+nm.upgrade_trigger\""),
    ("x-text=\"'✓ '+nm.upgrade_trigger\"", "x-text=\"'→ '+nm.upgrade_trigger\""),
    ("x-text=\"'? '+cc.upgrade_trigger\"", "x-text=\"'→ '+cc.upgrade_trigger\""),
    ("x-text=\"'⚠ '+(Array.isArray(opp.why_not)", "x-text=\"'⚠ '+(Array.isArray(opp.why_not)"),
    ("x-text=\"'⚠ '+(Array.isArray(r.why_not)", "x-text=\"'⚠ '+(Array.isArray(r.why_not)"),
    ("x-text=\"'⚠ '+ln\"", "x-text=\"'✗ '+ln\""),
    ("x-text=\"'⚠ '+rb\"", "x-text=\"'⛔ '+rb\""),
    ("x-text=\"'⚠ '+today7.cross_asset_confirmation.conflicts.join", "x-text=\"'⚠ '+today7.cross_asset_confirmation.conflicts.join"),
    ("x-text=\"'✓ '+today7.cross_asset_confirmation.confirms.join", "x-text=\"'✓ '+today7.cross_asset_confirmation.confirms.join"),
    # Strategy lab / discovery / ops
    (
        "????? ? Draft <span class=\"mono text-white\" x-text=\"stratLabDraft.draftId\"></span> ? ???? Playbook ???????????????",
        "草稿已建立 · Draft <span class=\"mono text-white\" x-text=\"stratLabDraft.draftId\"></span> · 尚未同步 Playbook · not yet promoted",
    ),
    ("x-text=\"stratLabDraft.generating?'?':researchGettingStarted('strategy').nextButton\"", "x-text=\"stratLabDraft.generating?'⏳':researchGettingStarted('strategy').nextButton\""),
    ("Raw scanner hits ? similar-pattern cluster ? debug", "Raw scanner hits · similar-pattern cluster · debug"),
    ("'hidden ? 0 strict passed'", "'hidden · 0 strict passed'"),
    (
        "x-text=\"catName==='FLOW'?'💧':catName==='VALIDATION'?'✓':catName==='PATTERN'?'📐':catName==='SECTOR'?'??':catName==='RISK'?'?':'??'\"",
        "x-text=\"(typeof CCHelpers!=='undefined'&&CCHelpers.signalCategoryIcon)?CCHelpers.signalCategoryIcon(catName):(catName==='FLOW'?'💧':catName==='VALIDATION'?'✓':catName==='PATTERN'?'📐':catName==='SECTOR'?'🏭':catName==='RISK'?'⚠':'📦')\"",
    ),
    (":disabled=\"ledgerView.loading\">??</button>", ":disabled=\"ledgerView.loading\">↻</button>"),
    ("x-text=\"ledgerView.expanded?'? Hide details':'? Show details ('+(ledgerView.rows?.length||0)+' rows)'\"",
     "x-text=\"ledgerView.expanded?'▾ Hide details':'▸ Show details ('+(ledgerView.rows?.length||0)+' rows)'\""),
    (">?? Health</button>", ">💚 Health</button>"),
    (">?? Engine State</div>", ">⚙ Engine State</div>"),
    (">?? IBKR</button>", ">⚡ IBKR</button>"),
    ("placeholder=\"Search ticker or company? (e.g. AAPL, ??)\"",
     "placeholder=\"Search ticker or company name (e.g. AAPL, 苹果)\""),
    ("x-text=\"'?' + (rl.thompson.best_arm.mean_multiplier??'?')",
     "x-text=\"'×' + (rl.thompson.best_arm.mean_multiplier??'—')"),
    # Runtime JS — delegate to CCHelpers where possible
    ("let msg='?????? ? ???? Brief ???';", "let msg=(typeof CCHelpers!=='undefined'&&CCHelpers.replayBriefMissingError)?CCHelpers.replayBriefMissingError():'No Morning Brief snapshot for that date';"),
    ("this.showExportToast('??????? ? ???? Playbook ?????????');",
     "this.showExportToast((typeof CCHelpers!=='undefined'&&CCHelpers.stratLabDraftCreatedToast)?CCHelpers.stratLabDraftCreatedToast():'Draft created · not yet synced to Playbook');"),
    ("throw new Error('CSV ????????????');",
     "throw new Error((typeof CCHelpers!=='undefined'&&CCHelpers.shadowCsvEmptyError)?CCHelpers.shadowCsvEmptyError():'CSV needs headers and at least one row');"),
    ("throw new Error('???? CSV ? ? ???????');",
     "throw new Error((typeof CCHelpers!=='undefined'&&CCHelpers.shadowCsvImportEmptyError)?CCHelpers.shadowCsvImportEmptyError():'No valid CSV rows to import');"),
    ("this.showExportToast('??? '+imported+' ????? ? ?????');",
     "this.showExportToast((typeof CCHelpers!=='undefined'&&CCHelpers.shadowImportSuccessToast)?CCHelpers.shadowImportSuccessToast(imported):('Imported '+imported+' trades'));"),
    ("fundIcon(name){return name==='FUND_ALPHA'?'??':name==='FUND_PENDA'?'??':name==='FUND_MACRO'?'??':'??'},",
     "fundIcon(name){return (typeof CCHelpers!=='undefined'&&CCHelpers.fundIcon)?CCHelpers.fundIcon(name):(name==='FUND_ALPHA'?'🟢':name==='FUND_PENDA'?'🔵':name==='FUND_MACRO'?'🟣':'📦')},"),
    ("return 'Structure snapshot ? ????';", "return 'Structure snapshot · 結構快照';"),
    ("if(field==='entry') return 'Reference level ? ????';", "if(field==='entry') return 'Reference level · 參考價位';"),
    ("if(field==='stop') return 'Risk reference ? ????';", "if(field==='stop') return 'Risk reference · 風險參考';"),
    ("if(field==='target') return 'Upside references ? ????';", "if(field==='target') return 'Upside references · 上行參考';"),
    ("return 'Paper draft disabled ? ??????? ? ? live Dossier + Playbook ???????';",
     "return 'Paper draft disabled · 紙上模擬已關閉 — 需 live Dossier + Playbook 確認後才可模擬';"),
    ("// Auto-enable bracket if both stop + target are available ? close alpha?execution loop",
     "// Auto-enable bracket if both stop + target are available · close alpha→execution loop"),
]


def main() -> None:
    text = INDEX.read_text(encoding="utf-8")
    before = text.count("??")
    applied = 0
    for old, new in REPLACEMENTS:
        if old in text:
            text = text.replace(old, new)
            applied += 1
    INDEX.write_text(text, encoding="utf-8")
    text.encode("utf-8")
    after = text.count("??")
    print(f"applied {applied} visible UTF-8 replacements")
    print(f"total ?? count: {before} -> {after} (includes JS nullish coalescing)")


if __name__ == "__main__":
    main()
