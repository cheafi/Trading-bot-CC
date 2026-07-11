# CC Release Checklist

**Verdict targets:** `RELEASE_READY` · `RELEASE_WITH_WARNINGS` · `RELEASE_BLOCKED`

---

## One-Command Gate

```bash
bash scripts/cc-release-check.sh
```

Runs template drift, runtime + surface authority verifiers, authority language audit, visible copy audit, payload snapshot, perf smoke, and targeted pytest suites.

---

## Manual Steps (pre-merge)

- [ ] `node scripts/build-cc-template.mjs --check`
- [ ] `node scripts/verify-runtime-contract.mjs`
- [ ] `node scripts/verify-surface-authority-contract.mjs`
- [ ] `python3 scripts/audit-authority-language.py --fail-on critical`
- [ ] `python3 scripts/audit-visible-copy.py --fail-on high`
- [ ] `python3 scripts/snapshot-today-payload.py`
- [ ] `python3 scripts/perf-smoke-check.py` (optional analytics slow OK if Today passes)
- [ ] Export All Pages smoke — header, Ops, FAB; timestamp filename; no empty PDF
- [ ] No visible `??` or `?` corruption in UI copy (`repair-visible-copy.py` if needed)

---

## Pytest (focused)

```bash
python -m pytest tests/test_cc_release_audit.py tests/test_cc_export_smoke.py tests/test_cc_payload_snapshot.py tests/test_cc_authority_copy_contract.py tests/test_surface_authority_contract.py -q
```

---

## Success Criteria

| Check | Pass condition |
|-------|----------------|
| Authority | No critical forbidden phrases outside approved contexts |
| Visible copy | No high/critical corruption (`??`, mojibake, broken prefixes) |
| Decision Quality | Collapsed default; learning mode neutral; no fake precision |
| OI | Research-only; blocked banner when deploy unavailable |
| Threshold | Review only · no live changes when nothing promoted |
| Export | Non-empty degraded fallback; timestamp slug; no deploy leak |
| Payload | Required keys + `may_authorize_deploy: false` |

---

## Reporting `??` / Corruption

1. Run `python3 scripts/audit-visible-copy.py --json > /tmp/copy-audit.json`
2. Fix with `python3 scripts/repair-visible-copy.py` for known index.html patterns
3. Re-run audit until `--fail-on high` passes

---

## Threshold Shadow Rules

- Proposals stay **shadow** until human `approve_shadow`
- Analytics never writes live thresholds (`no_live_changes_from_analytics: true`)
- Ops panel is diagnostic — acknowledge/reject/defer only
