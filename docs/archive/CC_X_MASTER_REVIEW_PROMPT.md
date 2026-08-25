# CC X — Institutional Alpha OS Master Review Prompt

**Canonical continuous improvement prompt** for VS Code AI Agent, Cursor, Copilot, and Claude Code.  
Reuse this file whenever you need a full-repo institutional review of TradingAI_Bot / CC X without re-authoring scope.

**Latest execution output:** [`CC_X_FULL_INSTITUTIONAL_REVIEW.md`](./CC_X_FULL_INSTITUTIONAL_REVIEW.md)  
**Roadmap companion:** [`CC_X_INSTITUTIONAL_ALPHA_OS.md`](./CC_X_INSTITUTIONAL_ALPHA_OS.md)  
**Prior review baseline:** [`CC_VNEXT_INSTITUTIONAL_MASTER_REVIEW.md`](./CC_VNEXT_INSTITUTIONAL_MASTER_REVIEW.md)

---

## How to Run

1. Paste everything from `--- PROMPT START ---` through `--- PROMPT END ---` into your agent.
2. Set repo path and branch (e.g. `cc/upgrade-regime-tracking`).
3. Agent must **read existing docs first** — do not duplicate blindly:
    - `docs/CC_X_INSTITUTIONAL_ALPHA_OS.md`
    - `docs/CC_VNEXT_INSTITUTIONAL_MASTER_REVIEW.md`
    - `docs/CC_CONSOLIDATED_BRIEFING.md`
4. Agent must **explore the codebase holistically** (architecture, services, engines, UI, tests, scheduler, authority).
5. Agent produces **NEW** comprehensive doc: `docs/CC_X_FULL_INSTITUTIONAL_REVIEW.md`.
6. **Docs only** — no code changes unless explicitly requested in a separate task.
7. **Never commit secrets.**

---

--- PROMPT START ---

Execute **CC X Institutional Alpha OS Master Review** for TradingAI_Bot.

Act as a brutally honest institutional trading-platform architecture, PM workflow, alpha research, risk, and implementation board — one combined team of CIO, quant researcher, PM/COO, UX designer, compliance officer, and principal engineer.

**Mission:** Upgrade CC from an Operator Decision OS into an **Institutional Alpha OS** (investment-outcome-first) while preserving every authority contract. Target path: **7.0 → 9.5**. Compete on **evidence + prioritization + governance + institutional memory** — not HFT latency or fake confidence.

### Strategic north star

Every module must answer:

> **Does this improve long-term portfolio alpha after cost and risk?**

Build and measure in this order:

```
Capital → Expected Alpha → Risk Budget → Portfolio Construction → Execution → Measured Alpha → Knowledge
```

Six **core engines** (not pages):

| Engine           | Primary question                                         |
| ---------------- | -------------------------------------------------------- |
| **Knowledge**    | What did we learn last time this looked like March 2024? |
| **Research**     | Is the hypothesis supported?                             |
| **Decision**     | May we deploy?                                           |
| **Portfolio**    | Where should the next $10K go?                           |
| **Execution**    | Can we execute without destroying edge?                  |
| **Intelligence** | Did the platform become smarter today?                   |

Pages (Dashboard, Playbook, Discovery, Portfolio) are **views** of the same underlying model (`InvestmentObject` + `AlphaObject`).

---

### HARD RULES (must appear in review output)

| Principle                              | Enforcement                                                                                 |
| -------------------------------------- | ------------------------------------------------------------------------------------------- |
| **Research ≠ Deploy authority**        | `surface_authority.py`, `authority: research_only`, Discovery/Flow/Agent never grant deploy |
| **Page Gate > Card Rank**              | `operator_state_contract.py`; WAIT/NO_TRADE blocks deploy regardless of score               |
| **No auto trading/deploy**             | Human deploy approval; IBKR handoff ladder; `deploy_open` server-authoritative              |
| **No threshold auto-loosening**        | `decision_truth_model.py` TRADE_RR_THRESHOLD=2.5 — static without human changelog           |
| **No fake confidence**                 | Thompson/ML hidden n&lt;5/n&lt;30; mock factor labeled degraded; sample size on EdgeModel   |
| **Incremental evolution not rewrites** | Adapter patterns; legacy rank fallback; revert IO consumer only on authority regression     |

**Explicit prohibitions:** auto-loosen thresholds; ML multiplier without sample floor; synthetic flow as live; Discovery score implying deploy; screens without EV; auto rule changes from learning; cache `deploy_open=true`.

---

### Review method

- Full-repo read: services (~160), engines (~100), routers (~61), tests (~180+), scheduler, UI (`index.html`, `cc-app.js`), authority cluster.
- Code-path citations only; label Observed | Inferred | Not verifiable.
- Reference recent work: `DecisionBoardService`, Telegram alerts, opportunity coverage, `AlphaObject`, `InvestmentObject`.
- Align with investment-outcome-first six engines per `CC_X_INSTITUTIONAL_ALPHA_OS.md`.

---

### Required deliverables

Produce `docs/CC_X_FULL_INSTITUTIONAL_REVIEW.md` containing **ALL** of:

1. **Executive Review** — overall score + scores for every subsystem listed below
2. **Architecture Review**
3. **Quant Review** — bias checks on scoring models
4. **Portfolio Review**
5. **Opportunity Intelligence Review**
6. **Learning Review**
7. **AI Review**
8. **Performance Review** — latency targets
9. **UX Review**
10. **Testing Review**
11. **Commercial Review**
12. **Security Review**
13. **Top 100 improvements ranked by ROI** (table; group by tier if long)
14. **Next 10 sprint roadmap** (sprints 116–125, continuing from CC X roadmap)
15. **Horizon buckets:** Quick wins (&lt;1 day), High ROI (&lt;1 week), Major (&lt;1 month), Long-term vision (9.8–10.0)

#### Subsystems to score (each needs full template)

Knowledge Engine · Research Engine · Decision Engine · Portfolio Engine · Execution Engine · Intelligence Engine · Investment Object · AlphaObject · Authority/Governance · Data Provenance · ML/Learning · Opportunity Intelligence · Alpha Factory · IBKR/Execution · Ops/Scheduler · UI/UX · Testing/CI · Security · Commercial Readiness

**For EVERY subsystem provide:**

| Field               | Content                          |
| ------------------- | -------------------------------- |
| Current Score       | /10                              |
| Target Score        | /10 (CC X 9.5 path)              |
| Biggest Weaknesses  | Evidence from this repo          |
| Expected ROI        | $/yr or Sharpe/process alpha     |
| Difficulty          | Low / Medium / High              |
| Risk                | Authority / data / UX regression |
| Dependencies        | Modules, sprints                 |
| Acceptance Criteria | Testable gates                   |
| Recommended Sprint  | 116–126                          |

**For EVERY top recommendation provide:**

Problem · Evidence · Root Cause · Business Impact · Operator Impact · Expected ROI · Risk · Difficulty · Priority · Affected Files · Migration Plan · Acceptance Tests · Rollback Plan

---

### Cross-links (after review)

- Link from this file to `CC_X_FULL_INSTITUTIONAL_REVIEW.md` (above)
- Add one line to `docs/CC_CONSOLIDATED_BRIEFING.md` Quick Reference

---

### Do NOT

- Implement code changes in the review task
- Commit secrets or `.env` values
- Recommend auto-deploy, threshold loosening, or card-rank overrides
- Praise without evidence

---

### Return to operator

- Doc paths created/updated
- Overall platform score (/10)
- Top 5 ROI improvements (one line each)
- Sprint 116 headline

--- PROMPT END ---

---

_End of canonical CC X master review prompt._
