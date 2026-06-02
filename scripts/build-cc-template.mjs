#!/usr/bin/env node
/**
 * Inline CC partials into index.html (instant + Jinja serve committed output).
 * Usage: node scripts/build-cc-template.mjs [--check]
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const INDEX = path.join(ROOT, 'src/api/templates/index.html');
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
  return html.replace(re, block);
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

if (check) {
  if (built !== current) {
    console.error(
      'index.html is out of date — run: node scripts/build-cc-template.mjs',
    );
    process.exit(1);
  }
  console.log('CC template partials match index.html');
  process.exit(0);
}

if (built !== current) {
  fs.writeFileSync(INDEX, built);
  console.log('Updated', INDEX);
} else {
  console.log('index.html already up to date');
}
