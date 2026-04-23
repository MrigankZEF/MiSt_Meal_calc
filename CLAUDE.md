# CLAUDE.md — MiSt session rules (auto-loaded)

> Claude Code loads this file automatically at session start.
> Follow every rule here without being reminded.

---

## Session-end rules (before final commit)

1. **Append to `CHANGELOG.md`** — new entry at the top (newest-first):
   ```
   - **YYYY-MM-DD · Claude (CLI) · <one-line summary>**
     - bullet describing what changed
   ```
2. **Update `VISION.md §0`** — set `Last session` date; update `Active features` and `Parked` lines if anything changed.

Do NOT wait to be reminded. Do NOT skip for small sessions.

---

## Dev gotchas

| Situation | Rule |
|---|---|
| Running tests | `source .venv/bin/activate && python3 -m pytest` (bare `python3` may miss installed packages) |
| Added columns to user-DB models | Delete `data/user.db` — `create_all()` never adds columns to existing tables. Warn that saved data will be lost. |
| RIVM / NEVO ingest on Windows | Run inside WSL: `wsl -d Ubuntu -- bash -lc "cd /home/mriga/.openclaw/workspace/projects/mist-mealcalc/backend && .venv/bin/python scripts/ingest_rivm.py"` — Windows Python on a `\\wsl$\...` UNC path gets SQLite "database is locked". |
| Before committing frontend changes | Run `npx tsc --noEmit` from `frontend/` to catch type errors. |
| Backend CWD | All backend commands assume `backend/` as CWD unless stated. |
