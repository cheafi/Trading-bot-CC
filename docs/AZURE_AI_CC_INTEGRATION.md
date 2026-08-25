# Azure AI — CC Integration Guide

Maps CC X Tier 1 capabilities to Azure AI services and documents opt-in configuration for the Command Center (`ai_service.py`, Futu capture, research memory).

**Security:** Never commit secrets. All Azure endpoints must use `https://`. Store keys in `.env` or your secret manager only.

---

## MCP availability

| Tool namespace  | Status                                | Notes                                                      |
| --------------- | ------------------------------------- | ---------------------------------------------------------- |
| `azure__search` | **Not available** in this environment | Enable Azure MCP via `/azure:setup` or Cursor MCP settings |
| `azure__speech` | **Not available**                     | Same as above                                              |

When MCP is enabled, use `azure__search` for index management and hybrid queries, and `azure__speech` for transcription / TTS experiments. Until then, use Azure Portal, `az` CLI, or SDKs referenced in the [azure-ai skill](https://github.com/microsoft/skills).

---

## CC X → Azure AI service mapping

| CC X Tier 1 feature                              | Azure service               | Current CC module                                              | Integration status                                                |
| ------------------------------------------------ | --------------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------- |
| **Futu screenshot OCR**                          | Document Intelligence       | `futu_portfolio_parser.py` → `parse_futu_image_vision()`       | Doc-only fallback path (`azure_document_intelligence.py` planned) |
| **BDR / advisory / PM memo**                     | Azure OpenAI                | `ai_service.py`, `gpt_validator.py`, `ai_advisor.py`           | **Implemented** in `ai_service.py` (opt-in)                       |
| **Knowledge Graph + Continuous Research Memory** | AI Search (vector + hybrid) | `trade_memory_service.py`, `research_store.py`, `pm_memory.py` | Doc-only — needs index + ingest pipeline                          |
| **Voice PM assistant** (Tier 3)                  | Speech (STT/TTS)            | —                                                              | Future — optional                                                 |

### Recommended ROI order

1. **Azure OpenAI** — Highest ROI today. Endpoint + deployment already wired in Docker Compose; enables enterprise auth, data residency, and unified billing without changing CC ranking/gates.
2. **Document Intelligence** — Medium ROI for Futu capture when vision LLM cost/latency matters; strong for tabular OCR on HK/US holdings screenshots.
3. **AI Search** — High long-term ROI for Knowledge Graph (Sprint 121) and Continuous Research Memory (Sprint 125); requires index schema + embedding ingest.
4. **Speech** — Tier 3 polish; defer until core PM workflows are stable.

---

## What was implemented (this branch)

### Azure OpenAI in `ai_service.py`

- Opt-in via `AZURE_OPENAI_ENABLED=true` (OpenAI direct API remains default when unset).
- Supports **API key** or **service principal** auth (same pattern as `gpt_validator.py`).
- Deployment-based routing: `AZURE_OPENAI_DEPLOYMENT` plus optional per-task overrides.
- Used by narratives, signal analysis, PM memos, trade review JSON, and Futu vision parsing when enabled.
- Health endpoint reports `azure_openai` when enabled with valid auth.

Provider chain when Azure is enabled:

```
Local LLM → OpenClaw → NVIDIA → Azure OpenAI → OpenAI
```

### Not implemented (doc-only)

- `azure_document_intelligence.py` Futu OCR fallback — requires `DOCUMENTINTELLIGENCE_*` credentials (not set in this environment).
- AI Search index for research memory — requires `AZURE_SEARCH_*` credentials (not set).

---

## Environment variables

Copy placeholders into `.env` (never commit real values):

```bash
# ── Azure OpenAI (implemented in ai_service.py) ─────────────────────────────
AZURE_OPENAI_ENABLED=true
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2026-01-15-preview

# Auth option A — API key (simplest for dev)
AZURE_OPENAI_API_KEY=your-api-key-here

# Auth option B — service principal (production; omit API key)
AZURE_TENANT_ID=00000000-0000-0000-0000-000000000000
AZURE_CLIENT_ID=00000000-0000-0000-0000-000000000000
AZURE_CLIENT_SECRET=your-client-secret-here

# Optional per-task deployment overrides (same resource)
AZURE_OPENAI_DEPLOYMENT_NARRATIVE=gpt-4o
AZURE_OPENAI_DEPLOYMENT_SIGNAL=gpt-4o
AZURE_OPENAI_DEPLOYMENT_QUICK=gpt-4o-mini

# ── OpenAI direct (default path; unchanged) ─────────────────────────────────
OPENAI_API_KEY=sk-...
OPENAI_API_BASE=https://api.openai.com/v1

# ── Document Intelligence (planned Futu OCR fallback) ───────────────────────
DOCUMENTINTELLIGENCE_ENDPOINT=https://YOUR-DI-RESOURCE.cognitiveservices.azure.com
DOCUMENTINTELLIGENCE_API_KEY=your-di-key-here
# Or: AZURE_DI_ENDPOINT / AZURE_DI_KEY (alias — not wired yet)

# ── AI Search (planned Knowledge Graph / research memory) ───────────────────
AZURE_SEARCH_ENDPOINT=https://YOUR-SEARCH.search.windows.net
AZURE_SEARCH_API_KEY=your-search-admin-key-here
AZURE_SEARCH_INDEX=cc-research-memory

# ── Speech (Tier 3 — optional) ──────────────────────────────────────────────
AZURE_SPEECH_KEY=your-speech-key-here
AZURE_SPEECH_REGION=eastus
```

### Credential check (this environment)

| Variable                                                      | Status                                   |
| ------------------------------------------------------------- | ---------------------------------------- |
| `OPENAI_API_KEY`                                              | Set                                      |
| `AZURE_OPENAI_ENDPOINT`                                       | Set                                      |
| `AZURE_OPENAI_DEPLOYMENT`                                     | Set                                      |
| `AZURE_OPENAI_API_VERSION`                                    | Set                                      |
| `AZURE_OPENAI_API_KEY`                                        | Empty (service principal auth available) |
| `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` | Set                                      |
| `DOCUMENTINTELLIGENCE_*`                                      | Missing                                  |
| `AZURE_SEARCH_*`                                              | Missing                                  |

To activate Azure OpenAI in CC: set `AZURE_OPENAI_ENABLED=true` and restart the API.

---

## Setup steps

### 1. Azure OpenAI (ready now)

1. Create an Azure OpenAI resource in [Azure AI Foundry](https://ai.azure.com) or Portal.
2. Deploy models (e.g. `gpt-4o` for narrative/signal/vision, `gpt-4o-mini` for quick tasks).
3. Add env vars above; set `AZURE_OPENAI_ENABLED=true`.
4. Restart CC: `python _cc_instant.py` or `docker compose up`.
5. Verify: `GET /health` → `ai_status.provider` = `azure_openai`.

### 2. Document Intelligence (Futu OCR — future)

1. Create a **Document Intelligence** (Form Recognizer) resource.
2. Set `DOCUMENTINTELLIGENCE_ENDPOINT` + `DOCUMENTINTELLIGENCE_API_KEY`.
3. Planned flow: `parse_futu_image_vision()` tries Azure DI OCR → text regex → vision LLM fallback.

### 3. AI Search (Knowledge Graph — Sprint 121+)

1. Create Azure AI Search service (Basic or Standard).
2. Define index with vector fields for dossier chunks, PM notes, and decision artifacts.
3. Ingest from `research_store.py` / `pm_memory.py` on write or via nightly job.
4. Query from dossier and Decision Board research panels (hybrid keyword + vector).

### 4. Speech (Tier 3)

1. Create Speech resource; set `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION`.
2. Wire STT for voice PM queries; TTS for brief playback — not started.

---

## Existing Azure usage elsewhere in repo

These modules already use Azure OpenAI via the OpenAI SDK + `settings.use_azure_openai`:

| Module                         | Purpose                  |
| ------------------------------ | ------------------------ |
| `src/engines/gpt_validator.py` | Signal validation        |
| `src/engines/ai_advisor.py`    | Trading advisory         |
| `src/ml/trade_learner.py`      | Trade learning summaries |

`ai_service.py` now aligns with the same env vars but uses explicit `AZURE_OPENAI_ENABLED` so CC narratives do not silently switch providers.

---

## Docker Compose

`docker-compose.yml` already passes through Azure vars to engine containers. Add to your `.env`:

```bash
AZURE_OPENAI_ENABLED=true
```

No compose file changes required for the `ai_service.py` integration.

---

## Related docs

- [CC_X_INSTITUTIONAL_ALPHA_OS.md](./CC_X_INSTITUTIONAL_ALPHA_OS.md) — Tier 1–3 roadmap
- [FUTU_CAPTURE_SETUP.md](./FUTU_CAPTURE_SETUP.md) — Futu screenshot capture
- [CC_CONSOLIDATED_BRIEFING.md](./CC_CONSOLIDATED_BRIEFING.md) — Full env var reference
- [CC_PUBLIC_ACCESS.md](./CC_PUBLIC_ACCESS.md) — Dev tunneling (HTTPS only for public URLs)
