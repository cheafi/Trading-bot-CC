#!/usr/bin/env node
/**
 * Surface authority contract verifier — per-surface PASS/FAIL + banned phrase scan.
 * Usage: node scripts/verify-surface-authority-contract.mjs
 */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const index = readFileSync(join(root, 'src/api/templates/index.html'), 'utf8');
const helpers = readFileSync(join(root, 'src/api/static/cc-helpers.js'), 'utf8');
const guide = readFileSync(join(root, 'src/api/templates/cc/partials/guide.html'), 'utf8');

function loadContract() {
  const raw = execFileSync(
    'python3',
    [
      '-c',
      'import json; from src.services.surface_authority_contract import export_contract_json; print(json.dumps(export_contract_json()))',
    ],
    { cwd: root, encoding: 'utf8' },
  );
  return JSON.parse(raw.trim());
}

const contract = loadContract();
const { global_banned_phrases: globalBanned, whitelist, surfaces, priority_test_surfaces: priority } = contract;

const MARKERS = {
  guide: "tab==='guide'",
  today: "tab==='today'",
  playbook: 'data-cc="playbook-surface"',
  discovery: 'data-cc="discovery-surface"',
  dossier: "tab==='dossier'",
  portfolio: "tab==='portfolio'",
  command: "tab==='command'",
  stratlab: "tab==='stratlab'",
  time_travel: 'replayModeActive()',
  funds: "tab==='funds'",
  flow: "tab==='flow'",
  rs: "tab==='rs'",
  notrade: "tab==='notrade'",
  ops: "tab==='ops'",
  ibkr: "tab==='ibkr'",
  btlab: "tab==='btlab'",
};

function surfaceChunk(marker, endMarker) {
  const start = index.indexOf(marker);
  if (start < 0) return '';
  const end = endMarker ? index.indexOf(endMarker, start) : index.indexOf('<!-- SURFACE:', start);
  return index.slice(start, end > start ? end : start + 12000);
}

const CHUNK_ENDS = {
  portfolio: '<!-- SURFACE 4:',
  playbook: "x-show=\"tab==='dossier'\"",
};

function isWhitelisted(chunk, phrase) {
  const lower = chunk.toLowerCase();
  if (!lower.includes(phrase.toLowerCase())) return false;
  for (const ctx of whitelist) {
    if (lower.includes(ctx.toLowerCase())) return true;
  }
  if (lower.includes('illustrative examples only')) return true;
  if (lower.includes('removeTradeLanguageWhenBlocked')) return true;
  return false;
}

function checkViewmodel(chunk, vm, label, extraHaystack = '') {
  if (!vm) return [];
  const hay = chunk + extraHaystack;
  const inChunk = hay.includes(vm) || hay.includes(`${vm}()`);
  const inHelpers = helpers.includes(vm);
  if (!inChunk && !inHelpers) {
    return [`${label}: missing viewmodel/helper "${vm}"`];
  }
  return [];
}

function checkBanned(chunk, phrases, label, { caseSensitive = false } = {}) {
  const hits = [];
  for (const phrase of phrases) {
    if (!chunk) continue;
    if (isWhitelisted(chunk, phrase)) continue;
    const hay = caseSensitive ? chunk : chunk.toLowerCase();
    const needle = caseSensitive ? phrase : phrase.toLowerCase();
    if (hay.includes(needle)) {
      hits.push(`${label}: banned phrase "${phrase}"`);
    }
  }
  return hits;
}

const results = [];
const errors = [];

if (Object.keys(surfaces).length !== 16) {
  errors.push(`Contract must define 16 surfaces, got ${Object.keys(surfaces).length}`);
}

for (const [key, spec] of Object.entries(surfaces)) {
  const label = spec.ui_label || key;
  const marker = MARKERS[key];
  const surfaceErrors = [];

  if (!marker) {
    surfaceErrors.push('missing chunk marker');
  } else if (key !== 'time_travel' && !index.includes(marker)) {
    surfaceErrors.push(`marker "${marker}" not in index.html`);
  }

  const chunk = marker
    ? key === 'guide'
      ? guide
      : surfaceChunk(marker, CHUNK_ENDS[key])
    : '';
  if (key === 'command') {
    const agentChunk = surfaceChunk('data-cc="agent-page-default"');
    if (!agentChunk) surfaceErrors.push('agent sub-surface marker missing');
  }

  surfaceErrors.push(...checkBanned(chunk, spec.banned_phrases || [], label, {
    caseSensitive: key === 'portfolio',
  }));
  surfaceErrors.push(...checkViewmodel(chunk, spec.viewmodel, label, key === 'guide' || key === 'today' ? index : ''));

  if (spec.source_helper && !helpers.includes(spec.source_helper)) {
    const pyHelpers = [
      'build_operator_block',
      'resolve_dossier_mode',
      'build_portfolio_risk_view_model',
      'build_strategy_lab_page_state',
      'build_research_surface_block',
      'build_header_summary',
      'resolve_engine_state',
      'guide_mode_strip',
    ];
    if (!pyHelpers.includes(spec.source_helper) && !helpers.includes(spec.source_helper)) {
      surfaceErrors.push(`source helper "${spec.source_helper}" not found in cc-helpers.js`);
    }
  }

  const status = surfaceErrors.length ? 'FAIL' : 'PASS';
  results.push({ key, label, status, issues: surfaceErrors });
  errors.push(...surfaceErrors.map((e) => `[${label}] ${e}`));
}

// Priority surfaces must all PASS
for (const key of priority) {
  const row = results.find((r) => r.key === key);
  if (!row) errors.push(`priority surface missing from results: ${key}`);
  else if (row.status !== 'PASS') errors.push(`priority surface ${key} FAILED`);
}

// Global banned scan on runtime trust + playbook (not guide illustrations)
const trust = index.split('trust-strip-tier-primary', 1)[1]?.split('<!--', 1)[0] || '';
const playbook = surfaceChunk('data-cc="playbook-surface"');
const runtime = trust + playbook;
for (const phrase of globalBanned) {
  if (isWhitelisted(runtime, phrase)) continue;
  if (runtime.toLowerCase().includes(phrase.toLowerCase())) {
    errors.push(`GLOBAL: banned "${phrase}" in runtime bindings`);
  }
}

// Alpha QA collapsed inside Decision Quality only — no deploy authority from QA
const decisionQualityChunk = surfaceChunk('data-cc="decision-quality-panel"', '<!-- ── Naval clarity strip');
const alphaQualityChunk = (() => {
  const start = index.indexOf('data-cc="alpha-quality-panel"');
  if (start < 0) return '';
  const end = index.indexOf('</details>', start);
  return index.slice(start, end > start ? end + 10 : start + 2000);
})();
const alphaReviewChunk = (() => {
  const start = index.indexOf('data-cc="alpha-review-panel"');
  if (start < 0) return '';
  const end = index.indexOf('</details>', start);
  return index.slice(start, end > start ? end + 10 : start + 2500);
})();
const discoveryChunk = surfaceChunk('data-cc="discovery-surface"', '<!-- SURFACE:');
if (!decisionQualityChunk.includes('data-cc="decision-quality-panel"')) {
  errors.push('[Dashboard] missing decision-quality-panel marker');
}
if (!alphaQualityChunk.includes('data-cc="alpha-quality-panel"')) {
  errors.push('[Dashboard] Alpha QA must live inside collapsed Decision Quality details');
}
if (!/:open="false"/.test(decisionQualityChunk)) {
  errors.push('[Dashboard] Decision Quality must default collapsed');
}
if (/may_authorize_deploy/i.test(alphaQualityChunk) && !/authority effect:\s*none/i.test(alphaQualityChunk)) {
  errors.push('[Dashboard] Alpha QA must declare authority effect none');
}
if (/validated/i.test(alphaQualityChunk) && !/learning/i.test(alphaQualityChunk)) {
  errors.push('[Dashboard] Alpha QA: no validated without learning/sample guard');
}
if (!/allow_green_ui/.test(alphaQualityChunk)) {
  errors.push('[Dashboard] Alpha QA: missing overfit green UI guard');
}
if (!alphaReviewChunk.includes('data-cc="alpha-review-panel"')) {
  errors.push('[Dashboard] Alpha Review must live inside collapsed Alpha Quality details');
}
if (!/:open="false"/.test(alphaReviewChunk)) {
  errors.push('[Dashboard] Alpha Review must default collapsed');
}
if (/@click.*deploy|data-cc-nav="deploy"|Deploy now/i.test(alphaReviewChunk)) {
  errors.push('[Dashboard] Alpha Review UI must not expose deploy actions');
}
if (/auto.?loosen/i.test(alphaReviewChunk)) {
  errors.push('[Dashboard] Alpha Review: banned auto-loosen copy');
}
if (!/authority effect:\s*none/i.test(alphaReviewChunk)) {
  errors.push('[Dashboard] Alpha Review must declare authority effect none');
}
try {
  const arItems = readFileSync(join(root, 'src/services/alpha_review_items.py'), 'utf8');
  if (!/deploy/.test(arItems) || !/auto_loosen/.test(arItems)) {
    errors.push('[Alpha Review] review items must block deploy and auto_loosen');
  }
} catch (e) {
  errors.push(`[Alpha Review] items source read failed: ${e.message}`);
}
try {
  const govSrc = readFileSync(join(root, 'src/services/capital_allocation_governor.py'), 'utf8');
  if (!/can_loosen_automatically[\s\S]{0,40}False/.test(govSrc)) {
    errors.push('[Governor] QA can_loosen_automatically must be false');
  }
  if (/may_authorize_deploy\s*=\s*True/.test(govSrc)) {
    errors.push('[Governor] QA must not authorize deploy');
  }
} catch (e) {
  errors.push(`[Governor] source read failed: ${e.message}`);
}
try {
  const ofSrc = readFileSync(join(root, 'src/services/overfit_guard.py'), 'utf8');
  if (!/label_cap/.test(ofSrc) || !/promising|learning/.test(ofSrc)) {
    errors.push('[Overfit] must cap success labels at promising/learning');
  }
} catch (e) {
  errors.push(`[Overfit] source read failed: ${e.message}`);
}

// Threshold Governance — diagnostic only, no research-surface controls
const opsThresholdChunk = (() => {
  const start = index.indexOf('data-cc="ops-threshold-governance-panel"');
  if (start < 0) return '';
  const end = index.indexOf('<!-- ERROR LOG -->', start);
  return index.slice(start, end > start ? end : start + 4000);
})();
if (!opsThresholdChunk.includes('data-cc="ops-threshold-governance-panel"')) {
  errors.push('[Ops] Threshold Governance diagnostic panel missing');
}
if (!/:open="false"/.test(opsThresholdChunk)) {
  errors.push('[Ops] Threshold Governance must default collapsed');
}
if (/@click.*deploy|promote_to_live|Deploy now/i.test(opsThresholdChunk)) {
  errors.push('[Ops] Threshold Governance: banned deploy/promote actions');
}
if (/auto.?loosen/i.test(opsThresholdChunk)) {
  errors.push('[Ops] Threshold Governance: banned auto-loosen copy');
}
if (!/threshold_review_line|Threshold Review:/.test(alphaReviewChunk)) {
  errors.push('[Dashboard] Alpha Review: missing compact Threshold Review status line');
}
if (/threshold.*control|loosen.*threshold|@click.*threshold/i.test(discoveryChunk)) {
  errors.push('[Discovery] banned threshold controls on research surface');
}
try {
  const regSrc = readFileSync(join(root, 'src/services/threshold_registry.py'), 'utf8');
  if (!/can_auto_loosen\s*=\s*False/.test(regSrc)) {
    errors.push('[Threshold Registry] can_auto_loosen must be false globally');
  }
  const idCount = (regSrc.match(/^\s+"[a-z]+\.[a-z_]+": _def\(/gm) || []).length;
  if (idCount < 16) {
    errors.push(`[Threshold Registry] expected 16 threshold IDs, found ${idCount}`);
  }
} catch (e) {
  errors.push(`[Threshold Registry] source read failed: ${e.message}`);
}

// Optional live API check
let apiNote = 'skipped (server down)';
try {
  const res = await fetch('http://127.0.0.1:8001/api/v7/today', { signal: AbortSignal.timeout(2000) });
  if (res.ok) {
    const data = await res.json();
    const tier = data?.deploy_authority_tier || data?.system_truth?.deploy_authority_tier;
    apiNote = tier ? `live tier=${tier}` : 'live OK (no tier field)';
  }
} catch {
  /* server optional */
}

console.log('=== SURFACE AUTHORITY CONTRACT ===');
for (const row of results) {
  const mark = row.status === 'PASS' ? '✓' : '✗';
  console.log(`${mark} ${row.label} (${row.key}): ${row.status}`);
  for (const issue of row.issues) console.log(`    - ${issue}`);
}
console.log(`\nAPI /api/v7/today: ${apiNote}`);
console.log(`Surfaces: ${results.filter((r) => r.status === 'PASS').length}/${results.length} PASS`);

if (errors.length) {
  console.error('\nverify-surface-authority-contract FAILED:\n' + errors.map((e) => '  - ' + e).join('\n'));
  process.exit(1);
}

console.log('\nverify-surface-authority-contract OK — 16 surfaces enforced');
