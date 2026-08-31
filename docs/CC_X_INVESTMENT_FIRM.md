# CC X — Investment Firm Operating System (v16)

**Product:** CC X · `TradingAI_Bot`  
**Subtitle:** Investment Decision Operating System (IDOS) — firm governance layer  
**Last updated:** 2026-08-25 (Phase A `59db29f` · Phase B cadence stubs · ADR-022)  
**Status:** Design adopted · Phase 1 stubs (firm-cadence API + Ops strip)  
**Architecture:** [`CC_X_ARCHITECTURE.md`](./CC_X_ARCHITECTURE.md)  
**Backlog:** [`CC_X_ENGINEERING_BACKLOG.md`](./CC_X_ENGINEERING_BACKLOG.md)  
**Meta layer:** [`CC_X_META_INTELLIGENCE.md`](./CC_X_META_INTELLIGENCE.md)  
**Governance:** [`CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md`](./CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md)

> v16 is the **firm intelligence** layer: CC runs the discipline of a world-class one-person partnership over 30 years. All governance surfaces are `research_only`; human deploy authority is permanent.

---

## The shift (v15 → v16 → IDOS)

| Version | Optimizes |
|---------|-----------|
| v15 | **System intelligence** — CC learns what inside itself deserves attention |
| v16 | **Firm intelligence** — CC runs institutional governance for one PM over decades |
| **IDOS (ADR-022)** | **Decision quality under uncertainty** — not decision volume |

Software serves the firm. The firm serves **compounding judgment under uncertainty**.

### The Four Questions — immutable law (after Constitution)

Every cadence, surface, and report must answer at least one:

| # | Question | Cadence use |
|---|----------|-------------|
| 1 | **What do we know?** | Facts. Measured. Fresh. Verified. |
| 2 | **What do we believe?** | Hypothesis. Confidence. Trade-offs. |
| 3 | **What don't we know?** | Missing evidence. Unknowns. Assumptions. Alternatives. |
| 4 | **What should we do?** | Deploy / Monitor / Research / Repair / Wait |

**Operator mental model:** **KNOW → BELIEVE → DOUBT → ACT**

Every screen and ritual opens:

```
TODAY
We know ...
We believe ...
We don't know ...
Therefore ...
```

---

## 1. Operating principles

| # | Principle | Source instinct |
|---|-----------|-----------------|
| 1 | Cash is a position — not failure | Marks, Munger |
| 2 | Rank ≠ deploy | CC Constitution |
| 3 | Beliefs before trades | Sleep, Berkshire |
| 4 | Process over prediction | Dalio |
| 5 | Inversion first | Munger |
| 6 | Concentration is earned | Sleep, Smith |
| 7 | Mistakes are assets | Dalio, Learning Engine |
| 8 | Silence is alpha | Marks |
| 9 | Attention is scarce (max 2–3 deep names) | Renaissance discipline |
| 10 | Knowledge outlives positions | Knowledge Engine |
| 11 | Regime gates capital | Marks, Dalio |
| 12 | Human deploy authority permanent | CC Constitution |
| 13 | Simplicity compounds | Munger, Smith |
| 14 | Time horizon explicit at birth | Sleep |
| 15 | Behavioral guardrails beat willpower | Decision science |

---

## 2. Daily firm routine

**Duration:** 15–30 min (WAIT) · 45–90 min (SELECTIVE/TRADE)  
**Owner:** PM · **Voice:** CIIO · **Authority:** Decision Engine only for deploy

| Step | Four Questions | CC surface | Output |
|------|----------------|------------|--------|
| Gate check | **Q4** — Can we deploy? Why not? | Mission Control | WAIT / SELECTIVE / TRADE |
| Regime posture | **Q1** — What environment do we know? | Regime strip | Defensive / neutral / risk-on |
| Attention queue | **Q4** — What 1–2 names deserve eyes? | Attention Engine | Monitor list |
| Belief delta | **Q2/Q3** — What changed? What don't we know? | Portfolio + triggers | Delta brief |
| Capital posture | **Q1/Q4** — Cash winning? Trap positions? | Marginal ROC | Hold / trim / add |
| One decision | **Q4** — Exactly one capital action? | Decision board + **Decision Journal** | Deploy · hold · trim · pass · **explicit wait** |

**Daily template:**

```
TODAY
We know ... (regime, freshness, portfolio facts)
We believe ... (active theses, conviction)
We don't know ... (gaps, assumptions, near-misses)
Therefore ... (one capital action or explicit wait)
```

**Close (5 min):** stewardship check · silence audit · **Decision Journal entry** (deploy or explicit wait) → Learning loop.

**Auto reports:** Mission Brief · attention ledger · gate log · override log · **decision journal recent**.

### Decision Journal + Red Team + Committee (IDOS cadences)

| Cadence | Ritual | CC surface | Output |
|---------|--------|------------|--------|
| Pre-deploy | Red Team challenge | `/api/v7/red-team/challenge` | Five challenge answers (stub → full) |
| Pre-deploy / daily wait | Decision Journal entry | `POST /api/v7/decision-journal/entry` | Pre-outcome record with review dates |
| Weekly IC | Decision Committee review | `/api/v7/decision-committee/review` | Virtual dissent log (stub) |
| Any deploy intent | Outside View base rate | `/api/v7/outside-view/base-rate` | Class prior vs thesis |
| Optional pre-decision | Decision Health self-report | `/api/v7/decision-health/summary` | Calibration inputs (non-blocking) |

All IDOS surfaces: `research_only`; human deploy authority permanent.

---

## Workflow Operating System

Professional edge = **disciplined workflows**, structured reviews, decision governance — not more features, AI, or models. Eight loops + Decision Cooling + Research Queue replace tab-first navigation. Integrates IDOS capabilities (Decision Journal CCX-156 · Red Team CCX-157 · Outside View CCX-158 · Decision Committee CCX-159 · Decision Health CCX-160 · Four Questions · Investment Committee Resolution).

### Operator workflow (replaces tab nav)

```
Mission → Attention → Research → Belief → Counterargument → Quality → Authority → Capital → Execution → Stewardship → Review → Knowledge → Tomorrow
```

Discovery · Playbook · Portfolio · Flow · RS · News = **supporting evidence**, not workflow navigation.

### Stage → primary surface

| Stage | Primary surface |
|-------|-----------------|
| Mission | Mission Brief |
| Attention | Attention budget strip (CCX-164) |
| Research | CIIO + Research Queue + Dossier |
| Belief | Belief Review + Dossier thesis |
| Counterargument | Pre-decision checklist + Red Team |
| Quality | Opportunity quality + Decision Health |
| Authority | Decision board · `deploy_open` SSOT |
| Capital | Marginal ROC + Capital workflow |
| Execution | IBKR + Risk |
| Stewardship | Portfolio |
| Review | Belief Review + Decision Journal |
| Knowledge | Lessons & Calibration |
| Tomorrow | Daily IC 5 min + firm cadence |

### 1. Pre-Decision Workflow ⭐⭐⭐⭐⭐ (HIGHEST ROI)

**Path:** Mission → Question → Belief → Counterargument → Deploy

**Decision Readiness Checklist** (CCX-162 · P0 APPROVED): Why now? · Why not later? · Why not cash? · Why not another stock? · What changes my mind? · What would invalidate? · Opportunity cost?

Phase 1: `/api/v7/decision-readiness/checklist` + Mission Control strip — **display only**, no auto-deploy.

### 2. Daily Investment Committee ⭐⭐⭐⭐⭐ (CCX-163)

**5 min daily** (not just weekly): Mission → Market → Portfolio → Capital → One Belief → Done. One page, no scroll.

### 3. Attention Budget ⭐⭐⭐⭐⭐ (CCX-164)

Time budget per category (Research 60m · Portfolio 30m · Belief 20m · etc.). CIIO says **"Enough"** when expired.

### 4. Decision Pipeline ⭐⭐⭐⭐⭐ (CCX-165)

Idea → Screen → Research → Belief → Quality → Capital → Execution → Review. **80% die at each stage.**

### 5. Opportunity Lifecycle ⭐⭐⭐⭐⭐ (CCX-166)

Born → Observed → Researched → Believed → Monitored → Deployed → Exited → Retired → Archived

### 6. Time-Based Workflow ⭐⭐⭐⭐ (CCX-167)

Morning · Lunch · Close · Weekly · Monthly · Quarterly · Annual rhythm — extends §2–§6 cadences.

### 7. Opportunity Funnel ⭐⭐⭐⭐⭐ (CCX-168)

Universe → Observed → Interesting → Research → Belief → High Priority → Deploy Candidate → Deploy → Stewardship → Retired

### 8. Capital Workflow ⭐⭐⭐⭐⭐ (CCX-169)

Cash → Reserve → Pilot → Add → Full → Trim → Exit → Review

### Decision Cooling (CCX-170 · P0 APPROVED)

```
READY → 10 min cooling → Counterargument → Final Decision
```

Cancel if WAIT · quality drop · portfolio change · new evidence. Phase 1: state machine stub — **research_only**, no deploy authority. Configurable window (`DECISION_COOLING_SECONDS`; 1s in tests).

### Research Queue (CCX-171 · P0 APPROVED)

**Not watchlist/scanner.** CIIO allocates research time like capital.

| Ticker | Category | Budget |
|--------|----------|--------|
| Example | Research | 60m |
| Example | Belief | 20m |

Phase 1: `/api/v7/research-queue` + Ops read-only panel `[data-cc="research-queue-panel"]`.

### Workflow-nav mental model (CCX-172)

Replace equal-weight tabs with stage-first workflow. Tabs remain as evidence surfaces; operator progresses by stage, not by engine name.

---

## 3. Weekly Investment Committee

**When:** Sunday evening or Monday pre-open · **60–90 min**  
**Committees simulated:** Investment + Risk · **Secretary:** CIIO

| Block | Four Questions focus |
|-------|---------------------|
| Regime review | **Q1** — Did regime change? **Q3** — Posture still fit or assumption drift? |
| Portfolio health | **Q1** — Concentration, overlap, cash %, traps |
| Active beliefs | **Q2** — Top 5 thesis intact? **Q3** — Kill conditions near? |
| Opportunity queue | **Q4** — Monitor vs deploy-qualified (quality, not rank) |
| Near-miss review | **Q3** — False positive or early signal? |
| Mistake of the week | **Q1/Q3** — Process or outcome error? What don't we know? |
| One lesson | **Q1** — What enters Knowledge Engine? |
| Next week attention | **Q4** — Assign 2 deep-research slots |

**Reports:** Weekly CIO Digest · belief status board · marginal ROC snapshot · trust delta.

**Decisions:** promote/demote attention queue · flag beliefs amber→red · max new deploys (0–1).

---

## 4. Monthly Capital Review

**When:** First business day · **90–120 min**  
**Committees:** Capital + Investment · **Integrates:** v14 flywheel + v15 MIE (question-lift scoring)

**Must answer (Four Questions):**

| Q | Question |
|---|----------|
| Q1 | Did cash outperform marginal new deploys? (known outcomes) |
| Q2 | Which positions earned concentration? (beliefs validated) |
| Q3 | Capital traps — what don't we know about dead money + opportunity cost? |
| Q4 | One capital action · cash target band · retire one monitor · approve MIE's one improvement |

**Reports:** P&L attribution · marginal ROC ladder · concentration audit · capital mistakes · System Evolution Review (Four Questions format).

---

## 5. Quarterly Belief Review

**When:** Week after quarter-end · **Half day**  
**Committees:** Belief + Learning

| Theme | Four Questions focus |
|-------|---------------------|
| Calibration | **Q2/Q3** — Confident when wrong? Cautious when right? |
| Thesis drift | **Q2/Q3** — Story changed without log? |
| Kill conditions | **Q3/Q4** — Pre-stated exits ignored? |
| Conviction vs size | **Q1/Q2** — Size matched stated conviction? |
| Macro sensitivity | **Q1/Q3** — Regime invalidated beliefs? |
| Analog accuracy | **Q1/Q3** — Historical analogs validated? |

**Reports:** calibration scatter · forward outcomes T+20 · override analysis · idea graveyard.

**Decisions:** retire beliefs (death certificate) · upgrade/downgrade conviction · revise kill conditions · inversion ritual on one sacred cow.

---

## 6. Annual Learning Summit

**When:** December / fiscal year-end · **1.5 days**  
**Committees:** All · **Historian:** Knowledge Engine

| Session | Focus |
|---------|-------|
| Morning | Attribution tree · best/worst 3 decisions (process) · cash periods |
| Midday | Beliefs born/lived/died · knowledge graph themes · repeated mistakes |
| Afternoon | CC evolution score · features deleted · trust map · complexity index |

**Decisions:** IPS refresh · concentration limits · research budget · one behavioral rule · knowledge archive.

**Artifact:** Letter to future self · 30-year judgment scorecard.

---

## 7. Knowledge preservation

| Layer | What | When | Owner |
|-------|------|------|-------|
| Decision log | Thesis + kill conditions | At deploy | Decision Engine |
| Belief artifacts | IO + AlphaObject | At research birth | Research |
| Forward outcomes | T+0/1/5/20 marks | Auto + review | Learning |
| Mistake taxonomy | Process error class | At review | Learning Committee |
| Lesson cards | One paragraph | Weekly+ | Knowledge |
| Idea graveyard | Retired beliefs + why | Quarterly | Belief Committee |
| Analog library | Validated comparisons | Annual | Knowledge |
| Override journal | Human disagreed with CC | Real-time | Trust Engine |

**Never preserve:** raw chatter without thesis · rank without quality · AI without provenance · duplicate gates.

---

## 8. Capital governance

| When cash wins | When concentration increases | When position dies |
|----------------|------------------------------|-------------------|
| Regime WAIT / defensive | Thesis intact + kill far + regime OK | Kill condition hit |
| No deploy-qualified setup | Forward outcomes validate edge | Thesis falsified |
| Marginal ROC < cash hurdle | Marginal ROC of add > next best | Opportunity cost exceeds intent |
| Portfolio heat at limit | Belief quarterly upgrade | Stewardship failure |

**Belief dies:** inversion test passed · 2 quarterly reds · T+20 contradicts · trust collapsed.

**Attention moves:** monitor fails 4 weeks · quality tier lost · regime reassigns theme · attention ROI negative 90d.

---

## 9. Risk governance

| Risk | Control | CC enforcement |
|------|---------|----------------|
| Regime | Page gate blocks deploy | Decision Engine |
| Concentration | Top-3 / sector caps | Portfolio Engine |
| Liquidity | Size vs ADV | Execution Engine |
| Behavioral | Override cooldown, loss-day rules | Behavioral Governance |
| Model | Stale/mock flagged | Provenance contract |
| Process | Deploy without belief blocked | IO/Alpha birth required |
| Attention | Monitor cap | Attention Engine |
| Tail | Stop discipline, crisis posture | Regime strips |

**Reports:** daily gate+broker · weekly heat map · monthly drawdown vs regime · quarterly stress on top 3.

---

## 10. Decision governance

```
Page Gate  >  Card Rank  >  Quality Tier  >  Narrative
     ↓
Decision Engine (deploy_open only)
     ↓
Human PM (final deploy click)
```

| Type | Authority | Cadence |
|------|-----------|---------|
| Deploy | Human + gate open | Daily if warranted |
| Trim / add | Human + capital review | Weekly/monthly |
| Monitor promotion | Attention Engine | Weekly |
| Belief upgrade/downgrade | Belief Committee | Quarterly |
| Override | Human — logged | Anytime |
| Silence | CIIO recommends | Daily |

**Debate protocol:** steel man → inversion → pre-mortem → regime fit → replacement → kill conditions (pre-stated).

---

## 11. Behavioral governance

| Bias | Countermeasure |
|------|----------------|
| Action bias | WAIT default; silence score |
| Recency | Forward outcomes, not last trade |
| Confirmation | Inversion before deploy |
| Overconfidence | Quarterly calibration |
| Anchoring to rank | Quality tier separate |
| Narrative fallacy | Provenance required |
| Loss chasing | Mandatory cash day after override+loss |
| FOMO | Near-miss review |

**Rules:** no deploy within 24h of emotional override · max 1 new position/week · journal before override · no size increase on euphoria day.

---

## 12. Culture

**Rules:** owners not traders · omission over commission · write it down · kill ideas fast, nurture lessons · activity ≠ progress · cash is courage · gate outranks rank · one human deploys · simplicity wins · review process on wins and losses.

**Rituals:** gate bow (daily) · inversion minute (pre-deploy) · mistake Monday · cash audit (monthly) · belief trial (quarterly) · letter to future self (annual) · deletion ceremony (monthly).

**Vocabulary:** deploy-qualified (not buy signal) · belief (not conviction feeling) · kill condition (not stop) · gate (not green light) · silence (not missing out).

---

## 13. Top 50 institutional habits

1. Read gate before rank · 2. Cash as deliberate position · 3. Thesis before size · 4. Kill conditions before entry · 5. Invert every idea · 6. Pre-mortem before deploy · 7. One capital action/day max · 8. Max 3 deep-attention names · 9. Log overrides without shame · 10. Review process on wins · 11. Quality ≠ deploy authority · 12. Provenance on every number · 13. Challenge beliefs quarterly · 14. Retire undeveloped ideas · 15. Marginal ROC not absolute return · 16. What gets worse if we do this? · 17. Silence on unchanged days · 18. Never deploy from Discovery browse · 19. Honor stale-data flags · 20. Size follows conviction+time+validation · 21. Trim on thesis drift · 22. One mistake weekly · 23. One lesson card weekly · 24. Trust by follow-through · 25. Ignore low-trust advice · 26. Pre-answer recurring questions · 27. Regime limits size · 28. Concentration earned · 29. Replacement before adds · 30. Execution ≠ idea quality · 31. Forward outcomes over hindsight · 32. Calibration beats confidence · 33. Near-miss prevents FOMO · 34. Attention ROI per surface · 35. Delete complexity monthly · 36. No revenge trading · 37. No size on euphoria day · 38. Broker down = repair mission · 39. Mission Brief before drill-down · 40. Expand context deliberately · 41. Death certificate on retire · 42. Knowledge before new scan · 43. Annual letter to future self · 44. IPS on wall · 45. Steel man then inversion · 46. Hold period at birth · 47. Theme concentration monthly · 48. Drawdown vs regime not ego · 49. System evolution ≠ P&L · 50. Simplicity compounds 30 years.

---

## 14. What never changes (30 years)

1. Human deploy authority · 2. Page Gate > Card Rank · 3. Research ≠ deploy · 4. Beliefs before capital · 5. Kill conditions at birth · 6. Mistakes → lessons · 7. Cash as valid outcome · 8. Process review on wins and losses · 9. One PM, one firm · 10. The Constitution · 11. Attention scarcity · 12. Silence as success · 13. Knowledge outlives positions · 14. Simplicity budget · 15. Purpose = wisdom not activity.

---

## 15. Constitution of an investment firm (one page)

**We are a partnership of one human and one operating system, managing capital as if it cannot be replaced — because it cannot.**

**Purpose:** Not to trade, predict, or perform. To **compound calibrated judgment** over decades through fewer, better, fully-owned decisions.

**Authority.** The human alone deploys capital. The system advises with radical honesty, fails closed when uncertain, and never confuses research quality with deploy permission. The page gate outranks every card rank.

**Capital.** Cash is a position. Concentration is earned through time, validation, and regime fit — never excitement. Every deploy requires a written belief, explicit kill conditions, and marginal return superiority over the next best alternative including cash.

**Process.** Daily: Four Questions (know / believe / doubt / act). Weekly: portfolio health and attention assignment. Monthly: capital and system evolution audit. Quarterly: belief challenge and calibration. Annually: knowledge preservation and policy renewal.

**Risk.** Invert before invest. Pre-mortem before deploy. Log every override without shame; review without excuse. Reduce size when regime degrades; honor kill conditions without negotiation.

**Learning.** Positions end; lessons never do. Every mistake classified. Every belief can die. Every retired idea leaves a death certificate.

**Culture.** Omission over commission. Bored on WAIT days; decisive on qualified days. Delete complexity monthly. Trust advice that earns follow-through.

**The vow.** For thirty years we will not become more complicated to feel more intelligent. We will become **more selective, more calibrated, and more quiet** — until every dollar deployed is an expression of earned wisdom.

**Closing (IDOS).** The market is uncertain. Our process should not be. CC exists to help the operator continuously reduce avoidable uncertainty before risking irrecoverable capital. Success includes becoming **progressively less dependent on CC** — not more addicted to its surfaces.

---

## Stack on v10–v15

```
v10  Architecture      →  What exists
v11  Constitution      →  What must never break
v12  Investment OS     →  How PM thinks
v13  CIIO              →  How truth is spoken
v14  Alpha Flywheel    →  What compounds in markets
v15  Meta Engine       →  What compounds in the system
v16  Investment Firm   →  How the institution operates over 30 years
```

---

## Phase 1 implementation (current)

| Item | Backlog | Status |
|------|---------|--------|
| Phase 1 implementation (current) | CCX-141 | **done** — `/api/v7/firm-cadence/summary` |
| Pre-decision checklist API + strip | CCX-162 | **done** — `/api/v7/decision-readiness/checklist` |
| Research queue API + Ops panel | CCX-171 | **done** — `/api/v7/research-queue` |
| Decision cooling stub | CCX-170 | **done** — `/api/v7/decision-cooling/*` |
| Mission Control cadence strip | CCX-147 | **done** — display only |
| Ops firm cadence panel | CCX-147 | **done** |
| Daily CIIO template | CCX-141 | todo |
| Weekly IC digest | CCX-142 | todo |
| Monthly Capital template | CCX-143 | todo |
| Quarterly Belief ritual | CCX-144 | todo |
| Annual Learning Summit stub | CCX-145 | todo |
| Committee checklists in Ops | CCX-146 | in-progress |
| Lifecycle stages wired to IO/Alpha/Learning | CCX-147–155 | todo |

---

## Related documents

| Doc | Role |
|-----|------|
| [`CC_X_ARCHITECTURE.md`](./CC_X_ARCHITECTURE.md) | Engine boundaries + firm layer |
| [`CC_X_META_INTELLIGENCE.md`](./CC_X_META_INTELLIGENCE.md) | MIE monthly evolution |
| [`CC_X_REVIEW_CYCLE.md`](./CC_X_REVIEW_CYCLE.md) | Cadence → review type mapping |
| [`CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md`](./CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md) | IDOS + Four Questions + PR gate |
| [`CC_X_DECISION_LOG.md`](./CC_X_DECISION_LOG.md) | ADR-020 v16 adoption · ADR-022 IDOS |

---

## Test anchors

```bash
PYTHONPATH=. pytest tests/test_operator_mode_ux.py tests/test_decision_board_authority_cache.py tests/test_workflow_loops.py -q
```

Authority: firm cadence surfaces carry `research_only`; no deploy paths added.
