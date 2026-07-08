#!/usr/bin/env node
/**
 * Runtime render contract — Discovery scoped freshness + shell truth isolation.
 * Usage: node scripts/verify-runtime-contract.mjs
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const index = readFileSync(join(root, 'src/api/templates/index.html'), 'utf8');
const helpers = readFileSync(join(root, 'src/api/static/cc-helpers.js'), 'utf8');

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

const errors = [];

function ban(chunk, pattern, label) {
  if (pattern.test(chunk)) errors.push(label);
}

ban(discoveryChunk, /Freshness:\s*live/i, 'Discovery: unscoped "Freshness: live"');
ban(discoveryChunk, /h\.freshness\|\|'live'/i, 'Discovery: raw h.freshness||live pill');
ban(discoveryChunk, /brief fallback/i, 'Discovery: brief fallback copy');
ban(discoveryChunk, /ENGINE ON/i, 'Discovery: raw ENGINE ON');
ban(header, /['"]DATA ['"]\s*\+?\s*freshness/i, 'Header: unscoped DATA + freshness binding');
ban(header, /\bDATA FRESH\b|\bDATA STALE\b/, 'Header: unscoped DATA FRESH/STALE pill');
ban(helpers, /['"]DATA ['"]\s*\+/i, 'cc-helpers: unscoped DATA + tier binding');
ban(helpers, /\bDATA FRESH\b|\bDATA STALE\b/, 'cc-helpers: unscoped DATA FRESH/STALE pill');
ban(helpers, /['"]ENGINE ON['"]|return "ENGINE ON"/i, 'cc-helpers: raw ENGINE ON label');
ban(discoveryChunk, /\bENGINE ON\b|\bENGINE OFF\b/, 'Discovery: raw ENGINE ON/OFF');

if (!/discoveryScannerRunLabel/.test(discoveryChunk)) {
  errors.push('Discovery: missing discoveryScannerRunLabel');
}
if (!/Scanner run:/i.test(helpers)) {
  errors.push('cc-helpers: missing Scanner run scoped label');
}
if (!/shellTruthViewModel/.test(helpers)) {
  errors.push('cc-helpers: missing shellTruthViewModel');
}
if (!/runtimeEngineHeaderLabel/.test(helpers)) {
  errors.push('cc-helpers: missing runtimeEngineHeaderLabel');
}
if (!/runtimePrimaryStateLine\(\)/.test(trustPrimary)) {
  errors.push('Trust strip: primary must use runtimePrimaryStateLine()');
}
if (!/discoveryFunnelPanel\(\)\.status_line/.test(discoveryChunk)) {
  errors.push('Discovery funnel: missing STATUS row');
}

ban(portfolioChunk, /Active sleeves/i, 'Portfolio: banned "Active sleeves" in default');
ban(portfolioChunk, /Seed Demo Book/, 'Portfolio: banned "Seed Demo Book" in default');
ban(portfolioChunk, /Closed-Trade Ledger/i, 'Portfolio: banned "Closed-Trade Ledger"');
ban(portfolioChunk, /Method Not Allowed/i, 'Portfolio: raw Method Not Allowed');
ban(portfolioChunk, /CRITICAL RISK EVENT/, 'Portfolio: CRITICAL RISK EVENT literal in template');
if (!/pfRiskVM\(\)/.test(portfolioChunk)) {
  errors.push('Portfolio: missing pfRiskVM()');
}
if (!/Historical Journal/.test(portfolioChunk)) {
  errors.push('Portfolio: missing Historical Journal label');
}
if (!/Sleeve Research/.test(portfolioChunk)) {
  errors.push('Portfolio: missing Sleeve Research label');
}
if (!/Broker truth unavailable/.test(portfolioChunk)) {
  errors.push('Portfolio: missing broker truth unavailable banner');
}
if (!/portfolioRiskViewModel/.test(helpers)) {
  errors.push('cc-helpers: missing portfolioRiskViewModel');
}

ban(playbookChunk, /Deploy gate open/i, 'Playbook: banned Deploy gate open');
ban(playbookChunk, /BOARD POSTURE TRADE/i, 'Playbook: banned BOARD POSTURE TRADE');
ban(playbookChunk, /Current:\s*TRADE/i, 'Playbook: banned Current: TRADE');
ban(playbookChunk, /x-text="canonicalRegimeLine\(\)"/i, 'Playbook: raw canonicalRegimeLine binding');
ban(playbookChunk, /x-text="today7\.tradeability/i, 'Playbook: raw today7.tradeability binding');
ban(playbookChunk, /unifiedTruthStripLine\(\)/i, 'Playbook: raw unifiedTruthStripLine in trust strip');
if (!/playbookOperatorView\(\)/.test(playbookChunk)) {
  errors.push('Playbook: missing playbookOperatorView() wiring');
}
if (!/playbookQualificationDisplay\(\)/.test(playbookChunk)) {
  errors.push('Playbook: missing playbookQualificationDisplay() wiring');
}
if (!/playbookAuthorityViewModel/.test(helpers)) {
  errors.push('cc-helpers: missing playbookAuthorityViewModel');
}

if (errors.length) {
  console.error('verify-runtime-contract FAILED:\n' + errors.map((e) => '  - ' + e).join('\n'));
  process.exit(1);
}

console.log('verify-runtime-contract OK — Discovery + Portfolio + Playbook offline posture');
