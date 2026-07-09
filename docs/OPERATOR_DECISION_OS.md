# Operator Decision OS

**Branch law:** `sprint99-fund-productization`  
**SSOT code:** `src/services/surface_authority.py`, `src/services/authority_engine.py`, `src/services/operator_surface.py`, `src/services/decision_hierarchy.py`  
**Enforcement:** `tests/test_surface_authority_contract.py`, `scripts/verify-surface-authority-contract.mjs`, `scripts/verify-runtime-contract.mjs`

---

## Constitution

1. **Page gate beats card rank** — regime/tradeability (L1) caps all deploy surfaces before any card score matters.
2. **Research ≠ permission** — Discovery, Flow, Funds, RS, Dossier, Strategy Lab inform; they do not authorize sizing alone.
3. **One surface owns header copy** — `build_header_summary(surface_mode)`; deploy chips only on `dashboard_core` + `playbook_core`.
4. **Scoped truth, not global pills** — Market/Board/Brief/Broker/Runtime/Authority labels; never `DATA FRESH` + `DATA STALE` contradiction.
5. **Guide suspends decision language** — `GUIDE MODE · Reference only · Decision surfaces suspended`; runtime not evaluated on Guide.
6. **PILOT ≠ half-size default** — PILOT/WATCH labels are review candidates until deploy authority opens; half-size only when `pilot_sizing_allowed()` is true.
7. **Dossier ≠ decision card** — structure confirmation only; confirm-only mode hides trade plan and sizing.
8. **Ops confirms runtime; IBKR confirms handoff** — engine badge alone ≠ fresh cycle; LOGIN ≠ READY.

---

## Authority Chain

Five-level hierarchy (`decision_hierarchy.py`). Lowest failing level binds.

| Level | Label | Authority |
|-------|-------|-----------|
| L1 | Page gate | Blocks or permits all deploy surfaces |
| L2 | Board quality | Caps how many names earn sizing |
| L3 | Setup evidence | Thesis / timing / R:R — not decorative |
| L4 | Execution readiness | Broker + bracket + fill realism |
| L5 | Portfolio restraint | Book fit, turnover, crowding governor |

Deploy authority tiers (`authority_engine.py`):

| Tier | Primary posture | Allowed | Blocked |
|------|-----------------|---------|---------|
| `allowed` | Regime (TRADE/SELECTIVE/…) | deploy selectively on qualified names | — |
| `paper_only` | PAPER DEPLOY | paper simulation drafts | no live handoff |
| `pilot_only` | PILOT | pilot review; half size only when broker+fresh | no full-size deploy |
| `blocked` | MONITOR ONLY | monitor candidates, watch rules | no sizing, no handoff, no pilot entry |

Surface authority resolution (`surface_authority.resolve_authority`):

- **Guide** → always `suspended`
- **Dashboard / Playbook / Portfolio** → `blocked` on IBKR critical fail or WAIT/NO_TRADE (Playbook → `research_only` on WAIT)
- **Discovery / Dossier / Funds / RS / Command / Strategy Lab** → always `research_only` (with contextual reasons)
- **Flow** → always `confirmation_only`
- **Ops / IBKR** → `ops_probe` (connectivity ≠ capital permission)
- **Time Travel** → `suspended` replay overlay; not live deploy surface

Operator block fields (`operator_surface.build_operator_block`): **NOW / WHY / ALLOWED / BLOCKED / VALID CANDIDATES / NEXT**.

---

## Blocked / Allowed Day Mental Model

### Blocked day (tier = `blocked` or L1 closed)

- **NOW:** MONITOR ONLY · Deploy blocked
- **ALLOWED:** monitor candidates, create watch rules
- **BLOCKED:** no sizing, no handoff, no pilot entry
- **Surfaces:** Dashboard shows gate; Playbook qualification shows 0 deploy-qualified; Discovery research-only; Dossier confirm-only; Portfolio risk review only
- **Labels:** PILOT/TRADE/WATCH on cards are **review-only** — not permission

### Allowed day (tier = `allowed`, L1–L4 clear)

- **NOW:** regime primary (TRADE / SELECTIVE / …)
- **ALLOWED:** deploy selectively on qualified names
- **NEXT:** review deploy-qualified on Playbook
- **Surfaces:** Dashboard + Playbook may show deploy chips; Dossier still not standalone permission; IBKR must be READY for handoff

### Pilot day (tier = `pilot_only`)

- **NOW:** PILOT
- **ALLOWED:** pilot review only until `pilot_sizing_allowed()`; then half size when broker ready
- **BLOCKED:** no full-size deploy until execution-ready
- **Mental model:** review Pilot bucket first — not automatic half-size entry

### Paper day (tier = `paper_only`)

- **NOW:** PAPER DEPLOY
- **ALLOWED:** paper simulation drafts
- **BLOCKED:** no live IBKR handoff

---

## Daily Operator Flow

See [DAILY_OPERATOR_FLOW.md](./DAILY_OPERATOR_FLOW.md) for step-by-step blocked and allowed paths.

**Morning sequence (all days):**

1. Open **Dashboard** — read scoped truth strip + operator block
2. Check L1 gate — tradeability WAIT/NO_TRADE → stop at monitor path
3. Open **Playbook** — qualification line + ranked board (deploy chips only if authority open)
4. Cross-check **Dossier** for structure confirmation (not trade ticket)
5. **Portfolio** capacity before adding risk
6. Use **Discovery / Flow / RS** for idea generation only
7. **IBKR** only when handoff intended — confirm READY + bracket
8. **Ops** if any scope stale or engine conflict

**Never start from:** Guide (reference), Strategy Lab (research draft), Time Travel (historical), Rejections (audit only).

---

## Merge Checklist

Before merging surface/authority changes:

```bash
node scripts/build-cc-template.mjs --check
node scripts/verify-runtime-contract.mjs
node scripts/verify-surface-authority-contract.mjs
python -m pytest tests/test_surface_authority_contract.py tests/test_guide_surface_authority.py tests/test_runtime_render_contract.py -q
```

- [ ] `guide.html` partial changes rebuilt into `index.html`
- [ ] No banned phrases in live runtime bindings (whitelist only in guide illustrations / sanitizer maps)
- [ ] Dossier confirm-only copy preserved
- [ ] PILOT wording does not imply half-size default
- [ ] All 16 surfaces present in `SURFACE_CONTRACTS`
- [ ] `surface_authority.py` and contract module aligned
