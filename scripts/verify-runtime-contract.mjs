#!/usr/bin/env node
/**
 * Runtime render contract — release gate for surface authority product law.
 * Usage: node scripts/verify-runtime-contract.mjs
 */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const index = readFileSync(join(root, 'src/api/templates/index.html'), 'utf8');
const helpers = readFileSync(join(root, 'src/api/static/cc-helpers.js'), 'utf8');
const guide = readFileSync(join(root, 'src/api/templates/cc/partials/guide.html'), 'utf8');

const gates = {
  'RUNTIME CONTRACT': [],
  'SURFACE AUTHORITY': [],
  'GUIDE MODEL': [],
  'PLAYBOOK AUTHORITY': [],
  'DOSSIER CONFIRM ONLY': [],
  'PORTFOLIO RISK REVIEW': [],
};

function fail(gate, msg) {
  gates[gate].push(msg);
}

function ban(gate, chunk, pattern, label) {
  if (pattern.test(chunk)) fail(gate, label);
}

const discoveryChunk = (() => {
  const start = index.indexOf('data-cc="discovery-surface"');
  if (start < 0) return '';
  const end = index.indexOf('<!-- SURFACE:', start);
  return index.slice(start, end > start ? end : undefined);
})();
const header = index.split('</header>', 1)[0] || '';
const trustPrimary = (() => {
  const start = index.indexOf('trust-strip-tier-primary');
  if (start < 0) return '';
  const sub = index.slice(start);
  const end = sub.indexOf('</div>');
  return end > 0 ? sub.slice(0, end) : sub;
})();
const guideChunk = (() => {
  const start = index.indexOf("tab==='guide'");
  if (start < 0) return guide;
  const end = index.indexOf('<!-- SURFACE:', start);
  return index.slice(start, end > start ? end : start + 8000);
})();
const portfolioChunk = (() => {
  const start = index.indexOf("tab==='portfolio'");
  if (start < 0) return '';
  const end = index.indexOf('<!-- SURFACE 4:', start);
  return index.slice(start, end > start ? end : undefined);
})();
const playbookChunk = (() => {
  const start = index.indexOf('data-cc="playbook-surface"');
  if (start < 0) return '';
  const end = index.indexOf("x-show=\"tab==='dossier'\"", start);
  return index.slice(start, end > start ? end : undefined);
})();
const dossierChunk = (() => {
  const start = index.indexOf("tab==='dossier'");
  if (start < 0) return '';
  const end = index.indexOf('<!-- SURFACE', start + 20);
  return index.slice(start, end > start ? end : start + 12000);
})();

// ── RUNTIME CONTRACT ──
ban('RUNTIME CONTRACT', discoveryChunk, /Freshness:\s*live/i, 'Discovery: unscoped "Freshness: live"');
ban('RUNTIME CONTRACT', discoveryChunk, /h\.freshness\|\|'live'/i, 'Discovery: raw h.freshness||live pill');
ban('RUNTIME CONTRACT', discoveryChunk, /brief fallback/i, 'Discovery: brief fallback copy');
ban('RUNTIME CONTRACT', discoveryChunk, /ENGINE ON/i, 'Discovery: raw ENGINE ON');
ban('RUNTIME CONTRACT', header, /['"]DATA ['"]\s*\+?\s*freshness/i, 'Header: unscoped DATA + freshness binding');
ban('RUNTIME CONTRACT', header, /\bDATA FRESH\b|\bDATA STALE\b/, 'Header: unscoped DATA FRESH/STALE pill');
ban('RUNTIME CONTRACT', helpers, /['"]DATA ['"]\s*\+/i, 'cc-helpers: unscoped DATA + tier binding');
ban('RUNTIME CONTRACT', helpers, /\bDATA FRESH\b|\bDATA STALE\b/, 'cc-helpers: unscoped DATA FRESH/STALE pill');
ban('RUNTIME CONTRACT', helpers, /['"]ENGINE ON['"]|return "ENGINE ON"/i, 'cc-helpers: raw ENGINE ON label');
ban('RUNTIME CONTRACT', discoveryChunk, /\bENGINE ON\b|\bENGINE OFF\b/, 'Discovery: raw ENGINE ON/OFF');
if (!/discoveryScannerRunLabel/.test(discoveryChunk)) {
  fail('RUNTIME CONTRACT', 'Discovery: missing discoveryScannerRunLabel');
}
if (!/Scanner run:/i.test(helpers)) {
  fail('RUNTIME CONTRACT', 'cc-helpers: missing Scanner run scoped label');
}
if (!/shellTruthViewModel/.test(helpers)) {
  fail('RUNTIME CONTRACT', 'cc-helpers: missing shellTruthViewModel');
}
if (!/runtimeEngineHeaderLabel/.test(helpers)) {
  fail('RUNTIME CONTRACT', 'cc-helpers: missing runtimeEngineHeaderLabel');
}
if (!/runtimePrimaryStateLine\(\)/.test(trustPrimary)) {
  fail('RUNTIME CONTRACT', 'Trust strip: primary must use runtimePrimaryStateLine()');
}
if (!/discoveryFunnelPanel\(\)\.status_line/.test(discoveryChunk)) {
  fail('RUNTIME CONTRACT', 'Discovery funnel: missing STATUS row');
}

// ── SURFACE AUTHORITY ──
try {
  const raw = execFileSync(
    'python3',
    [
      '-c',
      'import json; from src.services.surface_authority_contract import export_contract_json; print(json.dumps(export_contract_json()))',
    ],
    { cwd: root, encoding: 'utf8' },
  );
  const contract = JSON.parse(raw.trim());
  if (Object.keys(contract.surfaces).length !== 16) {
    fail('SURFACE AUTHORITY', `Expected 16 surfaces, got ${Object.keys(contract.surfaces).length}`);
  }
  if (!/headerSummary\(\)\{/.test(index)) {
    fail('SURFACE AUTHORITY', 'index.html: missing headerSummary() surface ownership');
  }
} catch (e) {
  fail('SURFACE AUTHORITY', `contract load failed: ${e.message}`);
}

// ── GUIDE MODEL ──
if (!/GUIDE MODE · Reference only · Decision surfaces suspended/.test(index)) {
  fail('GUIDE MODEL', 'Guide: missing canonical authority strip');
}
if (/TRADE LIST/.test(guide)) {
  fail('GUIDE MODEL', 'Guide: banned TRADE LIST');
}
if (/decision card/i.test(guide)) {
  fail('GUIDE MODEL', 'Guide: banned decision card');
}
if (/pilot half-size/i.test(guide)) {
  fail('GUIDE MODEL', 'Guide: banned pilot half-size default wording');
}
if (!/PILOT\/TRADE labels on blocked days are review-only/i.test(guide)) {
  fail('GUIDE MODEL', 'Guide: missing PILOT review-only clarification');
}
if (!/structure review surface|structure confirmation/i.test(guide)) {
  fail('GUIDE MODEL', 'Guide: missing dossier structure confirmation wording');
}
if (guideChunk.split('Decision surfaces suspended').length - 1 > 2) {
  fail('GUIDE MODEL', 'Guide: duplicate authority strip copy');
}

// ── PLAYBOOK AUTHORITY ──
ban('PLAYBOOK AUTHORITY', playbookChunk, /Deploy gate open/i, 'Playbook: banned Deploy gate open');
ban('PLAYBOOK AUTHORITY', playbookChunk, /BOARD POSTURE TRADE/i, 'Playbook: banned BOARD POSTURE TRADE');
ban('PLAYBOOK AUTHORITY', playbookChunk, /Current:\s*TRADE/i, 'Playbook: banned Current: TRADE');
ban('PLAYBOOK AUTHORITY', playbookChunk, /x-text="canonicalRegimeLine\(\)"/i, 'Playbook: raw canonicalRegimeLine binding');
ban('PLAYBOOK AUTHORITY', playbookChunk, /x-text="today7\.tradeability/i, 'Playbook: raw today7.tradeability binding');
ban('PLAYBOOK AUTHORITY', playbookChunk, /unifiedTruthStripLine\(\)/i, 'Playbook: raw unifiedTruthStripLine in trust strip');
if (!/playbookOperatorView\(\)/.test(playbookChunk)) {
  fail('PLAYBOOK AUTHORITY', 'Playbook: missing playbookOperatorView() wiring');
}
if (!/playbookQualificationDisplay\(\)/.test(playbookChunk)) {
  fail('PLAYBOOK AUTHORITY', 'Playbook: missing playbookQualificationDisplay() wiring');
}
if (!/playbookAuthorityViewModel/.test(helpers)) {
  fail('PLAYBOOK AUTHORITY', 'cc-helpers: missing playbookAuthorityViewModel');
}

// ── DOSSIER CONFIRM ONLY ──
if (!/Confirm-only · 僅結構確認/.test(dossierChunk) && !/Confirm-only · 僅結構確認/.test(guide)) {
  fail('DOSSIER CONFIRM ONLY', 'Dossier: missing confirm-only label');
}
if (/decision card/i.test(dossierChunk)) {
  fail('DOSSIER CONFIRM ONLY', 'Dossier: banned decision card in live surface');
}
if (!/cardShowsStructureReference|Structure reference only|structure review/i.test(helpers + dossierChunk)) {
  fail('DOSSIER CONFIRM ONLY', 'Dossier: missing structure reference wiring');
}

// ── PORTFOLIO RISK REVIEW ──
ban('PORTFOLIO RISK REVIEW', portfolioChunk, /Active sleeves/i, 'Portfolio: banned "Active sleeves" in default');
ban('PORTFOLIO RISK REVIEW', portfolioChunk, /Seed Demo Book/, 'Portfolio: banned "Seed Demo Book" in default');
ban('PORTFOLIO RISK REVIEW', portfolioChunk, /Closed-Trade Ledger/i, 'Portfolio: banned "Closed-Trade Ledger"');
ban('PORTFOLIO RISK REVIEW', portfolioChunk, /Method Not Allowed/i, 'Portfolio: raw Method Not Allowed');
ban('PORTFOLIO RISK REVIEW', portfolioChunk, /CRITICAL RISK EVENT/, 'Portfolio: CRITICAL RISK EVENT literal in template');
if (!/pfRiskVM\(\)/.test(portfolioChunk)) {
  fail('PORTFOLIO RISK REVIEW', 'Portfolio: missing pfRiskVM()');
}
if (!/Historical Journal/.test(portfolioChunk)) {
  fail('PORTFOLIO RISK REVIEW', 'Portfolio: missing Historical Journal label');
}
if (!/Sleeve Research/.test(portfolioChunk)) {
  fail('PORTFOLIO RISK REVIEW', 'Portfolio: missing Sleeve Research label');
}
if (!/Broker truth unavailable/.test(portfolioChunk)) {
  fail('PORTFOLIO RISK REVIEW', 'Portfolio: missing broker truth unavailable banner');
}
if (!/portfolioRiskViewModel/.test(helpers)) {
  fail('PORTFOLIO RISK REVIEW', 'cc-helpers: missing portfolioRiskViewModel');
}

const allErrors = Object.values(gates).flat();
console.log('=== RELEASE GATE: verify-runtime-contract ===');
for (const [name, issues] of Object.entries(gates)) {
  const status = issues.length ? 'FAIL' : 'PASS';
  console.log(`[${status}] ${name}${issues.length ? ` (${issues.length})` : ''}`);
  for (const issue of issues) console.log(`  - ${issue}`);
}

if (allErrors.length) {
  console.error(`\nverify-runtime-contract FAILED — ${allErrors.length} issue(s)`);
  process.exit(1);
}

console.log('\nverify-runtime-contract OK — all release gates PASS');
