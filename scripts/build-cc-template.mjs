#!/usr/bin/env node
/**
 * Inline CC partials into index.html (instant + Jinja serve committed output).
 * Usage: node scripts/build-cc-template.mjs [--check]
 */
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const INDEX = path.join(ROOT, 'src/api/templates/index.html');
const GZIP_DASHBOARD = path.join(ROOT, 'src/api/static/cc-dashboard.html.gz');
const PARTIALS = {
  degraded_banners: path.join(
    ROOT,
    'src/api/templates/cc/partials/degraded_banners.html',
  ),
  ops_recovery_runbook: path.join(
    ROOT,
    'src/api/templates/cc/partials/ops_recovery_runbook.html',
  ),
  guide: path.join(ROOT, 'src/api/templates/cc/partials/guide.html'),
  deploy_surfaces: path.join(
    ROOT,
    'src/api/templates/cc/partials/deploy_surfaces.html',
  ),
};

function injectPartial(name, html, partialBody) {
  const start = `<!-- @cc-partial ${name} -->`;
  const end = `<!-- @cc-partial-end ${name} -->`;
  const re = new RegExp(
    `${escapeRe(start)}[\\s\\S]*?${escapeRe(end)}`,
    'm',
  );
  if (!re.test(html)) {
    throw new Error(`Missing markers for partial "${name}" in index.html`);
  }
  const block = `${start}\n${partialBody.trimEnd()}\n    ${end}`;
  // Use replacer fn — partial HTML may contain `$` (Alpine x-text), which breaks string replace.
  return html.replace(re, () => block);
}

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function build() {
  let html = fs.readFileSync(INDEX, 'utf8');
  for (const [name, partialPath] of Object.entries(PARTIALS)) {
    const body = fs.readFileSync(partialPath, 'utf8');
    html = injectPartial(name, html, body);
  }
  return html;
}

const check = process.argv.includes('--check');
const built = build();
const current = fs.readFileSync(INDEX, 'utf8');

function writeDashboardGzip(html) {
  const gz = zlib.gzipSync(Buffer.from(html, 'utf8'), { level: 9 });
  fs.writeFileSync(GZIP_DASHBOARD, gz);
}

if (check) {
  if (built !== current) {
    console.error(
      'index.html is out of date — run: node scripts/build-cc-template.mjs',
    );
    process.exit(1);
  }
  if (!fs.existsSync(GZIP_DASHBOARD)) {
    console.error(
      'cc-dashboard.html.gz missing — run: node scripts/build-cc-template.mjs',
    );
    process.exit(1);
  }
  const gzMtime = fs.statSync(GZIP_DASHBOARD).mtimeMs;
  const htmlMtime = fs.statSync(INDEX).mtimeMs;
  if (gzMtime < htmlMtime) {
    console.error(
      'cc-dashboard.html.gz stale — run: node scripts/build-cc-template.mjs',
    );
    process.exit(1);
  }
  console.log('CC template partials match index.html');
  process.exit(0);
}

if (built !== current) {
  fs.writeFileSync(INDEX, built);
  writeDashboardGzip(built);
  bundleCcAppIntoHelpers();
  console.log('Updated', INDEX);
  console.log('Updated', GZIP_DASHBOARD);
} else {
  writeDashboardGzip(built);
  bundleCcAppIntoHelpers();
  console.log('index.html already up to date');
  console.log('Refreshed', GZIP_DASHBOARD);
}

function bundleCcAppIntoHelpers() {
  const helpersPath = path.join(ROOT, 'src/api/static/cc-helpers.js');
  const appPath = path.join(ROOT, 'src/api/static/cc-app.js');
  const cachePath = path.join(ROOT, 'data/cache/cc-helpers.bundle.js');
  if (!fs.existsSync(appPath)) return;
  let helpers = fs.readFileSync(helpersPath, 'utf8');
  const marker = '/* CC_APP_BUNDLE_START';
  const app = fs.readFileSync(appPath, 'utf8');
  if (helpers.includes(marker)) {
    helpers = helpers.split(marker)[0].trimEnd();
  }
  const bundled =
    helpers +
    '\n\n/* CC_APP_BUNDLE_START — cc() Alpine app (source: cc-app.js) */\n' +
    app;
  fs.writeFileSync(helpersPath, bundled);
  fs.mkdirSync(path.dirname(cachePath), { recursive: true });
  fs.writeFileSync(cachePath, bundled);
}
