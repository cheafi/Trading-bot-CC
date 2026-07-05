# Single-Stock 360 — Feature Build Prompt（Insider / Options / 13F / PM Decision Layer）

**版本：** 2026-05-25  
**用途：** 專門 build / upgrade Dossier 360 intelligence  
**Existing backend：** `src/services/stock_intel.py` · `GET /api/v7/stock-intel/{ticker}`  
**UI tab：** `dossier` in `src/api/templates/index.html`

---

## Business standard

For any ticker, a PM must answer in **under 60 seconds**:

1. Buy / watch / avoid / wait — **why**
2. What changed recently (flow, insider, estimates, price structure)
3. What invalidates the thesis
4. What to monitor next
5. Can I hand off to IB paper with clear prefilled levels?

**Not acceptable:** data dump · decorative AI · stale 13F as live signal · mock flow without label

---

## Agent Prompt（開始）

You are building **institutional single-stock 360 intelligence** for TradingAI_Bot-main.

Primary surface: **Dossier tab** fed by **`GET /api/v7/stock-intel/{ticker}`**.

### Architecture (observed from code — extend, don't rewrite)

```
stock_intel.py
  ├── build_stock_intel(ticker)           # aggregator entry
  ├── _build_unified_decision()           # TRADE/WATCH/AVOID layer
  ├── _build_action_box()                 # PM action enum (if present)
  ├── build_ticker_flow_intel()           # flow fusion (flow_follow_through)
  └── dossier sub-loaders (fundamentals, technicals, peers, catalysts, ...)

index.html
  ├── fetchDossier() → /api/v7/stock-intel/{t}
  ├── dos.* state object
  └── dossier tab sections (x-show="tab==='dossier'")
```

### Target payload schema (extend stock-intel response)

Agent should implement **missing sections** incrementally. Each section MUST include:

```json
{
	"section_name": {
		"status": "ok | partial | unavailable | mock",
		"source": "polygon | sec_edgar | finnhub | internal | mock",
		"as_of": "ISO8601",
		"staleness_days": 0,
		"evidence_quality": "high | medium | low | insufficient",
		"items": [],
		"summary": "one-line PM-readable",
		"pm_takeaway": "action-oriented"
	}
}
```

### Section build order (ROI-first)

| Phase   | Section                 | Data source strategy                              | Trust rule               |
| ------- | ----------------------- | ------------------------------------------------- | ------------------------ |
| **S1**  | `action_box`            | fuse unified_decision + flow_intel + regime       | enum not prose           |
| **S2**  | `flow_intel`            | `/api/v7/flow-decision/{ticker}` + follow-through | mock → `NOT_ACTIONABLE`  |
| **S3**  | `insider_activity`      | SEC Form 4 / existing insider loader if any       | label filing lag         |
| **S4**  | `institutional_holders` | 13F where available                               | **90+ day lag label**    |
| **S5**  | `options_snapshot`      | chain summary: OI, IV, put/call, unusual          | no fake sweep detection  |
| **S6**  | `street_expectations`   | estimates, revisions, targets                     | show dispersion          |
| **S7**  | `catalyst_calendar`     | earnings, ex-div, lockup                          | date + impact tag        |
| **S8**  | `peer_context`          | existing peers block — enrich vs sector           | relative not absolute    |
| **S9**  | `monitor_triggers`      | price, event, insider, flow thresholds            | alert-ready              |
| **S10** | `influencer_tracking`   | **only** publicly filed / disclosed holders       | no gossip; classify tier |

### action_box enum (PM decision layer)

Use stable enums the UI can color-code:

```
STRONG_BUY_SETUP | BUY_ON_CONFIRM | WATCH_PULLBACK | WATCH_BREAKOUT |
HOLD | REDUCE | AVOID | NO_TRADE | HEDGE_ONLY | INSUFFICIENT_DATA
```

Each action_box entry requires:

```json
{
	"action": "WATCH_PULLBACK",
	"confidence": 0.0,
	"calibration_n": 0,
	"evidence": ["bullet 1", "bullet 2"],
	"why_now": "...",
	"why_not": "...",
	"invalidation": "...",
	"regime_fit": "aligned | neutral | contra",
	"handoff": { "ibkr_draft": true, "entry": null, "stop": null, "target": null }
}
```

**Rule:** If `calibration_n < 30`, cap displayed confidence and show `evidence_quality: insufficient`.

### Insider / fund-manager / influencer rules

1. **Insider:** large officer/director buys/sells; cluster buys; filing date; transaction type; size vs salary heuristic optional.
2. **13F / hedge fund:** quarter-end only; show `report_period` and `days_stale`.
3. **Influencer tier (non-gossip):**
    - Tier A: SEC 13F / 13D / 13G filers with public CIK
    - Tier B: disclosed activist letters / public fund letters (if sourced)
    - Tier C: social — **exclude by default** or sandbox with `research_only: true`
4. Never merge Tier C into action_box without explicit flag.

### Options intelligence rules

Include only if data exists:

- Put/call OI ratio change
- IV rank / percentile (label window)
- Unusual volume vs 20d avg
- LEAPS OI concentration by expiry
- Event window (earnings ±N days)

Tag each signal:

```json
{ "signal": "...", "quality": "credible | noisy | insufficient_sample", "reason": "..." }
```

Mock provider → entire options section `status: mock`, action_box cannot upgrade to BUY.

### UI requirements (Dossier tab)

1. **Top strip:** action_box + unified_decision (no duplicate verdicts — merge visually)
2. **Evidence ladder:** flow → insider → 13F → technical → fundamental (collapsible)
3. **Staleness badges** on every external-data card
4. **IB handoff button:** prefilled only; label "Draft to IB Paper"
5. **Empty states:** "No credible signal" not blank card
6. Do NOT add new Alpine keys without init in `cc()`

### Backend implementation pattern

```python
# In stock_intel.py — pattern for new section
async def _load_insider_section(ticker: str) -> Dict[str, Any]:
    try:
        raw = await _fetch_insider(ticker)  # existing or new loader
        if not raw:
            return {"status": "unavailable", "source": "sec_edgar", ...}
        return {"status": "ok", "items": _normalize_insider(raw), ...}
    except Exception:
        logger.exception("insider section failed for %s", ticker)
        return {"status": "partial", "summary": "Insider data unavailable", ...}
```

Wire into `build_stock_intel()` return dict. Sanitize with existing `sanitize_for_json`.

### Files to touch (typical)

| File                                  | Role                        |
| ------------------------------------- | --------------------------- |
| `src/services/stock_intel.py`         | aggregate sections          |
| `src/services/flow_follow_through.py` | per-ticker flow calibration |
| `src/api/routers/stock_intel.py`      | route, caching if needed    |
| `src/api/routers/platform_extras.py`  | `/flow-decision/{ticker}`   |
| `src/api/templates/index.html`        | Dossier UI sections         |
| `tests/test_stock_intel*.py`          | create if missing           |

### Verification (mandatory)

```bash
python3 -m py_compile src/services/stock_intel.py
python3 -m unittest tests.test_flow_follow_through -q
curl -sf 'http://127.0.0.1:8000/api/v7/stock-intel/AAPL' | python3 -m json.tool | head -80
# Check: action_box, flow_intel, insider sections present with status labels
node --check /tmp/cc.js   # after UI edits
```

### Anti-fake checklist (360-specific)

- [ ] Stale 13F not labeled as current conviction
- [ ] Mock flow not upgrading action to BUY
- [ ] confidence shown without calibration_n
- [ ] Duplicate TRADE/WATCH labels from unified_decision + action_box
- [ ] IB button implies order sent
- [ ] Empty peer table without "unavailable" status

### Output format

```markdown
## Single-Stock 360 Build Log

### Section: [name]

- Backend: [function] — status: ok/partial
- UI: [bind location] — verified: yes/no
- Sample payload: { ... truncated ... }
- Residual risk: ...

### PM workflow test (manual)

- Open dossier AAPL → action visible in <3s → evidence labeled → IB draft labeled
```

### Do NOT

- Add LLM wall-of-text narrative as primary decision layer
- Add influencer Twitter scraping without legal review flag
- Rebuild entire dossier in new framework
- Claim 10/10 without live data paths for ≥3 sections

## Agent Prompt（結束）

---

## Quick start

```
Read docs/SINGLE_STOCK_360_BUILD_PROMPT_ZH.md.
Implement S1–S3 only (action_box, flow_intel, insider_activity).
Start by reading src/services/stock_intel.py and dossier UI in index.html.
Patch minimally. Verify with curl + node --check.
```

---

## Current baseline (2026-05-25, code-observed)

| Component             | Status                                |
| --------------------- | ------------------------------------- |
| `unified_decision`    | Present — heuristic merge             |
| `action_box`          | Partial — verify UI bind              |
| `flow_intel`          | Present via `build_ticker_flow_intel` |
| `insider` / `13F`     | Weak or missing — **S3/S4 priority**  |
| `options_snapshot`    | Partial — depends on provider         |
| `influencer_tracking` | **Not built** — S10 roadmap           |
