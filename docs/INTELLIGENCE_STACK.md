# Intelligence Stack — Clarity Console

**Branch:** `sprint99-fund-productization`  
**North star when blocked:** MONITOR ONLY · Review only · Repair blockers · No deploy

---

## Layer Map

| Layer | Surface | Authority | Default UI |
|-------|---------|-----------|------------|
| L0 Guide | Guide | suspended | Reference only |
| L1 Page gate | Dashboard | deploy/blocked | Operator block + truth strip |
| L2 Board | Playbook | deploy/research | Qualification + ranked cards |
| L3 Research funnel | Discovery | research_only | OI collapsed · shortlist |
| L4 Structure | Dossier | confirm-only | No standalone permission |
| L5 Book fit | Portfolio | risk review | Capacity before risk |
| L6 Execution probe | IBKR / Ops | ops_probe | Connectivity ≠ capital |

## Intelligence Modules (collapsed by default)

### Decision Quality (Dashboard)
- **Alpha Quality** — evidence only, learning mode on low n, no green on medium/high overfit
- **Alpha Review** — advisory deltas, human review queue, authority effect: none
- **Threshold Review** — review only · no live changes; shadow proposals require human approval

### Opportunity Intelligence (Discovery)
- Research-only compact panel
- Promotion copy: **send to Playbook review** (never deploy)
- When blocked: **Research only · deploy authority unavailable**

### Threshold Governance (Ops)
- Diagnostic only — no deploy buttons
- `can_auto_loosen: false` globally
- Last-run lines for backfill / evaluate / review / propose / verifiers

---

## Learning Mode Interpretation

| Signal | Meaning |
|--------|---------|
| `learning_mode: true` | Sample below calibration threshold — no precise lift/ROI |
| `state_label: Learning mode` | Forward outcomes insufficient |
| `overfit_risk: medium/high` | Success labels capped — no green UI |
| Empty intelligence | Never success — show neutral/warn empty state |

---

## What Never Auto-Loosens

- Deploy/capital thresholds from analytics alone
- Governor QA adjustments without human review when flagged
- Playbook deploy-qualified count when page gate blocked
- Research surfaces promoting to deploy language

---

## Release Scripts

```bash
bash scripts/cc-release-check.sh
python3 scripts/audit-authority-language.py
python3 scripts/audit-visible-copy.py
python3 scripts/snapshot-today-payload.py
python3 scripts/perf-smoke-check.py
python3 scripts/repair-visible-copy.py   # one-time UTF-8 repair if needed
```

See [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) for full gate list.
