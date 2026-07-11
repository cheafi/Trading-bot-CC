"""Export All Pages smoke — helpers must always produce non-empty review HTML."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / "src/api/static/cc-helpers.js"


def test_export_helpers_present():
    js = HELPERS.read_text(encoding="utf-8")
    for fn in (
        "buildExportReviewHtml",
        "buildExportIssuesPage",
        "buildExportAllSurfacesPage",
        "exportReviewPdf",
        "exportSnapshotHasContent",
        "exportGuideWorkflowLine",
    ):
        assert fn in js


def test_export_print_root_in_index():
    html = (ROOT / "src/api/templates/index.html").read_text(encoding="utf-8")
    assert 'id="cc-export-print-root"' in html
    assert "exportReviewPdfClick" in html
    assert "data-cc=\"export-review-pdf\"" in html


def test_export_guide_workflow_no_corruption():
    html = (ROOT / "src/api/templates/index.html").read_text(encoding="utf-8")
    assert "Dashboard ? Playbook" not in html
    assert "monitor-only ? not" not in html


def test_export_review_pdf_no_empty_content_error():
    js = HELPERS.read_text(encoding="utf-8")
    assert "empty export content" not in js
    assert "empty export html" not in js


def test_node_export_html_smoke():
    snippet = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/api/static/cc-helpers.js', 'utf8');
const ctx = { console, process, setTimeout, clearTimeout, document: undefined, window: undefined, html2pdf: undefined };
vm.createContext(ctx);
vm.runInContext(src + `
  const snap = {
    generated_at: new Date().toISOString(),
    system_truth: { deploy_authority: false, reason_codes: ['WAIT'] },
    system_truth_line: 'MONITOR ONLY',
    cc_header: { freshness: 'STALE', engine: 'OFF', ibkr: 'offline', breaker: 'clear', mode: 'full' },
    today: { board_message: 'Wait day', tradeability: 'WAIT' },
    playbook: { funnel_label: '0 deploy-qualified', rows: [] },
    guide: { workflow: CCHelpers.exportGuideWorkflowLine() },
    decision_quality: { summary_lines: ['Learning mode'] },
  };
  const html = CCHelpers.buildExportReviewHtml(snap);
  if (!html || html.replace(/\\s/g,'').length < 120) throw new Error('export html too short');
  if (!CCHelpers.exportSnapshotHasContent(snap)) throw new Error('snapshot should have content');
  process.stdout.write(JSON.stringify({ ok: true, len: html.length }));
`, ctx);
"""
    proc = subprocess.run(["node", "-e", snippet], cwd=ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    data = json.loads(proc.stdout.strip())
    assert data["ok"] is True
    assert data["len"] > 200
