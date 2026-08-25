# GitHub Copilot — 逐步修改 + Diff 驗證 Prompt

**版本：** 2026-05-25  
**用途：** Copilot Chat / Copilot Edits 做 **小步 patch**，每步 before/after 驗證  
**Master prompt：** `docs/INSTITUTIONAL_PLATFORM_MASTER_PROMPT_ZH.md`

---

## 點解用呢版

Copilot 最適合 **單文件、小 diff、解釋型修改**。呢版 prompt 防止 Copilot：

- 一次改成個 `index.html`
- 加 state key 但唔 init
- 加 API call 但 route 唔存在
- claim "fixed" 冇 syntax check

---

## Agent Prompt（開始）

You are GitHub Copilot assisting on an institutional trading platform repo (`TradingAI_Bot-main`).

Work in **small, verifiable steps**. One concern per edit turn. Always show before/after for the exact lines you change.

### Step protocol (mandatory every edit)

**Before editing:**

1. Quote the exact current code (5–20 lines) from the file.
2. State what is broken and whether confirmed from code or inferred.
3. State the minimal change you will make.

**After editing:**

1. Show the new code snippet.
2. List verification steps the developer must run.
3. State residual risk (e.g. "runtime not verified", "needs Docker restart").

### File-specific rules

#### `src/api/templates/index.html` (Alpine `cc()`)

- NEVER add DOM bindings (`x-text`, `x-show`, `@click`) without matching key in `cc()` return object init.
- NEVER add `switchTab('xyz')` without `x-show="tab==='xyz'"` section AND tab in `tabs` or `moreTabs`.
- NEVER add orphan `try {}` blocks outside functions — **this broke the entire UI once**.
- After ANY edit to the `<script>` block, tell user to run:
    ```bash
    python3 -c "
    from pathlib import Path
    h=Path('src/api/templates/index.html').read_text()
    i=h.find('<script>\n    function cc()'); j=h.find('</script>',i)
    Path('/tmp/cc.js').write_text(h[i+8:j])
    "
    node --check /tmp/cc.js
    ```

#### Backend routers / services

- Check route exists before wiring frontend:
    ```bash
    rg "@router\.(get|post).*your-path" src/api/routers/
    ```
- Match payload shape: grep frontend consumer first:
    ```bash
    rg "ccFetch.*your-path" src/api/templates/index.html
    ```
- After Python edits:
    ```bash
    python3 -m py_compile path/to/file.py
    ```

### Common patch patterns (copy templates)

#### Pattern A — Wire existing API to UI

```
BEFORE: fetch exists but wrong endpoint / missing state
AFTER:
  1. Add state key in cc() init: foo: null
  2. Add async fetchFoo() calling ccFetch('/api/v7/...')
  3. Call fetchFoo in switchTab or x-init when tab active
  4. Bind x-text/x-for to foo.* with x-show fallbacks for empty
VERIFY: rg fetchFoo; curl endpoint; node --check
```

#### Pattern B — Add field to existing API response

```
BEFORE: service returns partial dict
AFTER:
  1. Add field in service builder function only
  2. Add optional UI bind with x-show="obj?.field"
  3. Do NOT break existing keys
VERIFY: unittest or curl | python3 -m json.tool
```

#### Pattern C — Honest mock labeling

```
BEFORE: mock data looks live
AFTER:
  - Add provider: "mock" | source_label | evidence_quality
  - UI: x-show warning when provider !== live
VERIFY: response JSON includes label
```

### Do-not-touch without explicit request

- Broad tab renames / nav restructure
- Delete files (cleanup audit only — classify, don't delete)
- `git commit` / `git push`
- Secrets in code

### Scoring before suggesting features

Ask internally: **Does this help a PM with real capital?**

| If yes                             | If no                         |
| ---------------------------------- | ----------------------------- |
| Wire dead API with real data       | Add decorative AI card        |
| Fix undefined Alpine state         | Add duplicate KPI             |
| Label mock vs live                 | Add fake Sharpe               |
| Connect dossier → IB draft clearly | Add new tab without data path |

### Incremental task menu (pick ONE per session)

1. **Portfolio equity curve** — wire `/api/v7/portfolio-equity` into Portfolio tab
2. **Flow live provider** — env + honest `count_live` display
3. **Dossier action_box** — ensure UI renders `action_box` from stock-intel
4. **Ops section_states** — hide panels when `inactive`
5. **Leaders tracker** — replace placeholder in Funds overlay

### Verification checklist (paste after each Copilot edit)

```markdown
- [ ] Syntax: node --check /tmp/cc.js OR py_compile
- [ ] Route exists: rg @router
- [ ] State key init: rg "keyname:" in cc()
- [ ] DOM bind: rg "keyname" in template section
- [ ] API smoke: curl -sf ...
- [ ] Runtime: browser hard refresh / Docker restart if needed
```

### Anti-fake language

Replace Copilot defaults:

| Don't say                  | Say instead                                     |
| -------------------------- | ----------------------------------------------- |
| "Successfully implemented" | "Code change applied; verify with: ..."         |
| "The feature now works"    | "Expected behavior if X; verified: syntax only" |
| "Production ready"         | "Prototype-grade until curl + UI confirmed"     |

## Agent Prompt（結束）

---

## Copilot Chat 開場白（copy）

```
Follow docs/COPILOT_ENGINEERING_PROMPT_ZH.md step protocol.

Task: [ONE task from menu]

Rules:
- Quote before/after code
- One file focus if possible
- No commit
- End with verification checklist

Start by reading the current implementation in:
[list exact file paths]
```

---

## Example micro-task prompt

```
Wire GET /api/v7/portfolio-equity into Portfolio tab.

Files to inspect first:
- src/api/routers/platform_p2.py (response shape)
- src/api/templates/index.html (tab=portfolio, pfDecision fetch patterns)

Minimal change only. Add pfEquity state, fetchPortfolioEquity(), chart/table bind.
Show before/after. Verification checklist at end.
```
