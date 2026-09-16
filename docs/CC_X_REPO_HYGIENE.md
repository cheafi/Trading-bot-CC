# CC X — Repository Hygiene

**Updated:** 2026-09-16 · Branch `cc/upgrade-regime-tracking`

Minimal disposition after external safety review §Repository hygiene.

## Tooling location

| Item              | Location                                               | Notes                                                      |
| ----------------- | ------------------------------------------------------ | ---------------------------------------------------------- |
| CC instant server | `scripts/cc_instant.py`                                | Root `_cc_instant.py` is a thin launcher (backward compat) |
| Project cleanup   | `scripts/cleanup.sh`                                   | `make clean` / `make cleanup-dry-run`                      |
| Entry points      | `run_bot.py`, `run_dashboard.py`, `run_discord_bot.py` | Legitimate root launchers                                  |

## Removed from root (2026-09-16)

Scratch one-off scripts (`fix_*.py`, `patch_*.py`, `purge_*.py`, `test_*.py`, `vars_check*.py`, `check*.js`, etc.), local logs (`*.log`), `progress.txt`, `tags.txt`, `import` log stub, `cc_cursor_chatgpt_bridge.zip`.

Patterns are in `.gitignore` to prevent re-commit.

## Ignored / local-only

- `backup_untracked/` — local backup scratch
- `data/state/` — runtime locks, heartbeat, server logs
- `data/cache/` — generated caches (yfinance, dashboard gzip)
- `.env` — secrets (never commit)
- `.roo/` — 360K rules only; `mcp.json` gitignored
- `.vscode/` — settings only (extensions/tasks/launch)

## State paths

Authoritative runtime state uses `src/core/state_paths.py` → `data/state/` or `STATE_DATA_DIR` volume. No `/tmp` for locks or caches.
