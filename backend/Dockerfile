# ── Stage 1: Build React frontend ─────────────────────────────────────────────
FROM node:20-alpine AS frontend

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# ── Stage 2: Python backend ────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install Python dependencies
# Editable install keeps __file__-based path resolution pointing at /app/app/,
# which is how config.py locates /data/reference.db at runtime.
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --upgrade pip && pip install -e .

COPY backend/scripts ./scripts

# Reference DB — committed read-only asset (RIVM + NEVO + EAT-Lancet tags)
COPY data/reference.db /data/reference.db

# Built frontend assets served by FastAPI at runtime
COPY --from=frontend /frontend/dist ./frontend_dist

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
