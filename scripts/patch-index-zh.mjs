#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const INDEX = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src/api/templates/index.html');
let h = fs.readFileSync(INDEX, 'utf8');
let n = 0;

function rep(old, neu, label) {
  if (!h.includes(old)) {
    console.warn('skip (not found):', label || old.slice(0, 60));
    return;
  }
  h = h.replace(old, neu);
  n++;
  console.log('ok:', label || old.slice(0, 50));
}

rep(
  `:title="(cc_status.mode==='LIVE'?'Live trading enabled':cc_status.mode==='PAPER'?'Paper/dry-run mode':'Engine offline')+' — click for Ops'"`,
  `:title="(cc_status.mode==='LIVE'?'實盤交易 · Live trading enabled':cc_status.mode==='PAPER'?'紙上模擬 · Paper/dry-run mode':'引擎離線 · Engine offline')+' — 點擊開啟 Ops'"`,
  'mode pill title',
);

rep(
  `:title="(cc_status.breaker_reason||'Circuit breaker triggered')+' — click for Ops to reset'"`,
  `:title="(cc_status.breaker_reason||'熔斷已觸發 · Circuit breaker triggered')+' — 點擊 Ops 重設'"`,
  'breaker title',
);

rep(
  `                  :title="unifiedTruthStripLine()"
                  x-text="unifiedTruthStripLine()"></span>`,
  `                  :title="(typeof CCHelpers!=='undefined'&&CCHelpers.localizeScopedFreshnessStrip)?CCHelpers.localizeScopedFreshnessStrip(unifiedTruthStripLine()):unifiedTruthStripLine()"
                  x-text="(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStripLocalized&&today7.system_truth)?CCHelpers.scopedFreshnessStripLocalized(today7.system_truth):(typeof CCHelpers!=='undefined'&&CCHelpers.localizeScopedFreshnessStrip)?CCHelpers.localizeScopedFreshnessStrip(unifiedTruthStripLine()):unifiedTruthStripLine()"></span>`,
  'header truth strip',
);

rep(
  `title="One-click review PDF — issues page + all surfaces snapshot for ChatGPT review"`,
  `title="一鍵匯出檢視 PDF — 問題頁 + 全介面快照 · One-click review PDF — issues page + all surfaces snapshot for ChatGPT review"`,
  'export pdf title',
);

rep(
  `x-text="exportReviewPdfBusy?'Exporting…':'Export review PDF'"`,
  `x-text="exportReviewPdfBusy?'匯出中…':'匯出檢視 PDF · Export review PDF'"`,
  'export pdf label',
);

rep(
  `title="Guide / Help"`,
  `title="操作指南 · Guide / Help"`,
  'guide help title',
);

rep(
  `<div class="text-[10px] font-bold uppercase" style="color:var(--amber)">🤖 Agent 盯盤 · Monitor only</div>`,
  `<div class="text-[10px] font-bold uppercase" style="color:var(--amber)">🤖 Agent 盯盤 · 僅監察 · Monitor only</div>`,
  'agent badge',
);

rep(
  `x-text="'Board stance '+(isWaitDay()?'WAIT':'MONITOR')"`,
  `x-text="'看板姿態 '+(isWaitDay()?'WAIT · 等待':'MONITOR · 僅監察')+' · Board stance '+(isWaitDay()?'WAIT':'MONITOR')"`,
  'board stance pill',
);

rep(
  `        if(truth.truth_strip) return String(truth.truth_strip);
        if(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip) return CCHelpers.scopedFreshnessStrip(truth);`,
  `        if(truth.truth_strip) return String(truth.truth_strip);
        if(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStripLocalized) return CCHelpers.scopedFreshnessStripLocalized(truth);
        if(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip) return CCHelpers.scopedFreshnessStrip(truth);`,
  'unifiedTruthStripLine localized',
);

rep(
  `        const typed=(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip)
          ?CCHelpers.scopedFreshnessStrip(truth)
          :'';`,
  `        const typed=(typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStripLocalized)
          ?CCHelpers.scopedFreshnessStripLocalized(truth)
          :((typeof CCHelpers!=='undefined'&&CCHelpers.scopedFreshnessStrip)?CCHelpers.scopedFreshnessStrip(truth):'');`,
  'dataContract typed strip',
);

rep(
  `        return {
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
        };`,
  `        const summary={
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
        return (typeof CCHelpers!=='undefined'&&CCHelpers.localizeHeaderSurface)?CCHelpers.localizeHeaderSurface(summary):summary;`,
  'headerSummary localize',
);

rep(
  `        if(detail) base.explanation=(base.explanation+' ('+String(detail)+')').trim();
        return base;
      },
      surfaceFetchStateMessage(state, detail){`,
  `        if(detail) base.explanation=(base.explanation+' ('+String(detail)+')').trim();
        return (typeof CCHelpers!=='undefined'&&CCHelpers.localizeFetchStateCopy)?CCHelpers.localizeFetchStateCopy(base):base;
      },
      surfaceFetchStateMessage(state, detail){`,
  'surfaceFetchStateCopy localize',
);

rep(
  `        let detail=String(this.playbookCardPrimaryBlocker(r)||'').trim();
        const norm=s=>String(s||'').toUpperCase().replace(/[^A-Z0-9]+/g,' ').trim();`,
  `        let detail=String(this.playbookCardPrimaryBlocker(r)||'').trim();
        if(typeof CCHelpers!=='undefined'&&CCHelpers.playbookCardGateLine){
          return CCHelpers.playbookCardGateLine(status,detail);
        }
        const norm=s=>String(s||'').toUpperCase().replace(/[^A-Z0-9]+/g,' ').trim();`,
  'playbookCardGateLine helper',
);

// tab labels
const tabRe = [
  [/\{id:'guide',icon:'[^']*',label:'Guide'\}/g, "{id:'guide',icon:'📖',label:'Guide · 指南'}"],
  [/\{id:'today',icon:'[^']*',label:'Dashboard'\}/g, "{id:'today',icon:'🎯',label:'Dashboard · 看板'}"],
  [/\{id:'signals',icon:'[^']*',label:'Playbook'\}/g, "{id:'signals',icon:'📋',label:'Playbook · 候選'}"],
  [/\{id:'scanners',icon:'[^']*',label:'Discovery'\}/g, "{id:'scanners',icon:'🔬',label:'Discovery · 掃描'}"],
  [/\{id:'portfolio',icon:'[^']*',label:'Portfolio[^']*'\}/g, "{id:'portfolio',icon:'💼',label:'Portfolio · 持倉'}"],
  [/\{id:'dossier',icon:'[^']*',label:'[^']*Dossier'\}/g, "{id:'dossier',icon:'🔍',label:'Dossier · 研究檔'}"],
  [/\{id:'funds',icon:'[^']*',label:'Funds'\}/g, "{id:'funds',icon:'💼',label:'Funds · 策略'}"],
  [/\{id:'flow',icon:'[^']*',label:'Flow'\}/g, "{id:'flow',icon:'💧',label:'Flow · 流量'}"],
  [/\{id:'rs',icon:'[^']*',label:'RS[^']*'\}/g, "{id:'rs',icon:'📈',label:'RS · 相對強度'}"],
  [/\{id:'command',icon:'[^']*',label:'Command[^']*advanced',hidden_from_primary_nav:true\}/g, "{id:'command',icon:'🖥',label:'Command · 進階',hidden_from_primary_nav:true}"],
  [/\{id:'notrade',icon:'[^']*',label:'Rejections'\}/g, "{id:'notrade',icon:'🚫',label:'Rejections · 拒絕'}"],
  [/\{id:'ops',icon:'[^']*',label:'Ops'\}/g, "{id:'ops',icon:'⚙️',label:'Ops · 運行'}"],
  [/\{id:'ibkr',icon:'[^']*',label:'IBKR'\}/g, "{id:'ibkr',icon:'⚡',label:'IBKR · 券商'}"],
  [/\{id:'btlab',icon:'[^']*',label:'Backtest[^']*'\}/g, "{id:'btlab',icon:'🧪',label:'Backtest · 回測'}"],
  [/\{id:'stratlab',icon:'[^']*',label:'Strategy Lab'\}/g, "{id:'stratlab',icon:'📊',label:'Strategy Lab · 策略實驗'}"],
];
for (const [re, sub] of tabRe) {
  if (re.test(h)) {
    h = h.replace(re, sub);
    n++;
    console.log('ok: tab', sub.match(/label:'([^']+)/)?.[1]);
  }
}

h = h.replace(
  /x-text="'Upgrade[^']*'\+playbookCardUpgradeTrigger\(r\)"/g,
  "x-text=\"'升級條件 · Upgrade · '+playbookCardUpgradeTrigger(r)\"",
);

fs.writeFileSync(INDEX, h);
console.log('patched', n, 'blocks in index.html');
