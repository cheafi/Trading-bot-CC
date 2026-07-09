#!/usr/bin/env python3
"""Restore UTF-8 emojis and Chinese labels corrupted to ?? in index.html."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src/api/templates/index.html"


def git_show(rev: str, path: str) -> str:
    return subprocess.check_output(["git", "show", f"{rev}:{path}"]).decode("utf-8")


def norm(s: str) -> str:
    s = re.sub(r"\?\?", "EMOJI", s)
    s = re.sub(r"[\u4e00-\u9fff]+", "ZH", s)
    s = s.replace("?", "SEP")
    s = re.sub(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\u2600-\u27BF]", "EMOJI", s)
    s = re.sub(r"[·—–]", "SEP", s)
    return s


def skel(s: str) -> str:
    return re.sub(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\u4e00-\u9fff·—\?]", "", s)


def restore_from_clean_refs(text: str) -> tuple[str, int]:
    clean_map: dict[str, str] = {}
    for rev in ("5078060", "e0179c6", "45ed4a5"):
        try:
            ref = git_show(rev, "src/api/templates/index.html")
        except subprocess.CalledProcessError:
            continue
        for line in ref.splitlines():
            if re.search(
                r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\u2600-\u27BF\u4e00-\u9fff·—]",
                line,
            ):
                clean_map[norm(line)] = line

    restored = 0
    out: list[str] = []
    for line in text.splitlines():
        key = norm(line)
        if key in clean_map and line != clean_map[key] and skel(line) == skel(clean_map[key]):
            out.append(clean_map[key])
            restored += 1
        else:
            out.append(line)
    return "\n".join(out) + "\n", restored


EXPLICIT_REPLACEMENTS: list[tuple[str, str]] = [
    ("{id:'guide',icon:'??',label:'Guide ? ??'}", "{id:'guide',icon:'📖',label:'Guide · 指南'}"),
    ("{id:'today',icon:'??',label:'Dashboard ? ??'}", "{id:'today',icon:'🎯',label:'Dashboard · 看板'}"),
    ("{id:'signals',icon:'??',label:'Playbook ? ??'}", "{id:'signals',icon:'📋',label:'Playbook · 候選'}"),
    ("{id:'scanners',icon:'??',label:'Discovery ? ??'}", "{id:'scanners',icon:'🔬',label:'Discovery · 掃描'}"),
    ("{id:'portfolio',icon:'??',label:'Portfolio ? ??'}", "{id:'portfolio',icon:'💼',label:'Portfolio · 持倉'}"),
    ("{id:'dossier',icon:'??',label:'Dossier ? ???'}", "{id:'dossier',icon:'🔍',label:'Dossier · 研究檔'}"),
    ("{id:'funds',icon:'??',label:'Funds ? ??'}", "{id:'funds',icon:'💼',label:'Funds · 策略'}"),
    ("{id:'flow',icon:'??',label:'Flow ? ??'}", "{id:'flow',icon:'💧',label:'Flow · 流量'}"),
    ("{id:'rs',icon:'??',label:'RS ? ????'}", "{id:'rs',icon:'📈',label:'RS · 相對強度'}"),
    (
        "{id:'command',icon:'??',label:'Command ? ??',hidden_from_primary_nav:true}",
        "{id:'command',icon:'🖥',label:'Command · 進階',hidden_from_primary_nav:true}",
    ),
    ("{id:'notrade',icon:'??',label:'Rejections ? ??'}", "{id:'notrade',icon:'🚫',label:'Rejections · 拒絕'}"),
    ("{id:'ops',icon:'??',label:'Ops ? ??'}", "{id:'ops',icon:'⚙️',label:'Ops · 運行'}"),
    ("{id:'ibkr',icon:'?',label:'IBKR ? ??'}", "{id:'ibkr',icon:'⚡',label:'IBKR · 券商'}"),
    ("{id:'btlab',icon:'??',label:'Backtest ? ??'}", "{id:'btlab',icon:'🧪',label:'Backtest · 回測'}"),
    ("{id:'stratlab',icon:'??',label:'Strategy Lab ? ????'}", "{id:'stratlab',icon:'📊',label:'Strategy Lab · 策略實驗'}"),
    (
        "x-text=\"'???? ? Replay: '+(ccReplayAsOf||'')+' ? ???????????'\"",
        "x-text=\"'⏪ 回放 · Replay: '+(ccReplayAsOf||'')+' · 全介面歷史快照'\"",
    ),
    ("Replay mode ? ?????? ? ????", "Replay mode · 歷史快照 · 非即時"),
    ("???? Exit live", "⏩ 回到即時 · Exit live"),
    (
        "x-text=\"'???? '+(isWaitDay()?'WAIT ? ??':'MONITOR ? ???')+' ? Board stance '+(isWaitDay()?'WAIT':'MONITOR')\"",
        "x-text=\"'看板姿態 '+(isWaitDay()?'WAIT · 等待':'MONITOR · 僅監察')+' · Board stance '+(isWaitDay()?'WAIT':'MONITOR')\"",
    ),
    ("x-text=\"agentMonitor.submitting?'?':'????'\"", "x-text=\"agentMonitor.submitting?'…':'提交監察'\""),
    ("x-text=\"agentMonitor.submitting?'?':'+ ??'\"", "x-text=\"agentMonitor.submitting?'…':'+ 新增'\""),
    ("???? ? Opportunity Status", "機會狀態 · Opportunity Status"),
    ("?? ? Why ? ", "原因 · Why · "),
    ("???? ? Upgrade ? ", "升級條件 · Upgrade · "),
    ("????? ? Actionable Today", "今日可執行 · Actionable Today"),
    ("???? ? ??? / ??? IBKR", "僅紙上 · 不可交接 IBKR"),
    ("return {title:'???? ? Getting started'", "return {title:'如何開始 · Getting started'"),
    ("title=\"? Time Travel ? ??????\"", "title=\"⏪ Time Travel · 全介面回放\""),
    ("?? Guide ? How to use this platform", "📖 Guide · How to use this platform"),
    ("? Time Travel ? ??????", "⏪ Time Travel · 全介面回放"),
    ("? Close", "✕ Close"),
    (
        "risk_alerts&&risk_alerts.by_severity.CRITICAL>0?'??':'?'",
        "risk_alerts&&risk_alerts.by_severity.CRITICAL>0?'🚨':'⚠️'",
    ),
    (
        "brief_regen_loading?'?':(brief_status?.latest?.age_days>2?'?':'?')",
        "brief_regen_loading?'⏳':(brief_status?.latest?.age_days>2?'⛔':'⚠️')",
    ),
    ("brief_regen_loading?'REGEN?':", "brief_regen_loading?'REGEN…':"),
    ("Exporting?':'Export All Pages'", "Exporting…':'Export All Pages'"),
    ("Loading dashboard?'", "Loading dashboard…'"),
    ("'?? '+cmd.decision.macro_regime", "'🌍 '+cmd.decision.macro_regime"),
    ("'?? '+cmd.decision.strategy_style", "'📊 '+cmd.decision.strategy_style"),
    ("?? ? Now", "現在 · Now"),
    ("?? ? Why", "原因 · Why"),
    ("?? ? Allowed", "允許 · Allowed"),
    ("?? ? Blocked", "禁止 · Blocked"),
    ("???? ? Missing", "缺少資料 · Missing"),
    ("??? ? Next", "下一步 · Next"),
    ("PAPER DEPLOY ? ????", "PAPER DEPLOY · 紙上部署"),
    ("moreTabs.find(t=>t.id===tab).label:'? More'", "moreTabs.find(t=>t.id===tab).label:'⋯ More'"),
    ("x-text=\"'?? '+topRankedHeroLabel()\"", "x-text=\"'🏆 '+topRankedHeroLabel()\""),
    ("?? Morning Briefing ? ", "📰 Morning Briefing · "),
    ("'?? '+(today7.regime.trend||'?')", "'📈 '+(today7.regime.trend||'—')"),
    ("'?? Vol '+(today7.regime.volatility||'?')", "'📊 Vol '+(today7.regime.volatility||'—')"),
    ("'??'+opp.structure.trend", "'↗'+opp.structure.trend"),
    ("'?? BQ:'+opp.structure.breakout_quality", "'⚡ BQ:'+opp.structure.breakout_quality"),
    ("'??'+opp.entry_quality.verdict", "'✓'+opp.entry_quality.verdict"),
    ("'?? '+(Array.isArray(opp.why_not)", "'⚠ '+(Array.isArray(opp.why_not)"),
    ("'?? '+(Array.isArray(r.why_not)", "'⚠ '+(Array.isArray(r.why_not)"),
    ("??? Risk Guard Active", "🛡 Risk Guard Active"),
    ("'?? '+r.structure.trend.toUpperCase()", "'↗ '+r.structure.trend.toUpperCase()"),
    ("'?? '+r.entry_quality.verdict", "'✓ '+r.entry_quality.verdict"),
    ("'??Q'+r.fundamentals.quality", "'Q'+r.fundamentals.quality"),
    (
        "row.status==='TRUSTED'?'??':row.status==='TENTATIVE'?'??':'??'",
        "row.status==='TRUSTED'?'✓':row.status==='TENTATIVE'?'~':'?'",
    ),
    (
        "catName==='FLOW'?'??':catName==='VALIDATION'?'?':catName===",
        "catName==='FLOW'?'💧':catName==='VALIDATION'?'✓':catName===",
    ),
    (
        "pf.corrPreview.blocked?'?? ':pf.corrPreview.warn?'? ':'? '",
        "pf.corrPreview.blocked?'⛔ ':pf.corrPreview.warn?'⚠ ':'✓ '",
    ),
    ("?? BRACKET ARMED ? ", "✅ BRACKET ARMED · "),
    ("ops.running?'??':'??'", "ops.running?'🟢':'⏸'"),
    ("ops.circuit_breaker?'??':'?'", "ops.circuit_breaker?'🛑':'✓'"),
    (
        "shadowImport.busy?'????':researchGettingStarted('shadow').nextB",
        "shadowImport.busy?'匯入中…':researchGettingStarted('shadow').nextB",
    ),
    (
        "dashboardEmptyState().kind==='WAIT_DAY_OK'?'??':'??'",
        "dashboardEmptyState().kind==='WAIT_DAY_OK'?'✓':'📭'",
    ),
    ("apiError.startsWith('??')", "apiError.startsWith('ℹ')"),
    ("apiError.startsWith('?')?'color:#fde68a", "apiError.startsWith('⚠')?'color:#fde68a"),
    ("title=\"??????? ? Export all pages", "title=\"一鍵匯出全介面 · Export all pages"),
    ("??????? ? Try typing", "試試輸入 · Try typing"),
    (
        "CC ? Clarity Console ? regime-aware market intelligence ? MIT License",
        "CC · Clarity Console · regime-aware market intelligence · MIT License",
    ),
    (
        "<span style=\"font-size:16px\">??</span>Guide</a>",
        "<span style=\"font-size:16px\">📖</span>Guide</a>",
    ),
    (
        "<span style=\"font-size:16px\">??</span>Dashboard</a>",
        "<span style=\"font-size:16px\">🎯</span>Dashboard</a>",
    ),
    (
        "<span style=\"font-size:16px\">??</span>Playbook</a>",
        "<span style=\"font-size:16px\">📋</span>Playbook</a>",
    ),
    (
        "<span style=\"font-size:16px\">??</span>Discovery</a>",
        "<span style=\"font-size:16px\">🔬</span>Discovery</a>",
    ),
    (
        "<span style=\"font-size:16px\">??</span>Portfolio</a>",
        "<span style=\"font-size:16px\">💼</span>Portfolio</a>",
    ),
    (
        "<span style=\"font-size:16px\">?</span>IBKR</a>",
        "<span style=\"font-size:16px\">⚡</span>IBKR</a>",
    ),
    (
        "<span style=\"font-size:16px\">??</span>Dossier</a>",
        "<span style=\"font-size:16px\">🔍</span>Dossier</a>",
    ),
    (
        "<span style=\"font-size:16px\">??</span>Ops</a>",
        "<span style=\"font-size:16px\">⚙️</span>Ops</a>",
    ),
    (
        "???? Whole-page",
        "🌐 Whole-page",
    ),
    (
        "???? Single ticker",
        "🎯 Single ticker",
    ),
    (
        "catName==='PATTERN'?'??':catName==='SE",
        "catName==='PATTERN'?'📐':catName==='SE",
    ),
    # Runtime toast / fallback copy (post-5078060 strings corrupted in 127078e pass)
    (
        "this.showExportToast('Playbook ?? Watch ?? ? 入門指引')",
        "this.showExportToast('Playbook 無 Watch 名單 · 先刷新')",
    ),
    (
        "this.showExportToast('?? Playbook ?? '+n+' 入門指引')",
        "this.showExportToast('✓ 已從 Playbook 建立 '+n+' 條監察')",
    ),
    (
        "this.showExportToast('???? PDF? ? Preparing PDF?')",
        "this.showExportToast('📄 準備 PDF 中… · Preparing PDF…')",
    ),
    (
        "this.showExportToast('??? ? Downloaded '+(res.filename||'cc-review.pdf'))",
        "this.showExportToast('✓ 已下載 · Downloaded '+(res.filename||'cc-review.pdf'))",
    ),
    (
        "this.showExportToast('PDF ???? ? PDF export failed')",
        "this.showExportToast('PDF 匯出失敗 · PDF export failed')",
    ),
    (
        "this.showExportToast('PDF 入門指引 ? PDF export unavailable')",
        "this.showExportToast('PDF 匯出不可用 · PDF export unavailable')",
    ),
    (
        ":'???? ? scan evidence'",
        ":'Research-only · scan evidence'",
    ),
    (
        "this.ibkr.orderError='?? SLIPPAGE BLOCK:\\n  ? '+slipReasonsText+'\\n\\n(Spread '+slipVerdict.spread_bps+'bps ? ADV-partici",
        "this.ibkr.orderError='🛑 SLIPPAGE BLOCK:\\n  • '+slipReasonsText+'\\n\\n(Spread '+slipVerdict.spread_bps+'bps · ADV-partici",
    ),
    (
        "if(!sid){this.showExportToast('入門指引??? ID');return;}",
        "if(!sid){this.showExportToast('請輸入策略 ID');return;}",
    ),
    (
        "this.showExportToast('入門指引?? · 同步至 Playbook 入門指引????')",
        "this.showExportToast('草稿已建立 · Draft saved · sync to Playbook when ready')",
    ),
    (
        "return 'Lagged / illustrative context ? 入門指引入門指引?? ? not used for confirmation'",
        "return 'Lagged / illustrative context · 延遲參考 · not used for confirmation'",
    ),
    (
        "return 'Paper draft disabled ? 入門指引?? ? ? live Dossier + Playbook 入門指引??'",
        "return 'Paper draft disabled · 紙上草稿關閉 · use live Dossier + Playbook path'",
    ),
]


def count_corrupted(text: str) -> int:
    n = 0
    for line in text.splitlines():
        if "<!-- ??" in line or re.search(r"\?{4,}", line):
            n += 1
        elif re.search(r"['\"][^'\"]*\?\?[^'\"]*['\"]", line) and not re.search(
            r"\?\?\d|\?\?null|\?\?undefined|\?\?\[\]|\?\?\{\}|\?\?''|\?\?\"\"|\?\?\)|\?\?,",
            line,
        ):
            n += 1
    return n


def restore_section_dividers(text: str) -> tuple[str, int]:
    """Restore ══════ / ── section comment markers corrupted to ? runs."""
    divider_map: dict[str, str] = {}
    for rev in ("5078060", "e0179c6", "45ed4a5"):
        try:
            ref = git_show(rev, "src/api/templates/index.html")
        except subprocess.CalledProcessError:
            continue
        for line in ref.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("<!--") and stripped.endswith("-->")):
                continue
            if re.search(r"[═─]", line):
                divider_map[norm(line)] = line

    restored = 0
    out: list[str] = []
    for line in text.splitlines():
        key = norm(line)
        if key in divider_map and line != divider_map[key] and skel(line) == skel(divider_map[key]):
            out.append(divider_map[key])
            restored += 1
        else:
            out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), restored


def main() -> None:
    before = INDEX.read_text(encoding="utf-8")
    before_corrupt = count_corrupted(before)
    before_q = before.count("??")

    text, restored_lines = restore_from_clean_refs(before)
    text, divider_lines = restore_section_dividers(text)
    explicit = 0
    for old, new in EXPLICIT_REPLACEMENTS:
        if old in text:
            text = text.replace(old, new)
            explicit += 1

    INDEX.write_text(text, encoding="utf-8")
    text.encode("utf-8")

    after = INDEX.read_text(encoding="utf-8")
    after_corrupt = count_corrupted(after)
    after_q = after.count("??")

    print(f"restored {restored_lines} lines from clean git refs")
    print(f"restored {divider_lines} section divider comments")
    print(f"applied {explicit} explicit replacements")
    print(f"corrupted-line estimate: {before_corrupt} -> {after_corrupt}")
    print(f"total ?? count: {before_q} -> {after_q} (includes JS nullish coalescing)")


if __name__ == "__main__":
    main()
