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
  'ALPHA QUALITY CONTRACT': [],
  'ALPHA REVIEW CONTRACT': [],
  'THRESHOLD GOVERNANCE CONTRACT': [],
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
const decisionQualityChunk = (() => {
  const start = index.indexOf('data-cc="decision-quality-panel"');
  if (start < 0) return '';
  const end = index.indexOf('<!-- ── Naval clarity strip', start);
  return index.slice(start, end > start ? end : start + 4000);
})();
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
const thresholdGovChunk = (() => {
  const start = index.indexOf('data-cc="ops-threshold-governance-panel"');
  if (start < 0) return '';
  const end = index.indexOf('</details>', start);
  return index.slice(start, end > start ? end + 10 : start + 3500);
})();
const dashboardChunk = (() => {
  const start = index.indexOf('data-cc="today-surface"');
  if (start < 0) return '';
  const end = index.indexOf('<!-- SURFACE: OPPORTUNITY SCANNER', start);
  return index.slice(start, end > start ? end : undefined);
})();

function scanVisibleUtf8Corruption(chunk, gate, label) {
  if (!chunk) return;
  const lines = chunk.split('\n');
  for (const line of lines) {
    if (/x-text="'[?] /.test(line)) {
      fail(gate, `${label}: corrupted x-text prefix ${line.trim().slice(0, 100)}`);
    }
    const xtextMatches = line.matchAll(/x-text="([^"]*)"/g);
    for (const m of xtextMatches) {
      const expr = m[1];
      if (/['"][?][?]/.test(expr) || /[?][?]['"]/.test(expr)) {
        fail(gate, `${label}: x-text literal ?? ${line.trim().slice(0, 100)}`);
      }
    }
    if (/>\?\?[^?<]/.test(line)) {
      fail(gate, `${label}: visible ?? ${line.trim().slice(0, 100)}`);
    }
    if (/>\? [A-Za-z]/.test(line) && !/Can you fill cleanly/.test(line)) {
      fail(gate, `${label}: corrupted visible label ${line.trim().slice(0, 100)}`);
    }
  }
}

// ── RUNTIME CONTRACT ──
scanVisibleUtf8Corruption(dashboardChunk, 'RUNTIME CONTRACT', 'Dashboard');
ban('RUNTIME CONTRACT', dashboardChunk, /x-text="'[?] /, 'Dashboard: corrupted UTF-8 prefix in x-text');
ban('RUNTIME CONTRACT', dashboardChunk, />\?\?[^?<]/, 'Dashboard: visible ?? in markup');
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

// ── ALPHA QUALITY CONTRACT ──
if (!/data-cc="alpha-quality-panel"/.test(index)) {
  fail('ALPHA QUALITY CONTRACT', 'Dashboard: missing collapsed ALPHA QUALITY panel inside Decision Quality');
}
if (!/ALPHA QUALITY/i.test(alphaQualityChunk)) {
  fail('ALPHA QUALITY CONTRACT', 'Dashboard: missing ALPHA QUALITY section label');
}
if (!/:open="false"/.test(decisionQualityChunk)) {
  fail('ALPHA QUALITY CONTRACT', 'Decision Quality: must remain collapsed by default');
}
ban('ALPHA QUALITY CONTRACT', alphaQualityChunk, /may_authorize_deploy\s*:\s*true/i, 'Alpha QA: banned may_authorize_deploy true');
ban('ALPHA QUALITY CONTRACT', alphaQualityChunk, /authority_effect\s*:\s*['"]promote/i, 'Alpha QA: banned authority promotion');
ban('ALPHA QUALITY CONTRACT', alphaQualityChunk, /validated/i, 'Alpha QA: banned validated label without sample guard in UI');
if (!/authority effect:\s*none/i.test(alphaQualityChunk)) {
  fail('ALPHA QUALITY CONTRACT', 'Alpha QA: missing authority effect none');
}
if (!/learning/i.test(alphaQualityChunk)) {
  fail('ALPHA QUALITY CONTRACT', 'Alpha QA: missing learning mode fallback');
}
if (!/overfit/i.test(alphaQualityChunk)) {
  fail('ALPHA QUALITY CONTRACT', 'Alpha QA: missing overfit risk display');
}
if (!/allow_green_ui/.test(alphaQualityChunk)) {
  fail('ALPHA QUALITY CONTRACT', 'Alpha QA: missing overfit green UI guard');
}
try {
  const govSrc = readFileSync(join(root, 'src/services/capital_allocation_governor.py'), 'utf8');
  if (!/can_loosen_automatically[\s\S]{0,40}False/.test(govSrc)) {
    fail('ALPHA QUALITY CONTRACT', 'Governor: can_loosen_automatically must be false');
  }
  if (!/qa_adjustment/.test(govSrc)) {
    fail('ALPHA QUALITY CONTRACT', 'Governor: missing qa_adjustment output');
  }
} catch (e) {
  fail('ALPHA QUALITY CONTRACT', `Governor source check failed: ${e.message}`);
}
try {
  const oqeSrc = readFileSync(join(root, 'src/services/opportunity_quality_engine.py'), 'utf8');
  if (!/alpha_quality/.test(oqeSrc)) {
    fail('ALPHA QUALITY CONTRACT', 'Decision quality dashboard: missing alpha_quality wiring');
  }
  if (/state\s*=\s*["']validated["']/.test(oqeSrc) && !/MIN_VALIDATED_SAMPLE|sample_size|n\s*>=/.test(oqeSrc)) {
    fail('ALPHA QUALITY CONTRACT', 'Decision quality: validated without sample guard');
  }
} catch (e) {
  fail('ALPHA QUALITY CONTRACT', `opportunity_quality_engine check failed: ${e.message}`);
}

// ── ALPHA REVIEW CONTRACT ──
if (!/data-cc="alpha-review-panel"/.test(index)) {
  fail('ALPHA REVIEW CONTRACT', 'Dashboard: missing collapsed ALPHA REVIEW panel inside Alpha Quality');
}
if (!/ALPHA REVIEW/i.test(alphaReviewChunk)) {
  fail('ALPHA REVIEW CONTRACT', 'Dashboard: missing ALPHA REVIEW section label');
}
if (!/:open="false"/.test(alphaReviewChunk)) {
  fail('ALPHA REVIEW CONTRACT', 'Alpha Review: must remain collapsed by default');
}
ban('ALPHA REVIEW CONTRACT', alphaReviewChunk, /@click.*deploy|data-cc-nav="deploy"|Deploy now/i, 'Alpha Review: banned deploy action in review UI');
ban('ALPHA REVIEW CONTRACT', alphaReviewChunk, /auto.?loosen/i, 'Alpha Review: banned auto-loosen in review UI');
ban('ALPHA REVIEW CONTRACT', alphaReviewChunk, /may_authorize_deploy\s*:\s*true/i, 'Alpha Review: banned may_authorize_deploy true');
if (!/authority effect:\s*none/i.test(alphaReviewChunk)) {
  fail('ALPHA REVIEW CONTRACT', 'Alpha Review: missing authority effect none');
}
if (!/human review/i.test(alphaReviewChunk)) {
  fail('ALPHA REVIEW CONTRACT', 'Alpha Review: missing human review count display');
}
try {
  const arSrc = readFileSync(join(root, 'src/services/alpha_review_service.py'), 'utf8');
  if (!/authority_effect\s*=\s*["']none["']/.test(arSrc) && !/"authority_effect":\s*"none"/.test(arSrc)) {
    fail('ALPHA REVIEW CONTRACT', 'alpha_review_service: must set authority_effect none');
  }
  if (!/may_authorize_deploy/.test(arSrc)) {
    fail('ALPHA REVIEW CONTRACT', 'alpha_review_service: missing may_authorize_deploy guard');
  }
  if (/successful/.test(arSrc) && !/cost_adj_positive|overfit_pass|min_sample/.test(arSrc)) {
    fail('ALPHA REVIEW CONTRACT', 'Alpha Review: no successful without sample + cost-adj + overfit pass');
  }
} catch (e) {
  fail('ALPHA REVIEW CONTRACT', `alpha_review_service check failed: ${e.message}`);
}
try {
  const itemsSrc = readFileSync(join(root, 'src/services/alpha_review_items.py'), 'utf8');
  if (!/BLOCKED_ACTIONS/.test(itemsSrc) || !/deploy/.test(itemsSrc) || !/auto_loosen/.test(itemsSrc)) {
    fail('ALPHA REVIEW CONTRACT', 'alpha_review_items: must block deploy and auto_loosen');
  }
} catch (e) {
  fail('ALPHA REVIEW CONTRACT', `alpha_review_items check failed: ${e.message}`);
}
try {
  const oqeSrc2 = readFileSync(join(root, 'src/services/opportunity_quality_engine.py'), 'utf8');
  if (!/alpha_review/.test(oqeSrc2)) {
    fail('ALPHA REVIEW CONTRACT', 'Decision quality dashboard: missing alpha_review wiring');
  }
} catch (e) {
  fail('ALPHA REVIEW CONTRACT', `opportunity_quality_engine alpha_review check failed: ${e.message}`);
}

// ── THRESHOLD GOVERNANCE CONTRACT ──
if (!/data-cc="ops-threshold-governance-panel"/.test(index)) {
  fail('THRESHOLD GOVERNANCE CONTRACT', 'Ops: missing collapsed Threshold Governance diagnostic panel');
}
if (!/:open="false"/.test(thresholdGovChunk)) {
  fail('THRESHOLD GOVERNANCE CONTRACT', 'Threshold Governance: must remain collapsed by default');
}
ban('THRESHOLD GOVERNANCE CONTRACT', thresholdGovChunk, /@click.*deploy|promote_to_live|Deploy now/i, 'Threshold Governance: banned deploy/promote live in Ops UI');
ban('THRESHOLD GOVERNANCE CONTRACT', thresholdGovChunk, /auto.?loosen/i, 'Threshold Governance: banned auto-loosen in Ops UI');
ban('THRESHOLD GOVERNANCE CONTRACT', dashboardChunk, /threshold.*control|loosen.*threshold|@click.*threshold/i, 'Dashboard: banned threshold controls on research surface');
ban('THRESHOLD GOVERNANCE CONTRACT', discoveryChunk, /threshold.*control|loosen.*threshold|@click.*threshold/i, 'Discovery: banned threshold controls on research surface');
if (!/Threshold Review:/.test(alphaReviewChunk) && !/threshold_review_line/.test(alphaReviewChunk)) {
  fail('THRESHOLD GOVERNANCE CONTRACT', 'Dashboard Alpha Review: missing compact Threshold Review status line');
}
if (!/no live changes/i.test(thresholdGovChunk)) {
  fail('THRESHOLD GOVERNANCE CONTRACT', 'Ops Threshold Governance: missing no live changes copy');
}
try {
  const regSrc = readFileSync(join(root, 'src/services/threshold_registry.py'), 'utf8');
  if (!/can_auto_loosen\s*=\s*False/.test(regSrc)) {
    fail('THRESHOLD GOVERNANCE CONTRACT', 'threshold_registry: can_auto_loosen must be false globally');
  }
} catch (e) {
  fail('THRESHOLD GOVERNANCE CONTRACT', `threshold_registry check failed: ${e.message}`);
}
try {
  const propSrc = readFileSync(join(root, 'src/services/threshold_proposal_service.py'), 'utf8');
  if (!/can_auto_loosen/.test(propSrc) || !/no_live_changes/.test(propSrc)) {
    fail('THRESHOLD GOVERNANCE CONTRACT', 'threshold_proposal_service: missing auto-loosen / no-live guards');
  }
} catch (e) {
  fail('THRESHOLD GOVERNANCE CONTRACT', `threshold_proposal_service check failed: ${e.message}`);
}
try {
  const oqeSrc3 = readFileSync(join(root, 'src/services/opportunity_quality_engine.py'), 'utf8');
  if (!/threshold_governance/.test(oqeSrc3)) {
    fail('THRESHOLD GOVERNANCE CONTRACT', 'Decision quality dashboard: missing threshold_governance wiring');
  }
} catch (e) {
  fail('THRESHOLD GOVERNANCE CONTRACT', `opportunity_quality_engine threshold_governance check failed: ${e.message}`);
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
