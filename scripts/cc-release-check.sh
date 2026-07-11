#!/usr/bin/env bash
# CC release check — dry-runs, audits, verifiers. Exit 0 = RELEASE_READY / WITH_WARNINGS.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CRITICAL=0
WARNINGS=0
RESULTS=()

run_step() {
  local label="$1"
  shift
  echo ""
  echo "== $label =="
  if "$@"; then
    RESULTS+=("PASS  $label")
    echo "→ PASS"
  else
    local rc=$?
    if [[ "$label" == *"(optional)"* ]]; then
      RESULTS+=("WARN  $label (exit $rc)")
      WARNINGS=$((WARNINGS + 1))
      echo "→ WARN (optional)"
    else
      RESULTS+=("FAIL  $label (exit $rc)")
      CRITICAL=$((CRITICAL + 1))
      echo "→ FAIL (exit $rc)"
    fi
  fi
}

echo "CC Release Check — $(date -u +%Y-%m-%dT%H:%M:%SZ)"

run_step "Template drift" node scripts/build-cc-template.mjs --check
run_step "Runtime contract verifier" node scripts/verify-runtime-contract.mjs
run_step "Surface authority verifier" node scripts/verify-surface-authority-contract.mjs
run_step "Authority language audit" python3 scripts/audit-authority-language.py --fail-on critical
run_step "Visible copy audit" python3 scripts/audit-visible-copy.py --fail-on high
run_step "Today payload snapshot" python3 scripts/snapshot-today-payload.py
run_step "Perf smoke (optional)" python3 scripts/perf-smoke-check.py

run_step "Authority copy tests" python3 -c "
import subprocess, sys
from pathlib import Path
ROOT = Path('.').resolve()
rc = subprocess.call([sys.executable, '-m', 'pytest',
  'tests/test_cc_authority_copy_contract.py','tests/test_cc_copy_safety_contract.py','-q','--tb=no'], cwd=ROOT)
if rc != 0 and rc != 4:
  # pytest missing (code 1/2) — run inline smoke
  import importlib.util
  for name in ('test_cc_authority_copy_contract','test_cc_copy_safety_contract'):
    spec = importlib.util.spec_from_file_location(name, ROOT/f'tests/{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in dir(mod):
      if attr.startswith('test_'):
        getattr(mod, attr)()
  sys.exit(0)
sys.exit(rc)
"

run_step "Release audit tests" python3 -c "
import subprocess, sys
from pathlib import Path
ROOT = Path('.').resolve()
rc = subprocess.call([sys.executable, '-m', 'pytest',
  'tests/test_cc_release_audit.py','tests/test_cc_export_smoke.py','tests/test_cc_payload_snapshot.py','-q','--tb=no'], cwd=ROOT)
if rc != 0 and rc != 4:
  import importlib.util
  for name in ('test_cc_release_audit','test_cc_export_smoke','test_cc_payload_snapshot'):
    spec = importlib.util.spec_from_file_location(name, ROOT/f'tests/{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in dir(mod):
      if attr.startswith('test_'):
        getattr(mod, attr)()
  sys.exit(0)
sys.exit(rc)
"

echo ""
echo "======== SUMMARY ========"
for r in "${RESULTS[@]}"; do
  echo "$r"
done
echo ""
echo "Critical failures: $CRITICAL"
echo "Warnings: $WARNINGS"

if [[ $CRITICAL -gt 0 ]]; then
  echo "VERDICT: RELEASE_BLOCKED"
  exit 1
elif [[ $WARNINGS -gt 0 ]]; then
  echo "VERDICT: RELEASE_WITH_WARNINGS"
  exit 0
else
  echo "VERDICT: RELEASE_READY"
  exit 0
fi
