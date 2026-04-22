# MiSt

Sustainability analytics for caterers. Two modes — **procurement** (bulk-buy analysis) and **meal** (per-dish analysis) — built on the Dutch RIVM environmental database and the NEVO nutrition database.

See [VISION.md](VISION.md) for the full product vision, architecture, and phase plan. This is a living document — every session updates it.

## Repo layout

| Path | What |
|---|---|
| [backend/](backend) | FastAPI API (Python 3.12) |
| [frontend/](frontend) | React + Vite + TypeScript |
| [data/](data) | Committed reference data (SQLite + source xlsx, gitignored) |
| [legacy/](legacy) | v1 single-file app preserved for reference |
| [VISION.md](VISION.md) | Living vision / audit doc |

## Quickstart

### With Docker (recommended)

```bash
docker compose up
```

- Backend at http://localhost:8000 — `GET /health` returns `{"status":"ok"}`
- Frontend at http://localhost:5173
- Postgres at localhost:5432 (user/pw `mist`/`mist`)

### Local (no Docker)

Backend:
```bash
cd backend
python -m venv .venv
# Windows:   .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
cd backend
pytest
```

## Legacy v1

The original single-file app lives in [legacy/](legacy). To run it:

```bash
cd legacy
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn legacy_app:app --port 9000
# open http://127.0.0.1:9000
```

## Deployment

Target: **Railway** (Docker, with a Postgres addon for the user DB).
Config: [railway.json](railway.json), uses [backend/Dockerfile](backend/Dockerfile).
